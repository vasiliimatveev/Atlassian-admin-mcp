import json

import pytest

from jira_dc_analyst.tools.issue_inspect import is_image_attachment, looks_like_text
from jira_dc_analyst.util import InvalidArgument, error_json, seg, set_json_indent, to_json


@pytest.mark.parametrize(
    "value, expected",
    [
        ("HR-1", "HR-1"),
        (10001, "10001"),
        ("../../plugins/1.0/", "..%2F..%2Fplugins%2F1.0%2F"),
        ("a b?c#d", "a%20b%3Fc%23d"),
        ("com.example.plugin", "com.example.plugin"),
    ],
)
def test_seg_encodes_one_segment(value, expected):
    assert seg(value) == expected


@pytest.mark.parametrize("value", ["", " ", ".", ".."])
def test_seg_rejects_empty_and_dot_segments(value):
    with pytest.raises(InvalidArgument):
        seg(value)


def test_to_json_is_compact_by_default_and_keeps_unicode():
    assert to_json({"a": [1, "ё"]}) == '{"a":[1,"ё"]}'


def test_to_json_indent_is_configurable():
    set_json_indent(2)
    try:
        assert to_json({"a": 1}) == '{\n  "a": 1\n}'
    finally:
        set_json_indent(None)


def test_error_json_puts_error_first_and_drops_none():
    text = error_json("boom", status=None, hint="h")
    assert text.startswith('{"error"')
    assert json.loads(text) == {"error": "boom", "hint": "h"}


@pytest.mark.parametrize(
    "mime, name, expected",
    [
        ("image/png", "x", (True, "image/png")),
        ("", "shot.JPG", (True, "image/jpeg")),
        ("application/octet-stream", "a.webp", (True, "image/webp")),
        ("application/pdf", "a.png", (False, "application/pdf")),
        ("", "notes", (False, "application/octet-stream")),
    ],
)
def test_is_image_attachment(mime, name, expected):
    assert is_image_attachment(mime, name) == expected


def test_looks_like_text():
    assert looks_like_text("text/plain", "x")
    assert looks_like_text("application/octet-stream", "build.LOG")
    assert not looks_like_text("application/pdf", "a.pdf")
