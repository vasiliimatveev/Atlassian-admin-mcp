import pytest

from atlassian_admin_mcp.config import DEFAULT_SR_PATH, ConfigError, Settings
from atlassian_admin_mcp.toolsets import TOOLSETS, resolve_toolsets

BASE_ENV = {"JIRA_URL": "https://jira.example.com/", "JIRA_PERSONAL_TOKEN": "t"}


def test_minimal_env_uses_defaults():
    s = Settings.from_env(BASE_ENV)
    assert s.url == "https://jira.example.com"
    assert s.personal_token == "t"
    assert s.sr_path == DEFAULT_SR_PATH
    assert s.ssl_verify is True
    assert s.cache_ttl == 120
    assert s.json_indent is None


def test_basic_auth_accepts_api_token_or_password():
    s = Settings.from_env({"JIRA_URL": "https://j", "JIRA_USERNAME": "u", "JIRA_PASSWORD": "p"})
    assert (s.username, s.password, s.personal_token) == ("u", "p", None)


@pytest.mark.parametrize(
    "env, message",
    [
        ({}, "JIRA_URL is required"),
        ({"JIRA_URL": "jira.example.com", "JIRA_PERSONAL_TOKEN": "t"}, "absolute http"),
        ({"JIRA_URL": "https://j"}, "JIRA_PERSONAL_TOKEN"),
        ({**BASE_ENV, "JIRA_ADMIN_CACHE_TTL": "abc"}, "integer"),
        ({**BASE_ENV, "JIRA_ADMIN_MAX_CONCURRENCY": "0"}, ">= 1"),
        ({**BASE_ENV, "JIRA_ADMIN_TIMEOUT": "-1"}, "> 0"),
    ],
)
def test_invalid_env_is_rejected(env, message):
    with pytest.raises(ConfigError, match=message):
        Settings.from_env(env)


@pytest.mark.parametrize(
    "raw, expected",
    [("false", False), ("0", False), ("true", True), ("", True), ("/etc/ca.pem", "/etc/ca.pem")],
)
def test_ssl_verify_accepts_bool_or_ca_bundle(raw, expected):
    assert Settings.from_env({**BASE_ENV, "JIRA_SSL_VERIFY": raw}).ssl_verify == expected


def test_sr_path_gets_leading_slash_and_timeout_falls_back():
    s = Settings.from_env({**BASE_ENV, "JIRA_ADMIN_SR_PATH": "rest/custom/x", "JIRA_TIMEOUT": "12"})
    assert s.sr_path == "/rest/custom/x"
    assert s.timeout == 12.0


def test_default_toolsets():
    assert resolve_toolsets("") == {n for n, t in TOOLSETS.items() if t.default}
    assert resolve_toolsets("default") == resolve_toolsets("")


def test_all_case_insensitive_and_unknown(caplog):
    assert resolve_toolsets("all") == set(TOOLSETS)
    assert resolve_toolsets("jmwe, SLA") == {"jmwe", "sla"}
    assert resolve_toolsets("nope,jmwe") == {"jmwe"}
    assert "nope" in caplog.text


def test_only_unknown_toolsets_fail_closed():
    assert resolve_toolsets("nope") == set()
