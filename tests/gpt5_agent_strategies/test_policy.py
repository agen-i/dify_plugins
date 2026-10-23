from __future__ import annotations

import json

from app.gpt5_agent_strategies.internal.loop import should_continue
from app.gpt5_agent_strategies.internal.policy import build_system_instruction


def test_build_system_instruction_contains_policy_sections() -> None:
    text = build_system_instruction(base_instruction="You are a coding agent")

    assert "<persistence>" in text
    assert "<context_gathering>" in text
    assert "<uncertainty_and_ambiguity>" in text


def test_build_system_instruction_appends_plain_text_overrides() -> None:
    override = "<runtime_policy>\n- Keep answers concise.\n</runtime_policy>"
    text = build_system_instruction(
        base_instruction="You are a coding agent",
        prompt_policy_overrides=override,
    )

    assert text.endswith(override)


def test_build_system_instruction_overrides_specific_policy_blocks() -> None:
    override = json.dumps(
        {
            "tool_preamble_policy": "- Think in <think> blocks before tools.",
            "extra_policy": "<extra_policy>\n- Stay deterministic.\n</extra_policy>",
        },
        ensure_ascii=False,
    )
    text = build_system_instruction(
        base_instruction="You are a coding agent",
        prompt_policy_overrides=override,
    )

    assert "Before calling tools, emit a short thought block" not in text
    assert "<tool_preamble>" in text
    assert "</tool_preamble>" in text
    assert "Think in <think> blocks before tools." in text
    assert "<extra_policy>" in text


def test_build_system_instruction_wraps_policy_tags_when_user_omits_tags() -> (
    None
):
    override = json.dumps(
        {
            "persistence_policy": "- continue",
            "context_gathering_policy": "- gather context",
            "uncertainty_policy": "- state assumptions",
        },
        ensure_ascii=False,
    )
    text = build_system_instruction(
        base_instruction="You are a coding agent",
        prompt_policy_overrides=override,
    )

    assert "<persistence>" in text and "</persistence>" in text
    assert "<context_gathering>" in text and "</context_gathering>" in text
    assert "<uncertainty_and_ambiguity>" in text
    assert "</uncertainty_and_ambiguity>" in text
    assert "- continue" in text
    assert "- gather context" in text
    assert "- state assumptions" in text


def test_build_system_instruction_does_not_double_wrap_existing_policy_tags() -> (
    None
):
    override = json.dumps(
        {
            "persistence_policy": (
                "<persistence>\n- continue to finish task\n</persistence>"
            )
        },
        ensure_ascii=False,
    )
    text = build_system_instruction(
        base_instruction="You are a coding agent",
        prompt_policy_overrides=override,
    )

    assert text.count("<persistence>") == 1
    assert text.count("</persistence>") == 1


def test_build_system_instruction_keeps_extra_policy_without_forced_tag() -> (
    None
):
    override = json.dumps(
        {
            "extra_policy": "- prefer deterministic outputs",
        },
        ensure_ascii=False,
    )
    text = build_system_instruction(
        base_instruction="You are a coding agent",
        prompt_policy_overrides=override,
    )

    assert "- prefer deterministic outputs" in text
    assert "<extra_policy>" not in text


def test_build_system_instruction_treats_invalid_json_as_plain_text() -> None:
    malformed = '{"tool_preamble_policy":"override"'
    text = build_system_instruction(
        base_instruction="You are a coding agent",
        prompt_policy_overrides=malformed,
    )

    assert text.endswith(malformed)


def test_build_system_instruction_ignores_unknown_json_keys() -> None:
    override = json.dumps(
        {
            "tool_preamble_policy": "- custom preamble",
            "unknown_policy": "- this should be ignored",
        },
        ensure_ascii=False,
    )
    text = build_system_instruction(
        base_instruction="You are a coding agent",
        prompt_policy_overrides=override,
    )

    assert "- custom preamble" in text
    assert "unknown_policy" not in text
    assert "this should be ignored" not in text


def test_should_continue_stops_at_max_iterations() -> None:
    assert should_continue(
        iteration=1, maximum_iterations=3, has_tool_call=True
    )
    assert not should_continue(
        iteration=3, maximum_iterations=3, has_tool_call=True
    )


def test_should_continue_stops_without_tool_call() -> None:
    assert not should_continue(
        iteration=1, maximum_iterations=5, has_tool_call=False
    )
