from __future__ import annotations


def should_continue(
    *, iteration: int, maximum_iterations: int, has_tool_call: bool
) -> bool:
    if maximum_iterations <= 0:
        return False
    if iteration >= maximum_iterations:
        return False
    return bool(has_tool_call)
