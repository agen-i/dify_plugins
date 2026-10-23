from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

try:
    from app.gpt5_agent_strategies.prompt.template import (
        CONTEXT_GATHERING_POLICY,
        PERSISTENCE_POLICY,
        TOOL_PREAMBLE_POLICY,
        UNCERTAINTY_POLICY,
    )
except ModuleNotFoundError:
    from prompt.template import (
        CONTEXT_GATHERING_POLICY,
        PERSISTENCE_POLICY,
        TOOL_PREAMBLE_POLICY,
        UNCERTAINTY_POLICY,
    )


_POLICY_TAG_BY_KEY: dict[str, str] = {
    "persistence_policy": "persistence",
    "context_gathering_policy": "context_gathering",
    "uncertainty_policy": "uncertainty_and_ambiguity",
    "tool_preamble_policy": "tool_preamble",
}


def build_system_instruction(
    base_instruction: str,
    prompt_policy_overrides: str | None = None,
) -> str:
    instruction = (base_instruction or "").strip()
    if not instruction:
        instruction = "You are a helpful GPT-5 agent."

    policies = _resolve_policies(prompt_policy_overrides)
    blocks = [
        instruction,
        policies["persistence_policy"],
        policies["context_gathering_policy"],
        policies["uncertainty_policy"],
        policies["tool_preamble_policy"],
        policies.get("extra_policy", ""),
    ]
    return "\n\n".join(block for block in blocks if block.strip())


def _resolve_policies(
    prompt_policy_overrides: str | None,
) -> dict[str, str]:
    policies = {
        "persistence_policy": PERSISTENCE_POLICY,
        "context_gathering_policy": CONTEXT_GATHERING_POLICY,
        "uncertainty_policy": UNCERTAINTY_POLICY,
        "tool_preamble_policy": TOOL_PREAMBLE_POLICY,
        "extra_policy": "",
    }

    overrides = _parse_policy_overrides(prompt_policy_overrides)
    for key in policies:
        value = overrides.get(key)
        if not value:
            continue
        policies[key] = value

    return policies


def _parse_policy_overrides(
    prompt_policy_overrides: str | None,
) -> dict[str, str]:
    text = (prompt_policy_overrides or "").strip()
    if not text:
        return {}

    parsed = _try_parse_json_mapping(text)
    if parsed is None:
        return {"extra_policy": text}

    allowed_keys = {
        "persistence_policy",
        "context_gathering_policy",
        "uncertainty_policy",
        "tool_preamble_policy",
        "extra_policy",
    }
    overrides: dict[str, str] = {}
    for key in allowed_keys:
        value = parsed.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            overrides[key] = _normalize_policy_override(key, normalized)

    return overrides


def _normalize_policy_override(key: str, value: str) -> str:
    tag_name = _POLICY_TAG_BY_KEY.get(key)
    if not tag_name:
        return value
    return _ensure_wrapped_policy_tag(value, tag_name)


def _ensure_wrapped_policy_tag(value: str, tag_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if _is_policy_tag_wrapped(normalized, tag_name):
        return normalized
    return f"<{tag_name}>\n{normalized}\n</{tag_name}>"


def _is_policy_tag_wrapped(value: str, tag_name: str) -> bool:
    opening = f"<{tag_name}>"
    closing = f"</{tag_name}>"
    return value.startswith(opening) and value.endswith(closing)


def _try_parse_json_mapping(text: str) -> Mapping[str, Any] | None:
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return None

    if isinstance(loaded, Mapping):
        return loaded
    return None
