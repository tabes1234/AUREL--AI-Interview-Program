"""方舟 JSON 解析的健壮性测试。"""

import pytest

from app.services.ark_client import ArkError, parse_json_output


def test_parse_plain_json() -> None:
    assert parse_json_output('{"a": 1}') == {"a": 1}


def test_parse_markdown_wrapped_json() -> None:
    raw = '```json\n{"a": [1, 2]}\n```'
    assert parse_json_output(raw) == {"a": [1, 2]}


def test_parse_json_with_leading_text() -> None:
    raw = '好的，以下是结果：{"a": "b"}'
    assert parse_json_output(raw) == {"a": "b"}


def test_parse_invalid_json_raises() -> None:
    with pytest.raises(ArkError):
        parse_json_output("这不是 JSON")


def test_parse_non_object_raises() -> None:
    with pytest.raises(ArkError):
        parse_json_output('["数组不是对象"]')
