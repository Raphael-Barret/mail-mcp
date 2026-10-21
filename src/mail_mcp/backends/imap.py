from __future__ import annotations

import imaplib
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from html.parser import HTMLParser

from ..config import AccountConfig
from ..models import MessageBody, MessageSummary
from ..registry import BACKENDS
from .base import MailBackend

SNIPPET_LEN = 160
PREVIEW_BYTES = 6000
# En-têtes lus pour un résumé : les autres (Received...) peuvent peser des Ko.
SUMMARY_HEADERS = "FROM SUBJECT DATE MIME-VERSION CONTENT-TYPE CONTENT-TRANSFER-ENCODING"
MAX_BODY_CHARS = 100_000
TIMEOUT = 30

# Seules commandes autorisées sur la connexion : aucune ne modifie la boîte.
_ALLOWED_UID_COMMANDS = {"FETCH", "SEARCH"}


class ReadOnlyIMAP:
    """Enveloppe d'imaplib qui n'expose que la lecture.

    Les dossiers sont ouverts avec EXAMINE (select readonly) et les corps sont
    lus avec BODY.PEEK, donc ni flags ni état de la boîte ne changent. Toute
    autre commande (STORE, COPY, APPEND, EXPUNGE, DELETE...) n'existe pas ici.
    """

    def __init__(self, conn: imaplib.IMAP4):
        self._c = conn

    def select(self, folder: str) -> int:
        typ, data = self._c.select(_quote(folder), readonly=True)
        if typ != "OK":
            raise RuntimeError(f"Dossier inaccessible : {folder}")
        return int(data[0])

    def uid(self, command: str, *args: str):
        if command.upper() not in _ALLOWED_UID_COMMANDS:
            raise PermissionError(f"Commande IMAP interdite en lecture seule : {command}")
        return self._c.uid(command, *args)

    def search(self, *criteria: str | bytes) -> list[bytes]:
        typ, data = self._c.uid("SEARCH", "CHARSET", "UTF-8", *criteria)
        if typ != "OK":
            raise RuntimeError("Recherche IMAP refusée")
        return data[0].split() if data and data[0] else []

    def logout(self) -> None:
        try:
            self._c.logout()
        except Exception:
            pass


def _quote(folder: str) -> str:
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _make_id(folder: str, uidvalidity: str, uid: str) -> str:
    return f"{folder}|{uidvalidity}|{uid}"


def _split_id(message_id: str) -> tuple[str, str, str]:
    parts = message_id.rsplit("|", 2)
    if len(parts) != 3:
        raise ValueError(f"Identifiant de message invalide : {message_id!r}")
    return parts[0], parts[1], parts[2]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return "".join(p.parts)


