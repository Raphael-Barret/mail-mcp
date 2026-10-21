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


class DraftingBackend(MailBackend):
    """Capacité `draft` : écrire un brouillon, jamais l'envoyer."""

    @abstractmethod
    def create_draft(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        reply_to_message_id: str | None = None,
    ) -> str: ...


class ArchivingBackend(MailBackend):
    """Capacité `archive` : sortir un message de la boîte de réception, sans le détruire."""

    @abstractmethod
    def archive(self, message_id: str) -> str: ...


# Capacités d'écriture : chacune est une interface distincte, activée par compte
# dans la configuration (`allow`), jamais par un argument d'outil. `send` et
# `delete` viendront plus tard sur le même modèle.
