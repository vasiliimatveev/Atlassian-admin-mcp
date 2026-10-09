"""End-to-end: start the real CLI over stdio and talk MCP to it."""

import os
import subprocess
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from jira_dc_analyst.__main__ import main


def test_list_toolsets(capsys):
    main(["--list-toolsets"])
    out = capsys.readouterr().out
    assert "* admin" in out
    assert "  jmwe" in out


def test_missing_config_exits_with_message():
    env = {k: v for k, v in os.environ.items() if not k.startswith("JIRA_")}
    proc = subprocess.run(
        [sys.executable, "-m", "jira_dc_analyst"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert "JIRA_URL is required" in proc.stderr
    assert proc.stdout == ""  # stdout is reserved for the protocol


async def test_stdio_server_lists_tools():
    env = {
        **os.environ,
        "JIRA_URL": "https://jira.invalid",
        "JIRA_PERSONAL_TOKEN": "x",
        "TOOLSETS": "logs",
    }
    transport = StdioTransport(command=sys.executable, args=["-m", "jira_dc_analyst"], env=env)
    async with Client(transport) as c:
        names = sorted(t.name for t in await c.list_tools())
    assert names == ["jira_analyst_status", "jira_get_audit_log", "jira_get_system_log"]
