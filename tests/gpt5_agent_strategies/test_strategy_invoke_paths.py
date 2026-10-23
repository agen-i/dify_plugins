from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import BaseModel, Field


def _install_strategy_dify_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    entities_agent_mod = types.ModuleType("dify_plugin.entities.agent")
    entities_model_mod = types.ModuleType("dify_plugin.entities.model")
    entities_model_llm_mod = types.ModuleType("dify_plugin.entities.model.llm")
    entities_model_message_mod = types.ModuleType(
        "dify_plugin.entities.model.message"
    )
    entities_tool_mod = types.ModuleType("dify_plugin.entities.tool")
    interfaces_agent_mod = types.ModuleType("dify_plugin.interfaces.agent")

    class AgentInvokeMessage(dict):
        pass

    class ModelFeature:
        STREAM_TOOL_CALL = "stream_tool_call"
        VISION = "vision"

    @dataclass
    class LLMModelConfig:
        data: dict[str, Any]

        def __init__(self, **kwargs: Any) -> None:
            self.data = kwargs

    @dataclass
    class LLMUsage:
        total_price: float = 0.0
        currency: str = ""
        total_tokens: int = 0
        prompt_tokens: int = 0
        prompt_unit_price: float = 0.0
        prompt_price_unit: float = 0.0
        prompt_price: float = 0.0
        completion_tokens: int = 0
        completion_unit_price: float = 0.0
        completion_price_unit: float = 0.0
        completion_price: float = 0.0
        latency: float = 0.0

    @dataclass
    class LLMResult:
        model: str
        prompt_messages: list[Any]
        message: Any
        usage: LLMUsage | None
        system_fingerprint: Any = None

    @dataclass
    class LLMResultChunkDelta:
        message: Any
        usage: LLMUsage | None = None
        index: int = 0
        finish_reason: str = "stop"

    @dataclass
    class LLMResultChunk:
        model: str
        prompt_messages: list[Any]
        delta: LLMResultChunkDelta
        system_fingerprint: Any = None

    @dataclass
    class PromptMessage:
        content: Any = ""

    class PromptMessageContentType:
        TEXT = "text"
        IMAGE = "image"

    @dataclass
    class SystemPromptMessage(PromptMessage):
        pass

    @dataclass
    class UserPromptMessage(PromptMessage):
        pass

    @dataclass
    class ToolPromptMessage(PromptMessage):
        tool_call_id: str = ""
        name: str = ""

    @dataclass
    class AssistantPromptMessage(PromptMessage):
        tool_calls: list[Any] = field(default_factory=list)

        @dataclass
        class ToolCall:
            @dataclass
            class ToolCallFunction:
                name: str
                arguments: str

            id: str
            type: str
            function: AssistantPromptMessage.ToolCallFunction

    class ToolProviderType(str):
        pass

    class ToolInvokeMessage:
        class LogMessage:
            class LogStatus:
                START = "start"

        class MessageType:
            TEXT = "text"
            LINK = "link"
            IMAGE_LINK = "image_link"
            IMAGE = "image"
            JSON = "json"
            BLOB = "blob"

        @dataclass
        class TextMessage:
            text: str

        @dataclass
        class JsonMessage:
            json_object: dict[str, Any]

        class RetrieverResourceMessage:
            @dataclass
            class RetrieverResource:
                content: str
                position: Any = None
                dataset_id: Any = None
                dataset_name: Any = None
                document_id: Any = None
                document_name: Any = None
                data_source_type: Any = None
                segment_id: Any = None
                retriever_from: Any = None
                score: Any = None
                hit_count: Any = None
                word_count: Any = None
                segment_position: Any = None
                index_node_hash: Any = None
                page: Any = None
                doc_metadata: Any = None

    class _ErrorMeta:
        def __init__(self, message: str) -> None:
            self._message = message

        def to_dict(self) -> dict[str, str]:
            return {"error": self._message}

    class ToolInvokeMeta:
        @staticmethod
        def error_instance(message: str) -> _ErrorMeta:
            return _ErrorMeta(message)

    class ToolIdentity(BaseModel):
        name: str
        provider: str = "provider"

    class ToolParameterOption(BaseModel):
        value: str

    class ToolParameter(BaseModel):
        name: str
        type: str = "string"
        options: list[ToolParameterOption] = Field(default_factory=list)

    class ToolEntity(BaseModel):
        identity: ToolIdentity
        parameters: list[ToolParameter] = Field(default_factory=list)
        runtime_parameters: dict[str, Any] = Field(default_factory=dict)
        provider_type: str = "builtin"

    class AgentModelEntity(BaseModel):
        features: list[str] = Field(default_factory=list)

    class AgentModelConfig(BaseModel):
        provider: str = "provider"
        model: str = "gpt-5.2"
        completion_params: dict[str, Any] = Field(default_factory=dict)
        history_prompt_messages: list[Any] = Field(default_factory=list)
        entity: AgentModelEntity | None = Field(
            default_factory=AgentModelEntity
        )

    class AgentStrategy:
        def _init_prompt_tools(
            self, tools: list[Any] | None
        ) -> list[Any]:  # noqa: ARG002
            return []

        def recalc_llm_max_tokens(
            self,
            entity: Any,
            prompt_messages: list[Any],
            completion_params: dict[str, Any],
        ) -> None:  # noqa: ARG002
            return None

        def create_log_message(self, **kwargs: Any) -> dict[str, Any]:
            return {"kind": "log", **kwargs}

        def finish_log_message(
            self,
            *,
            log: dict[str, Any],
            data: dict[str, Any],
            metadata: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "kind": "log_finish",
                "log": log,
                "data": data,
                "metadata": metadata,
            }

        def create_text_message(self, text: str) -> dict[str, Any]:
            return {"kind": "text", "text": text}

        def create_blob_message(
            self, blob: bytes, meta: dict[str, Any]
        ) -> dict[str, Any]:
            return {"kind": "blob", "blob": blob, "meta": meta}

        def create_json_message(
            self, payload: dict[str, Any]
        ) -> dict[str, Any]:
            return {"kind": "json", "payload": payload}

        def create_retriever_resource_message(
            self, *, retriever_resources: list[Any], context: str
        ) -> dict[str, Any]:
            return {
                "kind": "retriever",
                "retriever_resources": retriever_resources,
                "context": context,
            }

        def increase_usage(
            self, llm_usage: dict[str, Any], usage: Any
        ) -> None:
            llm_usage["usage"] = usage

        def update_prompt_message_tool(
            self, tool_instance: Any, prompt_tool: Any
        ) -> None:  # noqa: ARG002
            return None

    entities_agent_mod.AgentInvokeMessage = AgentInvokeMessage
    entities_model_mod.ModelFeature = ModelFeature
    entities_model_llm_mod.LLMModelConfig = LLMModelConfig
    entities_model_llm_mod.LLMResult = LLMResult
    entities_model_llm_mod.LLMResultChunk = LLMResultChunk
    entities_model_llm_mod.LLMResultChunkDelta = LLMResultChunkDelta
    entities_model_llm_mod.LLMUsage = LLMUsage
    entities_model_message_mod.AssistantPromptMessage = AssistantPromptMessage
    entities_model_message_mod.PromptMessage = PromptMessage
    entities_model_message_mod.PromptMessageContentType = (
        PromptMessageContentType
    )
    entities_model_message_mod.SystemPromptMessage = SystemPromptMessage
    entities_model_message_mod.ToolPromptMessage = ToolPromptMessage
    entities_model_message_mod.UserPromptMessage = UserPromptMessage
    entities_tool_mod.ToolInvokeMessage = ToolInvokeMessage
    entities_tool_mod.ToolProviderType = ToolProviderType
    interfaces_agent_mod.AgentModelConfig = AgentModelConfig
    interfaces_agent_mod.AgentModelEntity = AgentModelEntity
    interfaces_agent_mod.AgentStrategy = AgentStrategy
    interfaces_agent_mod.ToolEntity = ToolEntity
    interfaces_agent_mod.ToolInvokeMeta = ToolInvokeMeta

    monkeypatch.setitem(
        sys.modules, "dify_plugin.entities.agent", entities_agent_mod
    )
    monkeypatch.setitem(
        sys.modules, "dify_plugin.entities.model", entities_model_mod
    )
    monkeypatch.setitem(
        sys.modules, "dify_plugin.entities.model.llm", entities_model_llm_mod
    )
    monkeypatch.setitem(
        sys.modules,
        "dify_plugin.entities.model.message",
        entities_model_message_mod,
    )
    monkeypatch.setitem(
        sys.modules, "dify_plugin.entities.tool", entities_tool_mod
    )
    monkeypatch.setitem(
        sys.modules, "dify_plugin.interfaces.agent", interfaces_agent_mod
    )


