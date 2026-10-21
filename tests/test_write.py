import asyncio

import pytest

from mail_mcp.backends.imap import ImapBackend, WriteIMAP
from mail_mcp.config import AccountConfig, load_accounts
from mail_mcp.server import create_server

LIST = [
    b'(\\HasNoChildren) "/" "INBOX"',
    b'(\\HasNoChildren \\Drafts) "/" "[Gmail]/Brouillons"',
    b'(\\HasNoChildren \\All) "/" "[Gmail]/Tous les messages"',
]


class FakeWriteConn:
    """Imite imaplib.IMAP4 côté écriture et note chaque commande reçue."""

    def __init__(self, caps=("IMAP4REV1", "MOVE"), listing=LIST):
        self.calls, self._caps, self._listing = [], caps, listing
        self.capabilities = ()

    def capability(self):
        self.capabilities = self._caps
        return "OK", [b""]

    def list(self):
        return "OK", self._listing

    def select(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        return "OK", [b"3"]

    def response(self, name):
        return name, [b"42"]

    def append(self, folder, flags, date, raw):
        self.calls.append(("append", folder, flags, raw))
        return "OK", [b"done"]

    def uid(self, command, *args):
        self.calls.append(("uid", command, args))
        return "OK", [b""]

    def logout(self):
        self.calls.append(("logout",))


def make(monkeypatch, conn=None, **cfg):
    conn = conn or FakeWriteConn()
    acc = AccountConfig(
        name="t", backend="imap", host="h", username="me@example.com", allow=("draft", "archive"), **cfg
    )
    b = ImapBackend(acc)
    monkeypatch.setattr(b, "_connect_write", lambda: WriteIMAP(conn))
    return b, conn


def tool_names(accounts):
    return {t.name for t in asyncio.run(create_server(accounts).list_tools())}


# -- exposition des outils -------------------------------------------------
def test_tools_only_for_allowed_capabilities():
    a = AccountConfig(name="a", backend="imap", allow=("draft",))
    names = tool_names({"a": a})
    assert "create_draft" in names and "archive_message" not in names


def test_calls_refused_on_account_without_capability():
    ok = AccountConfig(name="ok", backend="imap", allow=("draft",))
    ro = AccountConfig(name="ro", backend="imap")
    server = create_server({"ok": ok, "ro": ro})
    with pytest.raises(Exception) as exc:
        asyncio.run(
            server.call_tool(
                "create_draft", {"account": "ro", "to": ["x@y.fr"], "subject": "s", "body": "b"}
            )
        )
    cause = exc.value.__cause__ or exc.value
    assert isinstance(cause, PermissionError) and "non autorisée" in str(cause)


def test_unknown_capability_rejected_by_config():
    with pytest.raises(ValueError, match="inconnues"):
        AccountConfig(name="a", backend="imap", allow=("send",))


def test_allow_parsed_from_toml(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[accounts.a]\nbackend = "imap"\nallow = ["draft", "archive"]\n[accounts.b]\nbackend = "imap"\n')
    accs = load_accounts(f)
    assert accs["a"].allow == ("draft", "archive") and not accs["b"].write_enabled


# -- brouillon ---------------------------------------------------------------
def test_draft_goes_to_drafts_folder_and_is_not_sent(monkeypatch):
    b, conn = make(monkeypatch)
    out = b.create_draft(["bob@example.com"], "Café", "Salut", cc=["c@example.com"])
    (_, folder, flags, raw), = [c for c in conn.calls if c[0] == "append"]
    assert folder == '"[Gmail]/Brouillons"' and flags == "(\\Draft)"
    assert b"To: bob@example.com" in raw and b"From: me@example.com" in raw
    assert b"Cc: c@example.com" in raw and "Brouillon" in out
    assert not [c for c in conn.calls if c[0] == "uid"]


def test_draft_rejects_header_injection(monkeypatch):
    b, conn = make(monkeypatch)
    with pytest.raises(ValueError):
        b.create_draft(["bob@example.com\r\nBcc: evil@example.com"], "s", "b")
    with pytest.raises(ValueError):
        b.create_draft(["bob@example.com"], "s\r\nBcc: evil@example.com", "b")
    assert not [c for c in conn.calls if c[0] == "append"]


def test_draft_reply_sets_thread_headers(monkeypatch):
    b, conn = make(monkeypatch)
    monkeypatch.setattr(
        b,
        "_reply_context",
        lambda _id: {
            "Message-ID": "<m1@x>", "References": "<m0@x>", "Subject": "Question",
            "From": "Alice <alice@example.com>", "Reply-To": "",
        },
    )
    b.create_draft([], "", "Merci", reply_to_message_id="INBOX|42|1")
    raw = [c for c in conn.calls if c[0] == "append"][0][3]
    assert b"To: Alice <alice@example.com>" in raw and b"Subject: Re: Question" in raw
    assert b"In-Reply-To: <m1@x>" in raw and b"References: <m0@x> <m1@x>" in raw


def test_draft_folder_override_and_missing(monkeypatch):
    b, conn = make(monkeypatch, drafts_folder="Mes brouillons")
    b.create_draft(["bob@example.com"], "s", "b")
    assert [c for c in conn.calls if c[0] == "append"][0][1] == '"Mes brouillons"'
    b2, _ = make(monkeypatch, conn=FakeWriteConn(listing=[b'(\\HasNoChildren) "/" "INBOX"']))
    with pytest.raises(RuntimeError, match="drafts_folder"):
        b2.create_draft(["bob@example.com"], "s", "b")


# -- archivage ---------------------------------------------------------------
def test_archive_moves_to_all_mail_without_deleting(monkeypatch):
    b, conn = make(monkeypatch)
    b.archive("INBOX|42|7")
    assert ("uid", "MOVE", ("7", '"[Gmail]/Tous les messages"')) in conn.calls
    assert {c[1] for c in conn.calls if c[0] == "uid"} == {"MOVE"}  # ni STORE ni EXPUNGE


def test_archive_refuses_without_move_stale_id_or_archive_folder(monkeypatch):
    b, _ = make(monkeypatch, conn=FakeWriteConn(caps=("IMAP4REV1",)))
    with pytest.raises(RuntimeError, match="MOVE"):
        b.archive("INBOX|42|7")
    b, conn = make(monkeypatch)
    with pytest.raises(LookupError):
        b.archive("INBOX|7|7")
    assert not [c for c in conn.calls if c[0] == "uid"]
    with pytest.raises(ValueError, match="déjà"):
        make(monkeypatch)[0].archive("[Gmail]/Tous les messages|42|7")


def test_write_connection_has_no_destructive_commands():
    w = WriteIMAP(FakeWriteConn())
    for name in ("store", "expunge", "delete", "copy", "uid", "rename"):
        assert not hasattr(w, name)


class GmailConn(FakeWriteConn):
    """Gmail simulé : le message quitte INBOX seulement si `applies` est vrai."""

    def __init__(self, applies=True):
        super().__init__(caps=("IMAP4REV1", "X-GM-EXT-1"))
        self.applies, self.gone = applies, False

    def uid(self, command, *args):
        self.calls.append(("uid", command, args))
        if command == "STORE" and self.applies:
            self.gone = True
        if command == "SEARCH":
            return "OK", [b"" if self.gone else b"7"]
        return "OK", [b""]


def test_archive_gmail_removes_inbox_label_only(monkeypatch):
    conn = GmailConn()
    b, _ = make(monkeypatch, conn=conn)
    b.archive("INBOX|42|7")
    assert [c[1] for c in conn.calls if c[0] == "uid"] == ["STORE", "SEARCH"]
    assert [c for c in conn.calls if c[:2] == ("uid", "STORE")][0][2] == ("7", "-X-GM-LABELS", "(\\Inbox)")
    with pytest.raises(ValueError, match="INBOX"):
        b.archive("[Gmail]/Spam|42|7")


def test_archive_gmail_fails_loudly_if_message_stays_in_inbox(monkeypatch):
    b, _ = make(monkeypatch, conn=GmailConn(applies=False))
    with pytest.raises(RuntimeError, match="non effectué"):
        b.archive("INBOX|42|7")


def test_archive_without_move_copies_then_expunges_that_uid(monkeypatch):
    conn = FakeWriteConn(caps=("IMAP4REV1", "UIDPLUS"), listing=[b'(\\HasNoChildren) "/" "INBOX"'])
    b, _ = make(monkeypatch, conn=conn, archive_folder="Archive")
    b.archive("INBOX|42|7")
    assert [c[1:] for c in conn.calls if c[0] == "uid"] == [
        ("COPY", ("7", '"Archive"')),
        ("STORE", ("7", "+FLAGS.SILENT", "(\\Deleted)")),
        ("EXPUNGE", ("7",)),
    ]


def test_archive_without_move_needs_an_archive_folder(monkeypatch):
    conn = FakeWriteConn(caps=("IMAP4REV1", "UIDPLUS"), listing=[b'(\\HasNoChildren) "/" "INBOX"'])
    b, _ = make(monkeypatch, conn=conn)
    with pytest.raises(RuntimeError, match="archive_folder"):
        b.archive("INBOX|42|7")
    assert not [c for c in conn.calls if c[0] == "uid"]


def test_failed_copy_never_removes_the_message(monkeypatch):
    class Failing(FakeWriteConn):
        def uid(self, command, *args):
            self.calls.append(("uid", command, args))
            return ("NO", [b"quota"]) if command == "COPY" else ("OK", [b""])

    conn = Failing(caps=("IMAP4REV1", "UIDPLUS"))
    b, _ = make(monkeypatch, conn=conn, archive_folder="Archive")
    with pytest.raises(RuntimeError):
        b.archive("INBOX|42|7")
    assert [c[1] for c in conn.calls if c[0] == "uid"] == ["COPY"]
