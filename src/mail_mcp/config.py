from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import keyring
import keyring.errors

KEYRING_SERVICE = "mail-mcp"
# Capacités d'écriture activables par compte (`allow`). Aucune par défaut.
CAPABILITIES = frozenset({"draft", "archive"})


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
        try:
            value = keyring.get_password(KEYRING_SERVICE, self.name)
        except keyring.errors.KeyringError as e:
            raise RuntimeError(
                f"Trousseau indisponible ({e}). Sous Linux, un service Secret Service "
                "(gnome-keyring, KWallet) doit tourner et être déverrouillé."
            ) from e
        if value is None:
            raise RuntimeError(
                f"Aucun secret dans le trousseau pour le compte '{self.name}' "
                f"(service '{KEYRING_SERVICE}') : `mail-mcp set-secret {self.name}`"
            )
        return value


def default_config_path() -> Path:
    """%APPDATA% sous Windows, sinon $XDG_CONFIG_HOME ou ~/.config (macOS compris)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "mail-mcp" / "config.toml"


def config_path() -> Path:
    return Path(os.environ.get("MAIL_MCP_CONFIG") or default_config_path())


def load_accounts(path: Path | None = None) -> dict[str, AccountConfig]:
    path = path or config_path()
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    accounts: dict[str, AccountConfig] = {}
    for name, entry in raw.get("accounts", {}).items():
        entry = {**entry, "allow": tuple(entry.get("allow", ()))}
        accounts[name] = AccountConfig(name=name, **entry)
    return accounts
