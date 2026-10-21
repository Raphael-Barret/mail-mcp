from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import keyring

KEYRING_SERVICE = "mail-mcp"
# Capacités d'écriture activables par compte (`allow`). Aucune par défaut.
CAPABILITIES = frozenset({"draft", "archive"})
DEFAULT_PATH = Path.home() / ".config" / "mail-mcp" / "config.toml"


@dataclass(frozen=True)
class AccountConfig:
    name: str
    backend: str
    username: str = ""
    host: str = ""
    port: int = 993
    security: str = "ssl"
    address: str = ""
    allow: tuple[str, ...] = ()
    drafts_folder: str = ""
    archive_folder: str = ""

    def __post_init__(self) -> None:
        unknown = set(self.allow) - CAPABILITIES
        if unknown:
            raise ValueError(
                f"Compte '{self.name}' : capacités inconnues {sorted(unknown)} "
                f"(permises : {sorted(CAPABILITIES)})"
            )

    @property
    def write_enabled(self) -> bool:
        return bool(self.allow)

    @property
    def from_address(self) -> str:
        return self.address or self.username

    def secret(self) -> str:
        value = keyring.get_password(KEYRING_SERVICE, self.name)
        if value is None:
            raise RuntimeError(
                f"Aucun secret dans le Trousseau pour le compte '{self.name}' "
                f"(service '{KEYRING_SERVICE}')"
            )
        return value


def config_path() -> Path:
    return Path(os.environ.get("MAIL_MCP_CONFIG", DEFAULT_PATH))


def load_accounts(path: Path | None = None) -> dict[str, AccountConfig]:
    path = path or config_path()
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    accounts: dict[str, AccountConfig] = {}
    for name, entry in raw.get("accounts", {}).items():
        entry = {**entry, "allow": tuple(entry.get("allow", ()))}
        accounts[name] = AccountConfig(name=name, **entry)
    return accounts