class _SequenceLLM:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def invoke(self, **_: Any) -> Any:
        self.calls += 1
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


def _build_model_config(strategy_module: Any, *, stream: bool) -> Any:
    features = (
        [strategy_module.ModelFeature.STREAM_TOOL_CALL] if stream else []
    )
    interfaces_mod = sys.modules["dify_plugin.interfaces.agent"]
    entity = interfaces_mod.AgentModelEntity(features=features)
    return strategy_module.AgentModelConfig(
        provider="openai",
        model="gpt-5.2",
        completion_params={},
        history_prompt_messages=[],
        entity=entity,
    )


def _build_tool_entity(name: str = "lookup", **kwargs: Any) -> Any:
    interfaces_mod = sys.modules["dify_plugin.interfaces.agent"]
    payload = {
        "identity": {"name": name, "provider": "provider"},
        "parameters": [{"name": "q", "type": "string"}],
        "runtime_parameters": {},
        "provider_type": "builtin",
    }
    payload.update(kwargs)
    return interfaces_mod.ToolEntity(**payload)


@pytest.fixture
def strategy_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    _install_strategy_dify_stub(monkeypatch)
    sys.modules.pop(
        "app.gpt5_agent_strategies.strategies.gpt5_function_calling", None
    )
    importlib.invalidate_caches()
    return importlib.import_module(
        "app.gpt5_agent_strategies.strategies.gpt5_function_calling"
    )


