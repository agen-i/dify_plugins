from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.openai_gpt5_responses.internal.messages import (
    extract_output_text,
    extract_tool_calls,
    prompt_messages_to_responses_input,
)


@dataclass
class FakeFunction:
    name: str
    arguments: Any


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunction


@dataclass
class FakeMessage:
    role: str
    content: Any = ""
    tool_calls: list[FakeToolCall] | None = None
    tool_call_id: str | None = None


@dataclass
class FakeContentPart:
    data: str


def test_prompt_messages_keep_tool_call_context() -> None:
    assistant = FakeMessage(
        role="assistant",
        content="thinking",
        tool_calls=[
            FakeToolCall(
                id="call_1",
                function=FakeFunction(
                    name="lookup", arguments='{"q":"hello"}'
                ),
            )
        ],
    )
    tool = FakeMessage(
        role="tool", content="tool result", tool_call_id="call_1"
    )

    payload = prompt_messages_to_responses_input([assistant, tool])

    assert payload[0]["role"] == "assistant"
    assert payload[0]["content"] == "thinking"

    assert payload[1] == {
        "type": "function_call",
        "call_id": "call_1",
        "name": "lookup",
        "arguments": '{"q":"hello"}',
    }

    assert payload[2] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": "tool result",
    }


def test_prompt_messages_plain_user_content_is_still_input_text() -> None:
    user = FakeMessage(role="user", content="hello")
    payload = prompt_messages_to_responses_input([user])

    assert payload == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "hello"}],
        }
    ]


def test_prompt_messages_keep_empty_tool_output_with_call_id() -> None:
    tool = FakeMessage(role="tool", content="", tool_call_id="call_empty")

    payload = prompt_messages_to_responses_input([tool])

    assert payload == [
        {
            "type": "function_call_output",
            "call_id": "call_empty",
            "output": "",
        }
    ]


def test_prompt_messages_support_mixed_content_and_mapping_tool_arguments() -> (
    None
):
    assistant = FakeMessage(
        role="assistant",
        content=[
            FakeContentPart(data="line1"),
            {"text": "line2"},
            {"data": "line3"},
        ],
        tool_calls=[
            FakeToolCall(
                id="call_map",
                function=FakeFunction(name="lookup", arguments={"q": "x"}),
            )
        ],
    )

    payload = prompt_messages_to_responses_input([assistant])

    assert payload[0] == {
        "role": "assistant",
        "content": "line1\nline2\nline3",
    }
    assert payload[1]["type"] == "function_call"
    assert payload[1]["arguments"] == '{"q": "x"}'


def test_prompt_messages_skip_invalid_tool_call_without_id_or_name() -> None:
    assistant = FakeMessage(
        role="assistant",
        content="thought",
        tool_calls=[
            FakeToolCall(
                id="", function=FakeFunction(name="lookup", arguments="{}")
            ),
            FakeToolCall(
                id="call", function=FakeFunction(name="", arguments="{}")
            ),
        ],
    )

    payload = prompt_messages_to_responses_input([assistant])
    assert payload == [
        {
            "role": "assistant",
            "content": "thought",
        }
    ]


def test_prompt_messages_normalize_enum_role_to_openai_role() -> None:
    class PromptMessageRole(Enum):
        SYSTEM = "system"

    system = FakeMessage(role=PromptMessageRole.SYSTEM, content="policy")
    payload = prompt_messages_to_responses_input([system])

    assert payload == [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": "policy"}],
        }
    ]


def test_prompt_messages_normalize_prefixed_enum_string_role() -> None:
    system = FakeMessage(role="PromptMessageRole.SYSTEM", content="policy")
    payload = prompt_messages_to_responses_input([system])

    assert payload == [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": "policy"}],
        }
    ]


def test_extract_output_text_prefers_direct_output_text() -> None:
    response = FakeMessage(role="assistant", content="")
    response.output_text = "direct"
    response.output = [
        {
            "content": [
                {
                    "type": "output_text",
                    "text": "fallback",
                }
            ]
        }
    ]

    assert extract_output_text(response) == "direct"


def test_extract_output_text_reads_mapping_and_object_parts() -> None:
    part_obj = FakeMessage(role="assistant", content="")
    part_obj.type = "output_text"
    part_obj.text = "obj"
    response = FakeMessage(role="assistant", content="")
    response.output_text = None
    response.output = [
        {"content": [{"type": "output_text", "text": "map"}]},
        {"content": [part_obj]},
        {"content": [{"type": "summary_text", "text": "ignored"}]},
    ]

    assert extract_output_text(response) == "map\nobj"


def test_extract_tool_calls_accepts_mapping_and_object_items() -> None:
    obj_call = FakeMessage(role="assistant", content="")
    obj_call.type = "function_call"
    obj_call.call_id = "call_obj"
    obj_call.name = "obj_lookup"
    obj_call.arguments = {"q": "obj"}

    response = FakeMessage(role="assistant", content="")
    response.output = [
        {
            "type": "function_call",
            "call_id": "call_map",
            "name": "map_lookup",
            "arguments": {"q": "map"},
        },
        obj_call,
        {
            "type": "function_call",
            "call_id": "call_no_name",
            "name": "",
            "arguments": "{}",
        },
    ]

    assert extract_tool_calls(response) == [
        {
            "id": "call_map",
            "name": "map_lookup",
            "arguments": '{"q": "map"}',
        },
        {
            "id": "call_obj",
            "name": "obj_lookup",
            "arguments": '{"q": "obj"}',
        },
    ]
