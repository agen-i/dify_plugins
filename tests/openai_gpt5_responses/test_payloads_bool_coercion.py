from __future__ import annotations

import json

import pytest

from app.openai_gpt5_responses.internal.payloads import build_responses_request


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        (1, True),
        (0, False),
    ],
)
def test_enable_stream_accepts_bool_like_values(
    raw: object, expected: bool
) -> None:
    payload = build_responses_request(
        model="gpt-5.2",
        user_input="hello",
        model_parameters={"enable_stream": raw},
        tools=[],
        stream=True,
    )

    assert payload["stream"] is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        (1, True),
        (0, False),
    ],
)
def test_parallel_tool_calls_accepts_bool_like_values(
    raw: object, expected: bool
) -> None:
    payload = build_responses_request(
        model="gpt-5.2",
        user_input="hello",
        model_parameters={"parallel_tool_calls": raw},
        tools=[],
        stream=False,
    )

    assert payload["parallel_tool_calls"] is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        (1, True),
        (0, False),
    ],
)
def test_json_schema_strict_accepts_bool_like_values(
    raw: object, expected: bool
) -> None:
    schema = {
        "name": "answer",
        "schema": {"type": "object"},
        "strict": raw,
    }
    payload = build_responses_request(
        model="gpt-5.2",
        user_input="hello",
        model_parameters={
            "response_format": "json_schema",
            "json_schema": json.dumps(schema),
        },
        tools=[],
        stream=False,
    )

    assert payload["text"]["format"]["strict"] is expected


@pytest.mark.parametrize(
    ("field", "raw"),
    [
        ("enable_stream", "yes"),
        ("parallel_tool_calls", "no"),
    ],
)
def test_invalid_bool_text_raises_value_error(field: str, raw: object) -> None:
    with pytest.raises(ValueError):
        build_responses_request(
            model="gpt-5.2",
            user_input="hello",
            model_parameters={field: raw},
            tools=[],
            stream=False,
        )


def test_invalid_json_schema_strict_raises_value_error() -> None:
    with pytest.raises(ValueError):
        build_responses_request(
            model="gpt-5.2",
            user_input="hello",
            model_parameters={
                "response_format": "json_schema",
                "json_schema": (
                    '{"name":"answer","schema":{"type":"object"},"strict":"invalid"}'
                ),
            },
            tools=[],
            stream=False,
        )
