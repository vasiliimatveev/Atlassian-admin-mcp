"""Read-only MCP server for Jira Data Center administrators."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("atlassian-admin-mcp")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "0.0.0"