def test_invoke_blocking_result_message_none_is_safe(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=None,
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [],
                "maximum_iterations": 1,
            }
        )
    )

    assert llm.calls == 1
    assert any(m.get("kind") == "json" for m in messages)


def test_invoke_blocking_tool_not_found_path(strategy_module: Any) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_1",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="thinking",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [],
                "maximum_iterations": 1,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    assert "there is not a tool named lookup" in "\n".join(text_messages)


def test_invoke_streaming_plain_text_path(strategy_module: Any) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="stream hello",
                tool_calls=[],
            ),
            usage=None,
        ),
    )

    def _stream() -> Any:
        yield chunk

    llm = _SequenceLLM([_stream()])
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=True),
                "tools": [],
                "maximum_iterations": 1,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    assert "stream hello" in text_messages


def test_invoke_applies_prompt_policy_overrides_to_system_prompt(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="answer",
            tool_calls=[],
        ),
        usage=None,
    )

    class _CaptureLLM:
        def __init__(self, response: Any) -> None:
            self.response = response
            self.last_kwargs: dict[str, Any] = {}

        def invoke(self, **kwargs: Any) -> Any:
            self.last_kwargs = kwargs
            return self.response

    llm = _CaptureLLM(llm_result)
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    _ = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "You are a coding agent",
                "prompt_policy_overrides": (
                    '{"tool_preamble_policy":"<tool_preamble>\\n'
                    '- custom preamble\\n</tool_preamble>"}'
                ),
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [],
                "maximum_iterations": 1,
            }
        )
    )

    prompt_messages = llm.last_kwargs["prompt_messages"]
    system_message = prompt_messages[0]
    system_prompt_text = str(getattr(system_message, "content", ""))
    assert "- custom preamble" in system_prompt_text
    assert "Before calling tools, emit a short thought block" not in (
        system_prompt_text
    )


@pytest.mark.parametrize(
    ("requested_timeout", "expected_timeout"),
    [(30, 60), (1200, 1200), (9999, 1800)],
)
def test_invoke_updates_session_invocation_timeout(
    strategy_module: Any,
    requested_timeout: int,
    expected_timeout: int,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="answer",
            tool_calls=[],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    strategy.session = types.SimpleNamespace(
        max_invocation_timeout=250,
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    _ = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [],
                "maximum_iterations": 1,
                "invocation_timeout_seconds": requested_timeout,
            }
        )
    )

    assert strategy.session.max_invocation_timeout == expected_timeout


def test_invoke_streaming_plain_text_emits_each_chunk(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    first_chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="stream ",
                tool_calls=[],
            ),
            usage=None,
        ),
    )
    second_chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="hello",
                tool_calls=[],
            ),
            usage=None,
        ),
    )

    def _stream() -> Any:
        yield first_chunk
        yield second_chunk

    llm = _SequenceLLM([_stream()])
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=True),
                "tools": [],
                "maximum_iterations": 1,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    assert text_messages == ["stream hello"]


