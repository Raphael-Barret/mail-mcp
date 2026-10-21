from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import keyring

KEYRING_SERVICE = "mail-mcp"
DEFAULT_PATH = Path.home() / ".config" / "mail-mcp" / "config.toml"


@dataclass(frozen=True)
class AccountConfig:
    name: str
    backend: str
    username: str = ""
    host: str = ""
    port: int = 993
    security: str = "ssl"
    write_enabled: bool = False

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
        accounts[name] = AccountConfig(name=name, **entry)
    return accounts
