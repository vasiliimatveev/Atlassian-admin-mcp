"""Command-line entry point: ``jira-dc-analyst-mcp``."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from . import __version__
from .config import ConfigError, Settings
from .toolsets import TOOLSETS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="jira-dc-analyst-mcp",
        description="Read-only MCP server for Jira Data Center administrators.",
    )
    parser.add_argument("--transport", choices=("stdio", "http", "sse"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--toolsets", help="Overrides TOOLSETS, e.g. 'default,scriptrunner'")
    parser.add_argument("--list-toolsets", action="store_true", help="Print toolsets and exit")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if args.list_toolsets:
        for name, t in TOOLSETS.items():
            mark = "*" if t.default else " "
            print(f"{mark} {name:<15} {t.description}  [needs: {t.requires}]")
        print("\n* = enabled by default. Use TOOLSETS=all to enable everything.")
        return

    level = logging.WARNING - 10 * args.verbose
    logging.basicConfig(
        level=max(level, logging.DEBUG),
        stream=sys.stderr,  # stdout carries the MCP protocol on stdio
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    env = dict(os.environ)
    if args.toolsets is not None:
        env["TOOLSETS"] = args.toolsets
    try:
        settings = Settings.from_env(env)
    except ConfigError as exc:
        print(f"jira-dc-analyst-mcp: {exc}", file=sys.stderr)
        sys.exit(2)

    from .server import create_server

    server = create_server(settings)
    if args.transport == "stdio":
        server.run(show_banner=False)
    else:
        server.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