def test_invoke_streaming_hides_think_blocks_when_disabled_but_keeps_internal_response(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    first_chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="<think>内部で計画を立てます。",
                tool_calls=[],
            ),
            usage=None,
        ),
    )
    second_chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="次に調査します。</think>ユーザー向け回答です。",
                tool_calls=[],
            ),
            usage=None,
        ),
    )

    def _stream() -> Any:
        yield first_chunk
        yield second_chunk

    llm = _SequenceLLM([_stream()])
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=True),
                "tools": [],
                "maximum_iterations": 1,
                "emit_intermediate_thoughts": False,
            }
        )
    )

    rendered = "".join(
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    )
    assert "<think>" not in rendered
    assert "</think>" not in rendered
    assert "内部で計画を立てます" not in rendered
    assert "次に調査します" not in rendered
    assert "ユーザー向け回答です。" in rendered

    round_log_finishes = [
        m
        for m in messages
        if isinstance(m, dict)
        and m.get("kind") == "log_finish"
        and isinstance(m.get("data"), dict)
        and isinstance(m["data"].get("output_summary"), dict)
        and "llm_response_chars" in m["data"]["output_summary"]
    ]
    assert round_log_finishes
    assert "output" not in round_log_finishes[0]["data"]
    assert (
        round_log_finishes[0]["data"]["output_summary"]["llm_response_chars"]
        > 0
    )


def test_invoke_streaming_does_not_duplicate_emitted_thought_with_late_tool_call(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_late_stream_tool",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    thought_chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="<think>\nsearch plan\n</think>",
                tool_calls=[],
            ),
            usage=None,
        ),
    )
    tool_call_chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="",
                tool_calls=[tool_call],
            ),
            usage=None,
        ),
    )

    def _stream() -> Any:
        yield thought_chunk
        yield tool_call_chunk

    llm = _SequenceLLM([_stream()])
    tool_text = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.TEXT,
        message=strategy_module.ToolInvokeMessage.TextMessage(text="tool-ok"),
    )
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: [tool_text]),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=True),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 1,
                "emit_intermediate_thoughts": True,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    rendered = "".join(text_messages)
    assert rendered.count("<think>\nsearch plan\n</think>") == 1


def test_extract_tool_calls_ignores_invalid_entries(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    missing_id = strategy_module.AssistantPromptMessage.ToolCall(
        id="",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    missing_name = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_missing_name",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="",
            arguments='{"q":"hello"}',
        ),
    )
    chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="",
                tool_calls=[missing_id, missing_name],
            ),
            usage=None,
        ),
    )

    assert strategy.extract_tool_calls(chunk) == []


def test_invoke_streaming_merges_duplicate_tool_call_ids(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    partial = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="",
                tool_calls=[
                    strategy_module.AssistantPromptMessage.ToolCall(
                        id="call_1",
                        type="function",
                        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
                            name="lookup",
                            arguments="{broken",
                        ),
                    )
                ],
            ),
            usage=None,
        ),
    )
    final = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="",
                tool_calls=[
                    strategy_module.AssistantPromptMessage.ToolCall(
                        id="call_1",
                        type="function",
                        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
                            name="lookup",
                            arguments='{"q":"hello"}',
                        ),
                    )
                ],
            ),
            usage=None,
        ),
    )

    def _stream() -> Any:
        yield partial
        yield final

    llm = _SequenceLLM([_stream()])
    calls: list[dict[str, Any]] = []
    text_response = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.TEXT,
        message=strategy_module.ToolInvokeMessage.TextMessage(text="ok"),
    )

    def _tool_invoke(**kwargs: Any) -> list[Any]:
        calls.append(kwargs)
        return [text_response]

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    _ = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=True),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 1,
            }
        )
    )

    assert len(calls) == 1
    assert calls[0]["tool_name"] == "lookup"
    assert calls[0]["parameters"]["q"] == "hello"


def test_invoke_streaming_tool_call_thought_is_wrapped(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_stream_intermediate",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    stream_chunk = strategy_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        delta=types.SimpleNamespace(
            message=strategy_module.AssistantPromptMessage(
                content="thinking before tool",
                tool_calls=[tool_call],
            ),
            usage=None,
        ),
    )
    final_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="final answer",
            tool_calls=[],
        ),
        usage=None,
    )

    def _stream() -> Any:
        yield stream_chunk

    llm = _SequenceLLM([_stream(), final_result])
    tool_text = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.TEXT,
        message=strategy_module.ToolInvokeMessage.TextMessage(text="tool-ok"),
    )
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: [tool_text]),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=True),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 3,
                "emit_intermediate_thoughts": True,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    rendered = "\n".join(text_messages)
    assert "<think>" in rendered
    assert "</think>" in rendered
    assert "thinking before tool" in rendered
    assert "final answer" in rendered


