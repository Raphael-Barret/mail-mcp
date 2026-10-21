from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import MessageBody, MessageSummary


class MailBackend(ABC):
    """Interface de lecture commune. Un backend par technologie (IMAP, Gmail API, Graph)."""

    name: str

    @abstractmethod
    def list_messages(
        self, folder: str = "INBOX", limit: int = 20, unread_only: bool = False
    ) -> list[MessageSummary]: ...

    @abstractmethod
    def search(self, query: str, folder: str = "INBOX", limit: int = 20) -> list[MessageSummary]: ...

    @abstractmethod
    def get_message(self, message_id: str) -> MessageBody: ...

    @abstractmethod
    def get_thread(self, message_id: str) -> list[MessageBody]: ...


class WritableBackend(MailBackend):
    """Capacité d'écriture, distincte de la lecture.

    Un backend ne l'implémente que s'il sait écrire, et le serveur n'expose les
    outils correspondants que pour les comptes dont la configuration active
    `write_enabled`. Jamais par un argument d'outil.
    """

    @abstractmethod
    def send(self, to: list[str], subject: str, body: str) -> str: ...

    @abstractmethod
    def reply(self, message_id: str, body: str) -> str: ...

    @abstractmethod
    def archive(self, message_id: str) -> None: ...

    @abstractmethod
    def delete(self, message_id: str) -> None: ...
