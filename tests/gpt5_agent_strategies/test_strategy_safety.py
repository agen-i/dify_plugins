from __future__ import annotations

import pytest

from app.gpt5_agent_strategies.internal.tooling import (
    ToolArgumentsParseResult,
    parse_tool_arguments,
    resolve_tool_instance,
)


def test_parse_tool_arguments_accepts_json_object() -> None:
    result = parse_tool_arguments('{"q":"hello","limit":3}')
    assert result == ToolArgumentsParseResult(
        ok=True, args={"q": "hello", "limit": 3}
    )


def test_parse_tool_arguments_accepts_empty_string_as_empty_object() -> None:
    result = parse_tool_arguments("")
    assert result == ToolArgumentsParseResult(ok=True, args={})


def test_parse_tool_arguments_handles_invalid_json() -> None:
    result = parse_tool_arguments("{broken-json")
    assert not result.ok
    assert result.args == {}
    assert result.error


def test_parse_tool_arguments_rejects_non_object_json() -> None:
    result = parse_tool_arguments('["a","b"]')
    assert not result.ok
    assert result.args == {}
    assert result.error


@pytest.mark.parametrize("raw", [{"q": "x"}, b'{"q":"x"}', None])
def test_parse_tool_arguments_rejects_non_string_payload(raw: object) -> None:
    result = parse_tool_arguments(raw)
    assert not result.ok
    assert result.args == {}
    assert result.error


def test_resolve_tool_instance_returns_none_when_missing() -> None:
    tools = {"known": object()}
    assert resolve_tool_instance(tools, "known") is tools["known"]
    assert resolve_tool_instance(tools, "missing") is None
