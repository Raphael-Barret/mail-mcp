import sys
from pathlib import Path

import keyring
import keyring.errors
import pytest
from keyring.backend import KeyringBackend

from mail_mcp import cli, config
from mail_mcp.config import AccountConfig, default_config_path


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


@pytest.fixture
def mem(monkeypatch, tmp_path):
    backend = MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    cfg = tmp_path / "config.toml"
    cfg.write_text('[accounts.a]\nbackend = "imap"\n')
    monkeypatch.setenv("MAIL_MCP_CONFIG", str(cfg))
    yield backend
    keyring.set_keyring(previous)


def answers(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(it))


def test_set_secret_stores_and_account_reads_it_back(mem, monkeypatch):
    answers(monkeypatch, "s3cret", "s3cret")
    assert cli.main(["set-secret", "a"]) == 0
    assert AccountConfig(name="a", backend="imap").secret() == "s3cret"


@pytest.mark.parametrize("pair", [("", ""), ("one", "two")])
def test_set_secret_refuses_empty_or_mismatch(mem, monkeypatch, pair):
    answers(monkeypatch, *pair)
    assert cli.main(["set-secret", "a"]) == 2
    assert mem.store == {}


def test_set_secret_refuses_unknown_account(mem, monkeypatch):
    answers(monkeypatch, "x", "x")
    assert cli.main(["set-secret", "typo"]) == 2
    assert mem.store == {}


def test_missing_secret_message_points_to_the_command(mem):
    with pytest.raises(RuntimeError, match="mail-mcp set-secret a"):
        AccountConfig(name="a", backend="imap").secret()


def test_no_keyring_backend_gives_actionable_error(monkeypatch):
    def boom(*a, **k):
        raise keyring.errors.NoKeyringError("none")

    monkeypatch.setattr(config.keyring, "get_password", boom)
    with pytest.raises(RuntimeError, match="Secret Service"):
        AccountConfig(name="a", backend="imap").secret()


def test_default_config_path_per_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert default_config_path() == tmp_path / "Roaming" / "mail-mcp" / "config.toml"

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert default_config_path() == tmp_path / "xdg" / "mail-mcp" / "config.toml"

    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert default_config_path() == tmp_path / "home" / ".config" / "mail-mcp" / "config.toml"
