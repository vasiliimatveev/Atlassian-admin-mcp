import pytest

from atlassian_admin_mcp.jql import (
    GuardDenied,
    combine,
    parse_issue_ref,
    split_order_by,
    validate_guard,
)

G = "project = SOS"


@pytest.mark.parametrize(
    "jql, expected",
    [
        ("", "(project = SOS)"),
        ("status = Open", "(project = SOS) AND (status = Open)"),
        (
            "status = Open ORDER BY created DESC, key",
            "(project = SOS) AND (status = Open) ORDER BY created DESC, key",
        ),
        ("ORDER BY rank", "(project = SOS) ORDER BY rank"),
        ('summary ~ "a) OR (b"', '(project = SOS) AND (summary ~ "a) OR (b")'),
        ('summary ~ "order by x"', '(project = SOS) AND (summary ~ "order by x")'),
        (
            "(a = 1 OR b = 2) order by cf[10010] asc",
            "(project = SOS) AND ((a = 1 OR b = 2)) order by cf[10010] asc",
        ),
        ('summary ~ "say \\"hi\\" )"', '(project = SOS) AND (summary ~ "say \\"hi\\" )")'),
    ],
)
def test_combine_wraps_user_jql_and_keeps_order_by(jql, expected):
    assert combine(G, jql) == expected


@pytest.mark.parametrize(
    "jql",
    [
        "project = SOS) OR (project = ABC",  # classic break-out
        "project = ABC) OR (1 = 1",
        "(project = ABC",
        'summary ~ "unterminated',
        "summary ~ 'x\\",
        "status = Open ORDER BY key OR project = ABC",  # condition after ORDER BY
        "status = Open ORDER BY key, project = ABC",
        "ORDER BY key ORDER BY rank",
    ],
)
def test_injection_attempts_are_denied(jql):
    with pytest.raises(GuardDenied):
        combine(G, jql)


@pytest.mark.parametrize("guard", ["", "   ", "project = A ORDER BY key", "project = A)"])
def test_bad_guard_is_denied(guard):
    with pytest.raises(GuardDenied):
        validate_guard(guard)


def test_split_order_by_ignores_masked_text():
    assert split_order_by('text ~ "ORDER BY" AND x = 1') == ('text ~ "ORDER BY" AND x = 1', "")
    assert split_order_by("border = 1") == ("border = 1", "")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("SOS-1", "SOS-1"),
        ("sos-1", "SOS-1"),  # Jira DC matches keys case-insensitively
        ("  abc-2 ", "ABC-2"),
        ("SOS%2D1", "SOS-1"),  # Jira decodes the path
        ("sOs_X-12", "SOS_X-12"),
        ("10001", "10001"),
    ],
)
def test_issue_refs_are_normalised(raw, expected):
    assert parse_issue_ref(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "SOS-0",
        "SOS-01",
        "0",
        "SOS",
        "SOS-1 OR project = ABC",
        "SOS-1,ABC-2",
        "SOS-1)",
        "%2553OS-1",  # double encoding
        "createmeta",
        "1-SOS",
        "SOS-1;x",
    ],
)
def test_anything_but_a_key_or_id_is_denied(raw):
    with pytest.raises(GuardDenied):
        parse_issue_ref(raw)
