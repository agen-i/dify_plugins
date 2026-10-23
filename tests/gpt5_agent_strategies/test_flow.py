from __future__ import annotations

from types import SimpleNamespace

from app.gpt5_agent_strategies.internal.flow import (
    build_round_prompt_messages,
    extract_blocking_tool_calls,
    extract_stream_tool_calls,
    should_emit_response_text,
)


def test_build_round_prompt_messages_is_not_mutating_input_history() -> None:
    history = ["history-1", "history-2"]

    combined = build_round_prompt_messages(
        history_prompt_messages=history,
        system_message="system",
        user_message="user",
    )

    assert combined == ["system", "history-1", "history-2", "user"]
    assert history == ["history-1", "history-2"]


def test_should_emit_response_text_allows_intermediate_when_enabled() -> None:
    assert should_emit_response_text(
        has_tool_calls=True,
        iteration_step=1,
        max_iteration_steps=3,
        emit_intermediate_thoughts=True,
    )


def test_should_emit_response_text_suppresses_when_disabled_and_not_final() -> (
    None
):
    assert not should_emit_response_text(
        has_tool_calls=True,
        iteration_step=1,
        max_iteration_steps=3,
        emit_intermediate_thoughts=False,
    )


def test_should_emit_response_text_allows_final_iteration_when_disabled() -> (
    None
):
    assert should_emit_response_text(
        has_tool_calls=True,
        iteration_step=3,
        max_iteration_steps=3,
        emit_intermediate_thoughts=False,
    )


def test_should_emit_response_text_allows_normal_text_only() -> None:
    assert should_emit_response_text(
        has_tool_calls=False, iteration_step=1, max_iteration_steps=3
    )


def test_extract_stream_tool_calls_handles_none_message() -> None:
    chunk = SimpleNamespace(delta=SimpleNamespace(message=None))
    assert extract_stream_tool_calls(chunk) == []


def test_extract_stream_tool_calls_reads_existing_calls() -> None:
    call = SimpleNamespace(id="call_1")
    chunk = SimpleNamespace(
        delta=SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))
    )

    assert extract_stream_tool_calls(chunk) == [call]


def test_extract_blocking_tool_calls_handles_none_message() -> None:
    result = SimpleNamespace(message=None)
    assert extract_blocking_tool_calls(result) == []


def test_extract_blocking_tool_calls_handles_empty_tool_calls() -> None:
    result = SimpleNamespace(message=SimpleNamespace(tool_calls=[]))
    assert extract_blocking_tool_calls(result) == []