def test_invoke_parse_error_tool_call_path(strategy_module: Any) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    bad_tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_bad",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments="{broken",
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[bad_tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [],
                "maximum_iterations": 1,
            }
        )
    )

    joined_text = "\n".join(
        [m["text"] for m in messages if m.get("kind") == "text"]
    )
    assert "tool arguments parse error" in joined_text


def test_invoke_max_iteration_limit_skips_tool_execution(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_1",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    first = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="round1",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    second = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="round2",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([first, second])
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: []),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [],
                "maximum_iterations": 2,
            }
        )
    )

    finished_logs = [
        m
        for m in messages
        if m.get("kind") == "log_finish"
        and isinstance(m.get("data"), dict)
        and isinstance(m["data"].get("output_summary"), dict)
    ]
    assert finished_logs
    assert any(
        log["data"]["output_summary"].get("is_error") is True
        for log in finished_logs
    )
    assert llm.calls == 2


def test_prompt_helper_methods_handle_images_and_system_message(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()

    base_messages = strategy._init_system_message(
        "system prompt",
        [strategy_module.UserPromptMessage(content="hi")],
    )
    assert isinstance(base_messages[0], strategy_module.SystemPromptMessage)

    image_item = types.SimpleNamespace(
        type=strategy_module.PromptMessageContentType.IMAGE,
        data="https://example.com/a.png",
    )
    text_item = types.SimpleNamespace(
        type=strategy_module.PromptMessageContentType.TEXT,
        data="caption",
    )
    user = strategy_module.UserPromptMessage(content=[text_item, image_item])
    normalized = strategy._clear_user_prompt_image_messages([user])
    assert normalized[0].content == "caption\n[image]"


def test_invoke_tool_image_message_path(strategy_module: Any) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_img",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need image",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    image_response = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.IMAGE,
        message=strategy_module.ToolInvokeMessage.TextMessage(
            text="https://example.com/image.png"
        ),
    )
    called: dict[str, Any] = {}

    def _tool_invoke(**kwargs: Any) -> list[Any]:
        called.update(kwargs)
        return [image_response]

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [
                    _build_tool_entity(
                        runtime_parameters={"lang": "ja"},
                    )
                ],
                "maximum_iterations": 1,
            }
        )
    )

    assert called["provider"] == "provider"
    assert called["tool_name"] == "lookup"
    assert called["parameters"]["lang"] == "ja"
    assert called["parameters"]["q"] == "hello"

    assert any(
        getattr(message, "type", None)
        == strategy_module.ToolInvokeMessage.MessageType.IMAGE
        for message in messages
    )
    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    assert "image generated and sent to user." in "\n".join(text_messages)


def test_invoke_tool_blob_message_path(strategy_module: Any) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_blob",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need file",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    blob_response = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.BLOB,
        message=types.SimpleNamespace(data=b"blob-data"),
    )
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: [blob_response]),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 1,
            }
        )
    )

    assert any(
        getattr(message, "type", None)
        == strategy_module.ToolInvokeMessage.MessageType.BLOB
        for message in messages
    )
    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    assert "Generated file ..." in "\n".join(text_messages)


def test_resolve_safe_local_file_path_rejects_path_traversal(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    assert (
        strategy._resolve_safe_local_file_path("/files/../etc/passwd") is None
    )


def test_read_local_file_for_blob_rejects_oversized_file(
    strategy_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    monkeypatch.setattr(
        strategy, "_resolve_safe_local_file_path", lambda _: "/tmp/fake"
    )
    monkeypatch.setattr(strategy_module.os.path, "exists", lambda _: True)
    monkeypatch.setattr(
        strategy_module.os.path,
        "getsize",
        lambda _: strategy._max_blob_file_bytes() + 1,
    )

    with pytest.raises(ValueError, match="too large"):
        strategy._read_local_file_for_blob("/files/huge.bin")


def test_invoke_image_blob_conversion_error_masks_internal_details(
    strategy_module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_img_err",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need image",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    image_response = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.IMAGE,
        message=strategy_module.ToolInvokeMessage.TextMessage(
            text="/files/a.png"
        ),
    )

    def _raise(_: str) -> tuple[bytes, str] | None:
        raise RuntimeError("internal path /etc/secret")

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: [image_response]),
    )
    monkeypatch.setattr(strategy, "_read_local_file_for_blob", _raise)

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 1,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    rendered = "\n".join(text_messages)
    assert "Failed to process generated image file." in rendered
    assert "internal path /etc/secret" not in rendered


