from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolArgumentsParseResult:
    ok: bool
    args: dict[str, Any]
    error: str | None = None


def parse_tool_arguments(arguments: Any) -> ToolArgumentsParseResult:
    if arguments == "":
        return ToolArgumentsParseResult(ok=True, args={})

    if not isinstance(arguments, str):
        return ToolArgumentsParseResult(
            ok=False,
            args={},
            error="tool arguments must be a JSON object string",
        )

    try:
        parsed = json.loads(arguments)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ToolArgumentsParseResult(
            ok=False,
            args={},
            error="tool arguments must be valid JSON object",
        )

    if not isinstance(parsed, Mapping):
        return ToolArgumentsParseResult(
            ok=False,
            args={},
            error="tool arguments must be a JSON object",
        )

    return ToolArgumentsParseResult(ok=True, args=dict(parsed))


def resolve_tool_instance(
    tool_instances: Mapping[str, Any], tool_name: str
) -> Any | None:
    return tool_instances.get(tool_name)
