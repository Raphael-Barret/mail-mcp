import pytest

from mail_mcp.backends import imap as imap_mod
from mail_mcp.backends.imap import ImapBackend, ReadOnlyIMAP
from mail_mcp.config import AccountConfig

RAW = (
    b"From: Alice <alice@example.com>\r\nTo: bob@example.com\r\n"
    b"Subject: =?utf-8?q?Caf=C3=A9?=\r\nDate: Tue, 21 Oct 2026 09:00:00 +0000\r\n"
    b"Message-ID: <m1@example.com>\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
    b"Bonjour le monde\r\n"
)


class FakeConn:
    """Imite imaplib.IMAP4 et enregistre toutes les commandes reçues."""

    def __init__(self, flags="(\\Seen)"):
        self.calls = []
        self.flags = flags

    def select(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        return "OK", [b"2"]

    def response(self, name):
        return name, [b"42"]

    def uid(self, command, *args):
        self.calls.append(("uid", command, args))
        if command == "SEARCH":
            return "OK", [b"1 2"]
        uids = args[0].split(",")
        data = []
        for u in uids:
            head = f"{u} (UID {u} FLAGS {self.flags} BODY[] {{{len(RAW)}}}".encode()
            data += [(head, RAW), b")"]
        return "OK", data

    def logout(self):
        self.calls.append(("logout",))


@pytest.fixture
def backend(monkeypatch):
    conn = FakeConn()
    b = ImapBackend(AccountConfig(name="t", backend="imap", host="h", username="u"))
    monkeypatch.setattr(b, "_connect", lambda: ReadOnlyIMAP(conn))
    return b, conn


def test_list_is_readonly_and_unified(backend):
    b, conn = backend
    msgs = b.list_messages(limit=5)
    assert [m.id for m in msgs] == ["INBOX|42|2", "INBOX|42|1"]  # récents d'abord
    m = msgs[0]
    assert (m.sender, m.subject, m.unread, m.snippet) == (
        "Alice <alice@example.com>", "Café", False, "Bonjour le monde")
    assert ("select", '"INBOX"', True) in conn.calls  # EXAMINE
    fetches = [c for c in conn.calls if c[:2] == ("uid", "FETCH")]
    assert fetches and all("BODY.PEEK" in c[2][1] for c in fetches)
    assert {c[1] for c in conn.calls if c[0] == "uid"} <= {"FETCH", "SEARCH"}


def test_unread_flag(monkeypatch):
    conn = FakeConn(flags="()")
    b = ImapBackend(AccountConfig(name="t", backend="imap"))
    monkeypatch.setattr(b, "_connect", lambda: ReadOnlyIMAP(conn))
    assert b.list_messages()[0].unread is True


def test_get_message(backend):
    b, _ = backend
    body = b.get_message("INBOX|42|1")
    assert body.text == "Bonjour le monde" and body.to == ["bob@example.com"]


def test_stale_uidvalidity_rejected(backend):
    b, _ = backend
    with pytest.raises(LookupError):
        b.get_message("INBOX|7|1")


def test_write_commands_do_not_exist():
    ro = ReadOnlyIMAP(FakeConn())
    for cmd in ("STORE", "COPY", "EXPUNGE"):
        with pytest.raises(PermissionError):
            ro.uid(cmd, "1")
    for name in ("store", "copy", "append", "expunge", "delete", "create"):
        assert not hasattr(ro, name)


def test_backend_registered():
    assert imap_mod.BACKENDS["imap"] is ImapBackend