def _body_text(msg: EmailMessage) -> str:
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        text = part.get_content()
    except Exception:
        return ""
    if part.get_content_type() == "text/html":
        text = _html_to_text(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _addresses(msg: EmailMessage, header: str) -> list[str]:
    value = msg.get(header)
    if not value:
        return []
    return [str(a) for a in getattr(value, "addresses", [])] or [str(value)]


def _parse_fetch(data: list) -> list[tuple[str, set[str], bytes]]:
    """Extrait (uid, flags, octets) de chaque réponse FETCH d'imaplib.

    Quand une réponse contient plusieurs sections, imaplib renvoie un tuple par
    section, dans un ordre que le serveur choisit (Gmail renvoie le corps avant
    les en-têtes). Les sections sont rangées d'après leur étiquette et
    recollées en-têtes d'abord ; celles sans UID se rattachent à la précédente.
    """
    out: list[tuple[str, set[str], bytearray, bytearray]] = []
    for item in data:
        if not isinstance(item, tuple):
            continue
        head = item[0].decode("ascii", "replace")
        uid = re.search(r"UID (\d+)", head)
        if uid:
            flags = re.search(r"FLAGS \(([^)]*)\)", head)
            out.append((uid.group(1), set((flags.group(1) if flags else "").split()), bytearray(), bytearray()))
        elif not out:
            continue
        section = "HEADER" if "BODY[HEADER" in head else "BODY"
        out[-1][2 if section == "HEADER" else 3].extend(item[1])
    return [(u, f, bytes(h + b)) for u, f, h, b in out]


class ImapBackend(MailBackend):
    def __init__(self, account: AccountConfig):
        self.account = account
        self.name = account.name

    # -- connexion ---------------------------------------------------------
    def _connect(self) -> ReadOnlyIMAP:
        a = self.account
        if a.security == "ssl":
            conn: imaplib.IMAP4 = imaplib.IMAP4_SSL(a.host, a.port, timeout=TIMEOUT)
        elif a.security == "starttls":
            conn = imaplib.IMAP4(a.host, a.port, timeout=TIMEOUT)
            conn.starttls()
        else:
            raise ValueError(f"Sécurité non supportée : {a.security!r} (ssl ou starttls)")
        conn.login(a.username, a.secret())
        return ReadOnlyIMAP(conn)

    # -- construction des résumés -------------------------------------------
    def _summaries(
        self, c: ReadOnlyIMAP, folder: str, uidvalidity: str, uids: list[str]
    ) -> list[MessageSummary]:
        if not uids:
            return []
        typ, data = c.uid(
            "FETCH",
            ",".join(uids),
            f"(FLAGS BODY.PEEK[HEADER.FIELDS ({SUMMARY_HEADERS})] BODY.PEEK[TEXT]<0.{PREVIEW_BYTES}>)",
        )
        if typ != "OK":
            raise RuntimeError("FETCH refusé")
        by_uid = {}
        for uid, flags, raw in _parse_fetch(data):
            by_uid[uid] = self._summary(folder, uidvalidity, uid, flags, raw)
        return [by_uid[u] for u in uids if u in by_uid]

    def _summary(
        self, folder: str, uidvalidity: str, uid: str, flags: set[str], raw: bytes
    ) -> MessageSummary:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        return MessageSummary(
            account=self.name,
            id=_make_id(folder, uidvalidity, uid),
            sender=str(msg.get("From", "")),
            subject=str(msg.get("Subject", "")),
            date=_safe_date(msg),
            unread="\\Seen" not in flags,
            snippet=_body_text(msg)[:SNIPPET_LEN].replace("\n", " "),
        )

    def _uidvalidity(self, c: ReadOnlyIMAP) -> str:
        typ, data = c._c.response("UIDVALIDITY")
        return data[0].decode() if data and data[0] else "0"

    def _recent(self, c: ReadOnlyIMAP, folder: str, uids: list[bytes], limit: int):
        chosen = [u.decode() for u in uids[-limit:]][::-1]  # plus récents d'abord
        return self._summaries(c, folder, self._uidvalidity(c), chosen)

    # -- interface MailBackend ----------------------------------------------
    def list_messages(self, folder="INBOX", limit=20, unread_only=False):
        c = self._connect()
        try:
            c.select(folder)
            uids = c.search("UNSEEN" if unread_only else "ALL")
            return self._recent(c, folder, uids, limit)
        finally:
            c.logout()

    def search(self, query, folder="INBOX", limit=20):
        c = self._connect()
        try:
            c.select(folder)
            uids = c.search("TEXT", query.encode("utf-8"))
            return self._recent(c, folder, uids, limit)
        finally:
            c.logout()

    def _fetch_full(self, c: ReadOnlyIMAP, folder: str, uid: str) -> MessageBody:
        typ, data = c.uid("FETCH", uid, "(FLAGS BODY.PEEK[])")
        parsed = _parse_fetch(data) if typ == "OK" else []
        if not parsed:
            raise LookupError(f"Message introuvable : {folder} uid {uid}")
        _, flags, raw = parsed[0]
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        summary = self._summary(folder, self._uidvalidity(c), uid, flags, raw)
        return MessageBody(
            summary=summary,
            to=_addresses(msg, "To"),
            cc=_addresses(msg, "Cc"),
            text=_body_text(msg)[:MAX_BODY_CHARS],
            thread_id=str(msg.get("Message-ID", "")) or None,
        )

    def get_message(self, message_id):
        folder, validity, uid = _split_id(message_id)
        c = self._connect()
        try:
            c.select(folder)
            if self._uidvalidity(c) != validity:
                raise LookupError("Identifiant périmé (UIDVALIDITY a changé), relister le dossier")
            return self._fetch_full(c, folder, uid)
        finally:
            c.logout()

    def get_thread(self, message_id):
        folder, validity, uid = _split_id(message_id)
        c = self._connect()
        try:
            c.select(folder)
            if self._uidvalidity(c) != validity:
                raise LookupError("Identifiant périmé (UIDVALIDITY a changé), relister le dossier")
            typ, data = c.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES)])")
            parsed = _parse_fetch(data) if typ == "OK" else []
            if not parsed:
                raise LookupError(f"Message introuvable : {folder} uid {uid}")
            hdr = BytesParser(policy=policy.default).parsebytes(parsed[0][2])
            ids = set(re.findall(r"<[^>]+>", f"{hdr.get('Message-ID', '')} {hdr.get('References', '')}"))
            found: set[str] = {uid}
            for mid in ids:
                for header in ("MESSAGE-ID", "REFERENCES"):
                    found.update(u.decode() for u in c.search("HEADER", header, mid))
            ordered = sorted(found, key=int)
            return [self._fetch_full(c, folder, u) for u in ordered]
        finally:
            c.logout()


def _safe_date(msg: EmailMessage):
    try:
        return msg["Date"].datetime if msg["Date"] else None
    except Exception:
        return None


BACKENDS["imap"] = ImapBackend
