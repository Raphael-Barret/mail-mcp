"""Tests exécutés sur chaque système par la CI : démarrage réel du serveur et trousseau réel."""
import asyncio
import os
import sys
import uuid

import keyring
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mail_mcp.config import KEYRING_SERVICE, AccountConfig


def test_server_starts_over_stdio_and_exposes_read_tools(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[accounts.a]\nbackend = "imap"\nhost = "localhost"\nusername = "u"\n')
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mail_mcp.cli"],
        env={**os.environ, "MAIL_MCP_CONFIG": str(cfg)},
    )

    async def run():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return {t.name for t in (await session.list_tools()).tools}

    names = asyncio.run(asyncio.wait_for(run(), timeout=60))
    assert {"list_accounts", "list_messages", "search_messages", "read_message", "read_thread"} <= names
    assert not {n for n in names if n in ("create_draft", "archive_message")}


@pytest.mark.skipif(sys.platform != "win32", reason="Credential Manager : Windows seulement")
def test_windows_credential_manager_round_trip():
    name = f"ci-{uuid.uuid4().hex[:8]}"
    keyring.set_password(KEYRING_SERVICE, name, "mot de passe é à ç")
    try:
        assert AccountConfig(name=name, backend="imap").secret() == "mot de passe é à ç"
    finally:
        keyring.delete_password(KEYRING_SERVICE, name)
