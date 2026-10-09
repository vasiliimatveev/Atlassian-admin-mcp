"""Static consistency checks between the Python tools and admin_analyst.groovy.

The Groovy file cannot run outside Jira, but the contract between the two
sides — action names and endpoint path — can be checked here.
"""

import re
from pathlib import Path

from jira_dc_analyst.config import DEFAULT_SR_PATH

ROOT = Path(__file__).resolve().parents[1]
GROOVY = (ROOT / "groovy" / "admin_analyst.groovy").read_text()
PY_SOURCES = "\n".join(p.read_text() for p in (ROOT / "src" / "jira_dc_analyst").rglob("*.py"))


def _groovy_actions() -> set[str]:
    return set(re.findall(r'case\s+"([a-z_]+)"\s*:', GROOVY))


def _python_actions() -> set[str]:
    return set(re.findall(r'sr_action\(\s*"([a-z_]+)"', PY_SOURCES))


def test_every_python_action_exists_in_groovy():
    missing = _python_actions() - _groovy_actions()
    assert not missing, f"actions called from Python but missing in Groovy: {sorted(missing)}"


def test_endpoint_name_matches_default_path():
    name = DEFAULT_SR_PATH.rsplit("/", 1)[-1]
    assert re.search(rf"^{name}\(httpMethod:\s*\"GET\"", GROOVY, re.M)
    assert f"URL:    GET {DEFAULT_SR_PATH}?action=" in GROOVY


def test_endpoint_is_read_only_and_group_restricted():
    assert re.findall(r'httpMethod:\s*"(\w+)"', GROOVY) == ["GET"]
    assert "groups: ALLOWED_GROUPS" in GROOVY
    assert re.search(r'final List<String> ALLOWED_GROUPS = \["jira-administrators"\]', GROOVY)


def test_ping_and_unknown_action_contract():
    assert 'case "ping":' in GROOVY
    assert "endpointVersion: ENDPOINT_VERSION" in GROOVY
    default_branch = GROOVY.split("default:", 1)[1][:200]
    assert "badRequest(" in default_branch


def test_system_log_reads_from_the_end():
    body = GROOVY.split("def getSystemLog", 1)[1].split("\ndef ", 1)[0]
    assert "readLines" not in body
    assert "RandomAccessFile" in body
