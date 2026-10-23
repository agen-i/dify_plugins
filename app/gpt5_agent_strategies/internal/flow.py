from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def build_round_prompt_messages(
    *,
    history_prompt_messages: Sequence[Any],
    system_message: Any,
    user_message: Any,
) -> list[Any]:
    return [system_message, *list(history_prompt_messages), user_message]


def should_emit_response_text(
    *,
    has_tool_calls: bool,
    iteration_step: int,
    max_iteration_steps: int,
    emit_intermediate_thoughts: bool = True,
) -> bool:
    if not has_tool_calls:
        return True
    if emit_intermediate_thoughts:
        return True
    return iteration_step >= max_iteration_steps


def extract_stream_tool_calls(llm_result_chunk: Any) -> list[Any]:
    delta = getattr(llm_result_chunk, "delta", None)
    message = getattr(delta, "message", None)
    if message is None:
        return []

    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        return []

    return list(tool_calls)


def extract_blocking_tool_calls(llm_result: Any) -> list[Any]:
    message = getattr(llm_result, "message", None)
    if message is None:
        return []

    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        return []

    return list(tool_calls)
