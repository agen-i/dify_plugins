from __future__ import annotations

import pytest

from app.openai_gpt5_responses.internal.payloads import (
    build_responses_request,
)


def test_build_responses_request_maps_reasoning_and_verbosity() -> None:
    payload = build_responses_request(
        model="gpt-5.2",
        user_input="hello",
        model_parameters={
            "max_output_tokens": 1024,
            "reasoning_effort": "medium",
            "reasoning_summary": "concise",
            "verbosity": "high",
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        },
        tools=[],
        stream=False,
    )

    assert payload["model"] == "gpt-5.2"
    assert payload["input"] == "hello"
    assert payload["max_output_tokens"] == 1024
    assert payload["reasoning"]["effort"] == "medium"
    assert payload["reasoning"]["summary"] == "concise"
    assert payload["text"]["verbosity"] == "high"
    assert payload["tool_choice"] == "auto"
    assert payload["parallel_tool_calls"] is True


def test_build_responses_request_json_schema_mode() -> None:
    payload = build_responses_request(
        model="gpt-5.2",
        user_input="hello",
        model_parameters={
            "response_format": "json_schema",
            "json_schema": '{"name":"answer","schema":{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"]}}',
        },
        tools=[],
        stream=False,
    )

    text_format = payload["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["name"] == "answer"


def test_build_responses_request_requires_json_schema_if_requested() -> None:
    with pytest.raises(ValueError):
        build_responses_request(
            model="gpt-5.2",
            user_input="hello",
            model_parameters={"response_format": "json_schema"},
            tools=[],
            stream=False,
        )


def test_build_responses_request_rejects_unsupported_reasoning_summary() -> (
    None
):
    with pytest.raises(ValueError, match="unsupported reasoning_summary"):
        build_responses_request(
            model="gpt-5.2",
            user_input="hello",
            model_parameters={"reasoning_summary": "verbose"},
            tools=[],
            stream=False,
        )
