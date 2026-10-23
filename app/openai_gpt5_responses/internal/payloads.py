from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

_ALLOWED_RESPONSE_FORMATS = {"text", "json_schema"}
_ALLOWED_VERBOSITY = {"low", "medium", "high"}
_ALLOWED_REASONING_EFFORT = {
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
}
_ALLOWED_REASONING_SUMMARY = {"auto", "concise", "detailed"}


def coerce_bool_strict(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise ValueError(f"{field_name} must be a boolean-like value")

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
        raise ValueError(f"{field_name} must be a boolean-like value")

    raise ValueError(f"{field_name} must be a boolean-like value")


def _parse_json_schema(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    if not isinstance(parsed, Mapping):
        raise ValueError("json_schema must be a JSON object")

    schema_name = str(parsed.get("name") or "structured_output")
    schema_body = parsed.get("schema")
    if not isinstance(schema_body, Mapping):
        raise ValueError(
            "json_schema must include an object field named 'schema'"
        )

    return {
        "type": "json_schema",
        "name": schema_name,
        "schema": dict(schema_body),
        "strict": coerce_bool_strict(
            parsed.get("strict", True), field_name="json_schema.strict"
        ),
    }


def _tool_to_response_tool(tool: Any) -> dict[str, Any]:
    if isinstance(tool, Mapping):
        name = str(tool.get("name") or "").strip()
        description = str(tool.get("description") or "")
        parameters = tool.get("parameters") or {
            "type": "object",
            "properties": {},
        }
        if not name:
            raise ValueError("tool name is required")
        return {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": parameters,
        }

    name = str(getattr(tool, "name", "")).strip()
    description = str(getattr(tool, "description", "") or "")
    parameters = getattr(tool, "parameters", None) or {
        "type": "object",
        "properties": {},
    }
    if not name:
        raise ValueError("tool name is required")
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": parameters,
    }


def build_responses_request(
    *,
    model: str,
    user_input: Any,
    model_parameters: Mapping[str, Any],
    tools: list[Any] | None,
    stream: bool,
) -> dict[str, Any]:
    params = dict(model_parameters)
    payload: dict[str, Any] = {
        "model": model,
        "input": user_input,
    }

    effective_stream = (
        coerce_bool_strict(
            params.pop("enable_stream", True), field_name="enable_stream"
        )
        and stream
    )
    payload["stream"] = effective_stream

    max_output_tokens = params.get("max_output_tokens")
    if max_output_tokens is not None:
        payload["max_output_tokens"] = int(max_output_tokens)

    reasoning_payload: dict[str, Any] = {}
    reasoning_effort = params.get("reasoning_effort")
    if reasoning_effort is not None:
        reasoning_effort = str(reasoning_effort)
        if reasoning_effort not in _ALLOWED_REASONING_EFFORT:
            raise ValueError(
                f"unsupported reasoning_effort: {reasoning_effort}"
            )
        reasoning_payload["effort"] = reasoning_effort

    reasoning_summary = params.get("reasoning_summary")
    if reasoning_summary is not None:
        reasoning_summary = str(reasoning_summary)
        if reasoning_summary not in _ALLOWED_REASONING_SUMMARY:
            raise ValueError(
                f"unsupported reasoning_summary: {reasoning_summary}"
            )
        reasoning_payload["summary"] = reasoning_summary

    if reasoning_payload:
        payload["reasoning"] = reasoning_payload

    response_format = str(params.get("response_format") or "text")
    if response_format not in _ALLOWED_RESPONSE_FORMATS:
        raise ValueError(f"unsupported response_format: {response_format}")

    text_block: dict[str, Any] = {"format": {"type": "text"}}
    if response_format == "json_schema":
        raw_schema = params.get("json_schema")
        if raw_schema is None or str(raw_schema).strip() == "":
            raise ValueError(
                "json_schema is required when response_format is json_schema"
            )
        text_block["format"] = _parse_json_schema(str(raw_schema))

    verbosity = params.get("verbosity")
    if verbosity is not None:
        verbosity = str(verbosity)
        if verbosity not in _ALLOWED_VERBOSITY:
            raise ValueError(f"unsupported verbosity: {verbosity}")
        text_block["verbosity"] = verbosity

    payload["text"] = text_block

    if "tool_choice" in params:
        payload["tool_choice"] = params["tool_choice"]

    if "parallel_tool_calls" in params:
        payload["parallel_tool_calls"] = coerce_bool_strict(
            params["parallel_tool_calls"], field_name="parallel_tool_calls"
        )

    tool_defs = [_tool_to_response_tool(tool) for tool in (tools or [])]
    if tool_defs:
        payload["tools"] = tool_defs

    return payload