def test_invoke_tool_exception_masks_internal_details(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_tool_error",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])

    def _tool_invoke(**_: Any) -> list[Any]:
        raise RuntimeError("internal error path=/srv/secret")

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 1,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    rendered = "\n".join(text_messages)
    assert "tool invoke error: failed to execute tool" in rendered
    assert "internal error path=/srv/secret" not in rendered


def test_invoke_normalizes_option_parameter_boolean_to_string(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_include_answer",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"include_answer": false}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    called: dict[str, Any] = {}
    text_response = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.TEXT,
        message=strategy_module.ToolInvokeMessage.TextMessage(text="ok"),
    )

    def _tool_invoke(**kwargs: Any) -> list[Any]:
        called.update(kwargs)
        return [text_response]

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    _ = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [
                    _build_tool_entity(
                        parameters=[
                            {
                                "name": "include_answer",
                                "type": "select",
                                "options": [
                                    {"value": "false"},
                                    {"value": "true"},
                                    {"value": "basic"},
                                    {"value": "advanced"},
                                ],
                            }
                        ]
                    )
                ],
                "maximum_iterations": 1,
            }
        )
    )

    assert called["parameters"]["include_answer"] == "false"


def test_invoke_validates_option_parameter_before_tool_call(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_invalid_option",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"include_answer":"invalid"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    call_count = 0

    def _tool_invoke(**_: Any) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return []

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [
                    _build_tool_entity(
                        parameters=[
                            {
                                "name": "include_answer",
                                "type": "select",
                                "options": [
                                    {"value": "false"},
                                    {"value": "true"},
                                    {"value": "basic"},
                                    {"value": "advanced"},
                                ],
                            }
                        ]
                    )
                ],
                "maximum_iterations": 1,
            }
        )
    )

    text_messages = [
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    ]
    rendered = "\n".join(text_messages)
    assert "tool arguments validation error" in rendered
    assert call_count == 0


def test_invoke_rejects_unknown_tool_argument_when_schema_exists(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_unknown_arg",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello","unexpected":"x"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    call_count = 0

    def _tool_invoke(**_: Any) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return []

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [
                    _build_tool_entity(
                        parameters=[
                            {"name": "q", "type": "string"},
                        ]
                    )
                ],
                "maximum_iterations": 1,
            }
        )
    )

    rendered = "\n".join(
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    )
    assert "unknown parameters" in rendered
    assert call_count == 0


def test_invoke_rejects_tool_argument_when_schema_missing_by_default(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_no_schema_default",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    call_count = 0

    def _tool_invoke(**_: Any) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return []

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [
                    _build_tool_entity(
                        name="lookup",
                        parameters=[],
                    )
                ],
                "maximum_iterations": 1,
            }
        )
    )

    rendered = "\n".join(
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    )
    assert "schema is required for tool 'lookup'" in rendered
    assert call_count == 0


def test_invoke_rejects_opt_in_without_override_env(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_no_schema_opt_in_no_env",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    call_count = 0

    def _tool_invoke(**_: Any) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return []

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [
                    _build_tool_entity(
                        name="lookup",
                        parameters=[],
                    )
                ],
                "maximum_iterations": 1,
                "allow_schemaless_tool_args": True,
            }
        )
    )

    rendered = "\n".join(
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    )
    assert "schema is required for tool 'lookup'" in rendered
    assert call_count == 0


def test_invoke_allows_tool_argument_when_schema_missing_with_opt_in(
    strategy_module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    monkeypatch.setenv("GPT5_AGENT_ALLOW_SCHEMELESS_OVERRIDE", "true")
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_no_schema_opt_in",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    llm_result = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="need tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([llm_result])
    call_count = 0

    def _tool_invoke(**_: Any) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [strategy_module.ToolInvokeMessage.TextMessage("done")]

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [
                    _build_tool_entity(
                        name="lookup",
                        parameters=[],
                    )
                ],
                "maximum_iterations": 1,
                "allow_schemaless_tool_args": True,
            }
        )
    )

    assert call_count == 1


