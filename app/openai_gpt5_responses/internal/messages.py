from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from typing import Any


def _attr_or_key(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if hasattr(item, "data"):
                chunks.append(str(item.data))
            elif isinstance(item, Mapping):
                if "text" in item:
                    chunks.append(str(item["text"]))
                elif "data" in item:
                    chunks.append(str(item["data"]))
        return "\n".join(x for x in chunks if x)
    return str(content)


def _to_assistant_function_calls(message: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    tool_calls = _attr_or_key(message, "tool_calls", []) or []
    for tool_call in tool_calls:
        call_id = _attr_or_key(tool_call, "id", "")
        function = _attr_or_key(tool_call, "function", {})
        name = _attr_or_key(function, "name", "")
        arguments = _attr_or_key(function, "arguments", "{}")

        if isinstance(arguments, Mapping):
            arguments = json.dumps(arguments, ensure_ascii=False)

        call_id = str(call_id or "")
        name = str(name or "")
        if not call_id or not name:
            continue

        calls.append(
            {
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": str(arguments or "{}"),
            }
        )

    return calls


def _to_function_call_outputs(message: Any) -> list[dict[str, Any]]:
    call_id = str(_attr_or_key(message, "tool_call_id", "") or "")
    output_text = _content_to_text(_attr_or_key(message, "content", ""))
    if not call_id:
        return []
    return [
        {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output_text,
        }
    ]


def _normalize_role(raw_role: Any) -> str:
    if raw_role is None:
        return "user"

    if isinstance(raw_role, Enum):
        role = str(raw_role.value)
    else:
        role = str(raw_role).strip()

    if not role:
        return "user"

    if role.startswith("PromptMessageRole."):
        role = role.split(".", 1)[1]

    role = role.lower().strip()
    if role in {"user", "assistant", "system", "developer", "tool"}:
        return role

    return "user"


def prompt_messages_to_responses_input(
    prompt_messages: list[Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in prompt_messages:
        role = _normalize_role(_attr_or_key(message, "role", "user"))

        if role == "assistant":
            text = _content_to_text(_attr_or_key(message, "content", ""))
            if text:
                result.append({"role": "assistant", "content": text})
            result.extend(_to_assistant_function_calls(message))
            continue

        if role == "tool":
            result.extend(_to_function_call_outputs(message))
            continue

        text = _content_to_text(_attr_or_key(message, "content", ""))
        if not text:
            continue
        result.append(
            {
                "role": role,
                "content": [{"type": "input_text", "text": text}],
            }
        )

    return result


def extract_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text:
        return text

    output_items = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in output_items:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, Mapping):
            content = item.get("content")

        if not content:
            continue

        for part in content:
            part_type = getattr(part, "type", None)
            if part_type is None and isinstance(part, Mapping):
                part_type = part.get("type")

            if part_type == "output_text":
                part_text = getattr(part, "text", None)
                if part_text is None and isinstance(part, Mapping):
                    part_text = part.get("text")
                if part_text:
                    chunks.append(str(part_text))

    return "\n".join(chunks)


def extract_tool_calls(response: Any) -> list[dict[str, str]]:
    output_items = getattr(response, "output", None) or []
    calls: list[dict[str, str]] = []
    for item in output_items:
        item_type = getattr(item, "type", None)
        if item_type is None and isinstance(item, Mapping):
            item_type = item.get("type")
        if item_type != "function_call":
            continue

        call_id = getattr(item, "call_id", None)
        name = getattr(item, "name", None)
        arguments = getattr(item, "arguments", None)

        if isinstance(item, Mapping):
            call_id = call_id or item.get("call_id")
            name = name or item.get("name")
            arguments = arguments or item.get("arguments")

        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)

        calls.append(
            {
                "id": str(call_id or ""),
                "name": str(name or ""),
                "arguments": str(arguments or "{}"),
            }
        )

    return [call for call in calls if call["name"]]
