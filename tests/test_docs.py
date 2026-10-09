"""Docs must match the code — tool counts drifted apart in the fork this came from."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_tools_md", ROOT / "scripts" / "gen_tools_md.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tools_md_is_up_to_date():
    assert (ROOT / "TOOLS.md").read_text() == _load_generator().render(), (
        "TOOLS.md is stale: run `uv run python scripts/gen_tools_md.py`"
    )


def test_readme_tool_count_matches_registry():
    readme = (ROOT / "README.md").read_text()
    tools_md = (ROOT / "TOOLS.md").read_text()
    total = int(re.search(r"\*\*(\d+) read-only tools", tools_md).group(1))
    counts = set(re.findall(r"(\d+) read-only tools", readme))
    assert counts == {str(total)}, f"README mentions {counts}, registry has {total}"


def test_env_example_lists_every_setting():
    env_example = (ROOT / ".env.example").read_text()
    config = (ROOT / "src" / "atlassian_admin_mcp" / "config.py").read_text()
    names = set(re.findall(r'"((?:JIRA|TOOLSETS)[A-Z_]*)"', config))
    missing = {n for n in names if n not in env_example}
    assert not missing, f".env.example misses {sorted(missing)}"