def test_normalize_tool_invoke_parameters_rejects_large_schemaless_args(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool = types.SimpleNamespace(
        identity=types.SimpleNamespace(name="lookup"),
        parameters=[],
    )
    oversized_args = {
        f"k{i}": "x" for i in range(strategy._MAX_SCHEMELESS_ARG_KEYS + 1)
    }
    _normalized, error = strategy._normalize_tool_invoke_parameters(
        tool_instance=tool,
        runtime_parameters={},
        tool_call_args=oversized_args,
        allow_schemaless_tool_args=True,
    )
    assert "too many arguments without schema" in str(error)


def test_invoke_skips_repeated_failed_tool_invocation(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_repeat_error",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    first = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="round1",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    second = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="round2",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    llm = _SequenceLLM([first, second])
    call_count = 0

    def _tool_invoke(**_: Any) -> list[Any]:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("internal invoke failure")

    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=_tool_invoke),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 3,
            }
        )
    )

    finished_logs = [
        m
        for m in messages
        if m.get("kind") == "log_finish"
        and isinstance(m.get("data"), dict)
        and isinstance(m["data"].get("output_summary"), dict)
    ]
    assert finished_logs
    assert any(
        log["data"]["output_summary"].get("is_error") is True
        for log in finished_logs
    )
    assert call_count == 1


def test_invoke_emits_intermediate_thought_with_tool_calls_by_default(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_intermediate",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    first = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="thinking before tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    second = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="final answer",
            tool_calls=[],
        ),
        usage=None,
    )
    llm = _SequenceLLM([first, second])
    tool_text = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.TEXT,
        message=strategy_module.ToolInvokeMessage.TextMessage(text="tool-ok"),
    )
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: [tool_text]),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 3,
                "emit_intermediate_thoughts": True,
            }
        )
    )

    rendered = "\n".join(
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    )
    assert "<think>" in rendered
    assert "</think>" in rendered
    assert "thinking before tool" in rendered
    assert "final answer" in rendered


def test_invoke_can_disable_intermediate_thought_with_tool_calls(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_intermediate_disabled",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    first = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="thinking before tool",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    second = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="final answer",
            tool_calls=[],
        ),
        usage=None,
    )
    llm = _SequenceLLM([first, second])
    tool_text = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.TEXT,
        message=strategy_module.ToolInvokeMessage.TextMessage(text="tool-ok"),
    )
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: [tool_text]),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 3,
                "emit_intermediate_thoughts": False,
            }
        )
    )

    rendered = "\n".join(
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    )
    assert "<think>" not in rendered
    assert "</think>" not in rendered
    assert "thinking before tool" not in rendered
    assert "final answer" in rendered


def test_invoke_emits_tool_thought_fallback_when_content_is_empty(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool_call = strategy_module.AssistantPromptMessage.ToolCall(
        id="call_empty_thought",
        type="function",
        function=strategy_module.AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup",
            arguments='{"q":"hello"}',
        ),
    )
    first = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="",
            tool_calls=[tool_call],
        ),
        usage=None,
    )
    second = strategy_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=strategy_module.AssistantPromptMessage(
            content="final answer",
            tool_calls=[],
        ),
        usage=None,
    )
    llm = _SequenceLLM([first, second])
    tool_text = types.SimpleNamespace(
        type=strategy_module.ToolInvokeMessage.MessageType.TEXT,
        message=strategy_module.ToolInvokeMessage.TextMessage(text="tool-ok"),
    )
    strategy.session = types.SimpleNamespace(
        model=types.SimpleNamespace(llm=llm),
        tool=types.SimpleNamespace(invoke=lambda **_: [tool_text]),
    )

    messages = list(
        strategy._invoke(
            {
                "query": "hello",
                "instruction": "",
                "model": _build_model_config(strategy_module, stream=False),
                "tools": [_build_tool_entity()],
                "maximum_iterations": 3,
                "emit_intermediate_thoughts": True,
            }
        )
    )

    rendered = "\n".join(
        m["text"]
        for m in messages
        if isinstance(m, dict) and m.get("kind") == "text"
    )
    assert "<think>" in rendered
    assert "まず、lookup ツールで必要な情報を確認します。" in rendered
    assert "</think>" in rendered


