import asyncio

from mail_mcp.config import AccountConfig
from mail_mcp.server import create_server

WRITE_WORDS = ("send", "reply", "archive", "delete", "move", "forward", "trash")


def test_no_write_tool_exposed_by_default():
    server = create_server({"a": AccountConfig(name="a", backend="imap")})
    names = [t.name for t in asyncio.run(server.list_tools())]
    assert names, "aucun outil exposé"
    assert not [n for n in names if any(w in n for w in WRITE_WORDS)]
