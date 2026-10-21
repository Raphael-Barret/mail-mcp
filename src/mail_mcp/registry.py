from __future__ import annotations

from collections.abc import Callable

from .backends import MailBackend
from .config import AccountConfig

BackendFactory = Callable[[AccountConfig], MailBackend]

# Un backend s'enregistre ici ; ajouter un compte ne demande qu'une entrée de config.
BACKENDS: dict[str, BackendFactory] = {}


def build_backend(account: AccountConfig) -> MailBackend:
    try:
        factory = BACKENDS[account.backend]
    except KeyError:
        raise ValueError(f"Backend inconnu '{account.backend}' pour '{account.name}'") from None
    return factory(account)