def test_format_thought_block_normalizes_intent_prefix(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    block = strategy._format_thought_block(
        "意図：まず current_time ツールで時刻を確認します。"
    )
    assert block.startswith("<think>\n")
    assert block.endswith("\n</think>")
    assert "意図：" not in block
    assert "まず current_time ツールで時刻を確認します。" in block


def test_format_thought_block_avoids_double_wrapping(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    block = strategy._format_thought_block(
        "<think>\nすでに整形済みです。\n</think>"
    )
    assert block.count("<think>") == 1
    assert block.count("</think>") == 1


def test_strip_think_blocks_for_display_removes_complete_and_dangling_blocks(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    text = "<think>内部検討</think>公開文。" "<think>途中までの思考"

    cleaned = strategy._strip_think_blocks_for_display(text)

    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    assert "内部検討" not in cleaned
    assert "公開文。" in cleaned


def test_log_data_defaults_to_metadata_only(strategy_module: Any) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    data = strategy._build_model_log_data(
        response="hello",
        tool_call_names=["lookup"],
        tool_calls=[("call_1", "lookup", {"q": "hello"}, None)],
    )

    assert "output_summary" in data
    assert "debug_output" not in data
    assert data["output_summary"]["response_chars"] == 5
    assert data["tool_input_summary"][0]["arg_keys"] == ["q"]


def test_log_data_redacts_sensitive_keys_in_verbose_mode(
    strategy_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    monkeypatch.setenv("GPT5_AGENT_VERBOSE_LOGGING", "true")

    data = strategy._build_tool_call_log_data(
        {
            "tool_call_id": "call_1",
            "tool_call_name": "lookup",
            "tool_call_input": {
                "api_key": "sk-secret",
                "query": "hello",
            },
            "tool_response": "tool invoke error: failed to execute tool",
            "meta": {"error": "failed"},
        }
    )

    assert data["output_summary"]["is_error"] is True
    assert "debug_output" in data
    assert (
        data["debug_output"]["tool_call_input"]["api_key"] == "***REDACTED***"
    )
    assert data["debug_output"]["tool_call_input"]["query"] == {"chars": 5}
    assert "preview" not in data["debug_output"]["tool_call_input"]["query"]


def test_log_data_includes_preview_only_with_explicit_flag(
    strategy_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    monkeypatch.setenv("GPT5_AGENT_VERBOSE_LOGGING", "true")
    monkeypatch.setenv("GPT5_AGENT_VERBOSE_LOG_PREVIEW", "true")

    data = strategy._build_model_log_data(
        response="hello world",
        tool_call_names=["lookup"],
        tool_calls=[("call_1", "lookup", {"q": "hello"}, None)],
    )

    debug_response = data["debug_output"]["response"]
    assert debug_response["chars"] == 11
    assert "preview" in debug_response


def test_round_log_data_counts_tool_errors(strategy_module: Any) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    data = strategy._build_round_log_data(
        llm_response="assistant response",
        tool_responses=[
            {
                "tool_call_name": "lookup",
                "tool_response": "ok",
            },
            {
                "tool_call_name": "lookup",
                "tool_response": "tool arguments validation error: invalid",
                "meta": {"error": "invalid"},
            },
        ],
    )
    assert data["output_summary"]["tool_response_count"] == 2
    assert data["output_summary"]["tool_error_count"] == 1


def test_normalize_tool_invoke_parameters_validates_required_and_types(
    strategy_module: Any,
) -> None:
    strategy = strategy_module.GPT5FunctionCallingStrategy()
    tool = types.SimpleNamespace(
        parameters=[
            types.SimpleNamespace(
                name="count", type="integer", required=True, options=[]
            ),
            types.SimpleNamespace(
                name="enabled",
                type="boolean",
                required=False,
                options=[],
            ),
        ]
    )

    _normalized, error = strategy._normalize_tool_invoke_parameters(
        tool_instance=tool,
        runtime_parameters={},
        tool_call_args={"enabled": "true"},
    )
    assert "missing required parameter 'count'" in str(error)

    normalized, error = strategy._normalize_tool_invoke_parameters(
        tool_instance=tool,
        runtime_parameters={},
        tool_call_args={"count": "12", "enabled": "true"},
    )
    assert error is None
    assert normalized["count"] == 12
    assert normalized["enabled"] is True

    _normalized, error = strategy._normalize_tool_invoke_parameters(
        tool_instance=tool,
        runtime_parameters={},
        tool_call_args={"count": "abc"},
    )
    assert "requires integer" in str(error)
