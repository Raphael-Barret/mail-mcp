from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class MessageSummary:
    """Format de sortie unifié, identique pour tous les backends."""

    account: str
    id: str
    sender: str
    subject: str
    date: datetime | None
    unread: bool
    snippet: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat() if self.date else None
        return d


@dataclass(frozen=True)
class MessageBody:
    summary: MessageSummary
    to: list[str]
    cc: list[str]
    text: str
    thread_id: str | None = None

    def to_dict(self) -> dict:
        d = self.summary.to_dict()
        d.update(to=self.to, cc=self.cc, text=self.text, thread_id=self.thread_id)
        return d
