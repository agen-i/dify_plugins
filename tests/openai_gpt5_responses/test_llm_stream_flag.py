from __future__ import annotations

import importlib
import sys
import types
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

BASE_DIR = Path(__file__).resolve().parents[2]
PLUGIN_DIR = BASE_DIR / "app" / "openai_gpt5_responses"


def _install_openai_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    openai_mod = types.ModuleType("openai")

    class APIError(Exception): ...

    class APIConnectionError(APIError): ...

    class APIStatusError(APIError): ...

    class APITimeoutError(APIError): ...

    class AuthenticationError(APIError): ...

    class PermissionDeniedError(APIError): ...

    class RateLimitError(APIError): ...

    class InternalServerError(APIError): ...

    class BadRequestError(APIError): ...

    class NotFoundError(APIError): ...

    class UnprocessableEntityError(APIError): ...

    class _ResponsesClient:
        def create(self, **_: Any) -> Any:
            return types.SimpleNamespace(
                model="gpt-5.2",
                usage=None,
                output_text="ok",
                output=[],
            )

    class OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _ResponsesClient()

    openai_mod.APIError = APIError
    openai_mod.APIConnectionError = APIConnectionError
    openai_mod.APIStatusError = APIStatusError
    openai_mod.APITimeoutError = APITimeoutError
    openai_mod.AuthenticationError = AuthenticationError
    openai_mod.PermissionDeniedError = PermissionDeniedError
    openai_mod.RateLimitError = RateLimitError
    openai_mod.InternalServerError = InternalServerError
    openai_mod.BadRequestError = BadRequestError
    openai_mod.NotFoundError = NotFoundError
    openai_mod.UnprocessableEntityError = UnprocessableEntityError
    openai_mod.OpenAI = OpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_mod)


def _install_dify_plugin_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    dify_plugin_mod = types.ModuleType("dify_plugin")

    class LargeLanguageModel:
        def timing_context(self) -> Any:
            class _Ctx:
                def __enter__(self) -> None:
                    return None

                def __exit__(
                    self,
                    exc_type: type[BaseException] | None,
                    exc: BaseException | None,
                    tb: Any,
                ) -> bool:
                    return False

            return _Ctx()

        def _validate_and_filter_model_parameters(
            self, **kwargs: Any
        ) -> dict[str, Any]:
            return dict(kwargs["model_parameters"])

        def _transform_invoke_error(self, exc: Exception) -> Exception:
            return exc

        def _calc_response_usage(self, **_: Any) -> None:
            return None

        def _get_num_tokens_by_gpt2(self, text: str) -> int:
            return len(text)

    dify_plugin_mod.LargeLanguageModel = LargeLanguageModel

    entities_mod = types.ModuleType("dify_plugin.entities")
    model_mod = types.ModuleType("dify_plugin.entities.model")
    model_llm_mod = types.ModuleType("dify_plugin.entities.model.llm")
    model_message_mod = types.ModuleType("dify_plugin.entities.model.message")
    errors_mod = types.ModuleType("dify_plugin.errors")
    errors_model_mod = types.ModuleType("dify_plugin.errors.model")

    @dataclass
    class LLMResult:
        model: str
        prompt_messages: list[Any]
        message: Any
        usage: Any
        system_fingerprint: Any

    @dataclass
    class LLMResultChunkDelta:
        index: int
        message: Any
        finish_reason: str
        usage: Any

    @dataclass
    class LLMResultChunk:
        model: str
        prompt_messages: list[Any]
        system_fingerprint: Any
        delta: LLMResultChunkDelta

    @dataclass
    class AssistantPromptMessage:
        content: Any
        tool_calls: list[Any]

        @dataclass
        class ToolCall:
            @dataclass
            class ToolCallFunction:
                name: str
                arguments: str

            id: str
            type: str
            function: AssistantPromptMessage.ToolCall.ToolCallFunction

    class PromptMessage: ...

    class PromptMessageTool: ...

    class CredentialsValidateFailedError(Exception): ...

    class InvokeError(Exception): ...

    model_llm_mod.LLMResult = LLMResult
    model_llm_mod.LLMResultChunk = LLMResultChunk
    model_llm_mod.LLMResultChunkDelta = LLMResultChunkDelta
    model_message_mod.AssistantPromptMessage = AssistantPromptMessage
    model_message_mod.PromptMessage = PromptMessage
    model_message_mod.PromptMessageTool = PromptMessageTool
    errors_model_mod.CredentialsValidateFailedError = (
        CredentialsValidateFailedError
    )
    errors_model_mod.InvokeError = InvokeError

    monkeypatch.setitem(sys.modules, "dify_plugin", dify_plugin_mod)
    monkeypatch.setitem(sys.modules, "dify_plugin.entities", entities_mod)
    monkeypatch.setitem(sys.modules, "dify_plugin.entities.model", model_mod)
    monkeypatch.setitem(
        sys.modules, "dify_plugin.entities.model.llm", model_llm_mod
    )
    monkeypatch.setitem(
        sys.modules, "dify_plugin.entities.model.message", model_message_mod
    )
    monkeypatch.setitem(sys.modules, "dify_plugin.errors", errors_mod)
    monkeypatch.setitem(
        sys.modules, "dify_plugin.errors.model", errors_model_mod
    )


@pytest.fixture
def llm_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    _install_openai_stub(monkeypatch)
    _install_dify_plugin_stub(monkeypatch)
    sys.modules.pop("app.openai_gpt5_responses.models.llm.llm", None)
    importlib.invalidate_caches()
    return importlib.import_module("app.openai_gpt5_responses.models.llm.llm")


def _build_llm_result(llm_module: Any) -> Any:
    assistant = llm_module.AssistantPromptMessage(content="ok", tool_calls=[])
    return llm_module.LLMResult(
        model="gpt-5.2",
        prompt_messages=[],
        message=assistant,
        usage=None,
        system_fingerprint=None,
    )


def test_llm_module_importable_without_app_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_openai_stub(monkeypatch)
    _install_dify_plugin_stub(monkeypatch)
    monkeypatch.setitem(sys.modules, "app", types.ModuleType("app"))
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    sys.modules.pop("models.llm.llm", None)
    importlib.invalidate_caches()

    module = importlib.import_module("models.llm.llm")
    assert module.OpenAIGPT5LargeLanguageModel.__name__


def test_invoke_disable_stream_string_returns_blocking_result(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    llm_result = _build_llm_result(llm_module)

    monkeypatch.setattr(
        model,
        "_normalize_parameters",
        lambda **_: {"enable_stream": "false"},
    )
    monkeypatch.setattr(
        model, "_to_credential_kwargs", lambda _credentials: {}
    )
    monkeypatch.setattr(model, "_to_llm_result", lambda **_: llm_result)

    result = model._invoke(
        model="gpt-5.2",
        credentials={},
        prompt_messages=[],
        model_parameters={"enable_stream": "false"},
        tools=[],
        stream=True,
    )

    assert result is llm_result


def test_invoke_does_not_start_nested_timing_context(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    llm_result = _build_llm_result(llm_module)

    monkeypatch.setattr(
        model,
        "_normalize_parameters",
        lambda **_: {"enable_stream": "false"},
    )
    monkeypatch.setattr(
        model, "_to_credential_kwargs", lambda _credentials: {}
    )
    monkeypatch.setattr(model, "_to_llm_result", lambda **_: llm_result)

    def _timing_context_should_not_be_called() -> Any:
        raise AssertionError("nested timing_context must not be called")

    monkeypatch.setattr(
        model, "timing_context", _timing_context_should_not_be_called
    )

    result = model._invoke(
        model="gpt-5.2",
        credentials={},
        prompt_messages=[],
        model_parameters={"enable_stream": "false"},
        tools=[],
        stream=True,
    )

    assert result is llm_result


def test_invoke_enable_stream_string_returns_generator(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    assistant = llm_module.AssistantPromptMessage(content="ok", tool_calls=[])
    expected_chunk = llm_module.LLMResultChunk(
        model="gpt-5.2",
        prompt_messages=[],
        system_fingerprint=None,
        delta=llm_module.LLMResultChunkDelta(
            index=0,
            message=assistant,
            finish_reason="stop",
            usage=None,
        ),
    )

    monkeypatch.setattr(
        model,
        "_normalize_parameters",
        lambda **_: {"enable_stream": "true"},
    )
    monkeypatch.setattr(model, "_to_credential_kwargs", lambda _: {})

    def _streaming_response(**_: Any) -> Any:
        yield expected_chunk

    monkeypatch.setattr(model, "_invoke_streaming", _streaming_response)

    result = model._invoke(
        model="gpt-5.2",
        credentials={},
        prompt_messages=[],
        model_parameters={"enable_stream": "true"},
        tools=[],
        stream=True,
    )

    assert isinstance(result, Generator)
    assert list(result) == [expected_chunk]


def test_invoke_streaming_formats_reasoning_and_emits_tool_call_on_done(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    usage_marker = {"usage": True}
    monkeypatch.setattr(
        model, "_calc_response_usage", lambda **_: usage_marker
    )

    events = [
        types.SimpleNamespace(
            type="response.reasoning_text.delta", delta="think-1"
        ),
        types.SimpleNamespace(
            type="response.reasoning_text.delta", delta=" think-2"
        ),
        types.SimpleNamespace(
            type="response.output_text.delta", delta="Answer"
        ),
        types.SimpleNamespace(
            type="response.function_call_arguments.delta",
            item_id="item_1",
            delta='{"q":',
        ),
        types.SimpleNamespace(
            type="response.function_call_arguments.delta",
            item_id="item_1",
            delta='"ok"}',
        ),
        types.SimpleNamespace(
            type="response.output_item.done",
            item=types.SimpleNamespace(
                type="function_call",
                id="item_1",
                call_id="call_1",
                name="lookup",
                arguments='{"q":"ok"}',
            ),
        ),
        types.SimpleNamespace(
            type="response.completed",
            response=types.SimpleNamespace(
                model="gpt-5.2",
                status="completed",
                usage=types.SimpleNamespace(input_tokens=2, output_tokens=3),
                _request_id="req_stream_ok",
            ),
        ),
    ]

    class _Stream(list):
        closed = False

        def close(self) -> None:
            self.closed = True

    stream = _Stream(events)

    class _Responses:
        def create(self, **_: Any) -> Any:
            return stream

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    chunks = list(
        model._invoke_streaming(
            model="gpt-5.2",
            credentials={},
            prompt_messages=[],
            client=_OpenAI(),
            request_payload={"model": "gpt-5.2", "stream": True},
            audit_id="audit123",
        )
    )

    assert chunks[0].delta.message.content == "<think>\nthink-1"
    assert chunks[1].delta.message.content == " think-2"
    assert chunks[2].delta.message.content == "\n</think>Answer"

    assert chunks[3].delta.message.tool_calls[0].id == "call_1"
    assert chunks[3].delta.message.tool_calls[0].function.name == "lookup"
    assert chunks[3].delta.message.tool_calls[0].function.arguments == (
        '{"q":"ok"}'
    )

    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].delta.usage is usage_marker
    assert chunks[-1].delta.message.content == ""
    assert stream.closed is True


def test_invoke_streaming_closes_open_think_when_stream_ends(
    llm_module: Any,
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()

    events = [
        types.SimpleNamespace(
            type="response.reasoning_text.delta", delta="thinking"
        ),
        types.SimpleNamespace(
            type="response.completed",
            response=types.SimpleNamespace(
                model="gpt-5.2",
                status="completed",
                usage=types.SimpleNamespace(input_tokens=1, output_tokens=1),
            ),
        ),
    ]

    class _Responses:
        def create(self, **_: Any) -> Any:
            return events

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    chunks = list(
        model._invoke_streaming(
            model="gpt-5.2",
            credentials={},
            prompt_messages=[],
            client=_OpenAI(),
            request_payload={"model": "gpt-5.2", "stream": True},
            audit_id="audit123",
        )
    )

    assert chunks[0].delta.message.content == "<think>\nthinking"
    assert chunks[1].delta.message.content == "\n</think>"
    assert chunks[-1].delta.finish_reason == "stop"


def test_invoke_streaming_raises_invoke_error_on_error_event(
    llm_module: Any,
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()

    events = [
        types.SimpleNamespace(
            type="error",
            code="invalid_request",
            message="bad request",
        )
    ]

    class _Responses:
        def create(self, **_: Any) -> Any:
            return events

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    with pytest.raises(llm_module.InvokeError):
        list(
            model._invoke_streaming(
                model="gpt-5.2",
                credentials={},
                prompt_messages=[],
                client=_OpenAI(),
                request_payload={"model": "gpt-5.2", "stream": True},
                audit_id="audit123",
            )
        )


def test_safe_int_and_credential_kwargs_bounds(llm_module: Any) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()

    assert model._safe_int("10", 1) == 10
    assert model._safe_int("not-int", 7) == 7

    kwargs = model._to_credential_kwargs(
        {
            "openai_api_key": "k",
            "openai_api_base": "https://api.openai.com",
            "request_timeout_seconds": "9999",
            "max_retries": "99",
            "openai_organization": " org ",
        }
    )
    assert kwargs["timeout"] == 1200.0
    assert kwargs["max_retries"] == 5
    assert kwargs["base_url"] == "https://api.openai.com/v1"
    assert kwargs["organization"] == "org"


def test_get_num_tokens_joins_prompt_content(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    captured: dict[str, str] = {}

    def _count(text: str) -> int:
        captured["text"] = text
        return 42

    monkeypatch.setattr(model, "_get_num_tokens_by_gpt2", _count)
    messages = [
        types.SimpleNamespace(content="a"),
        types.SimpleNamespace(content="b"),
        types.SimpleNamespace(content=None),
    ]

    assert model.get_num_tokens("gpt-5.2", {}, messages) == 42
    assert captured["text"] == "a\nb"


def test_normalize_parameters_fallback_after_validation_error(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()

    def _raise_value_error(**_: Any) -> dict[str, Any]:
        raise ValueError("bad")

    monkeypatch.setattr(
        model, "_validate_and_filter_model_parameters", _raise_value_error
    )
    normalized = model._normalize_parameters(
        model="gpt-5.2",
        credentials={},
        model_parameters={
            "max_output_tokens": 10,
            "enable_stream": True,
            "unknown": "x",
        },
    )

    assert normalized == {"max_output_tokens": 10, "enable_stream": True}


def test_to_llm_result_converts_usage_and_tool_calls(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    usage_marker = {"ok": True}
    monkeypatch.setattr(
        model, "_calc_response_usage", lambda **_: usage_marker
    )
    response = types.SimpleNamespace(
        model="gpt-5.2",
        output_text="assistant answer",
        output=[
            types.SimpleNamespace(
                type="function_call",
                call_id="call_1",
                name="lookup",
                arguments={"q": "hello"},
            )
        ],
        usage=types.SimpleNamespace(input_tokens=3, output_tokens=5),
    )

    llm_result = model._to_llm_result(
        model="gpt-5.2",
        credentials={},
        prompt_messages=[],
        response=response,
    )

    assert llm_result.message.content == "assistant answer"
    assert llm_result.message.tool_calls[0].function.name == "lookup"
    assert (
        llm_result.message.tool_calls[0].function.arguments == '{"q": "hello"}'
    )
    assert llm_result.usage is usage_marker


def test_validate_credentials_requires_api_key(llm_module: Any) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()

    with pytest.raises(llm_module.CredentialsValidateFailedError):
        model.validate_credentials("gpt-5.2", {})


def test_validate_credentials_calls_responses_create(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class _Responses:
        def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return types.SimpleNamespace()

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    monkeypatch.setattr(llm_module, "OpenAI", _OpenAI)
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    model.validate_credentials("gpt-5.2", {"openai_api_key": "k"})

    assert captured["model"] == "gpt-5.2"
    assert captured["store"] is False


def test_validate_credentials_rejects_invalid_api_base(
    llm_module: Any,
) -> None:
    model = llm_module.OpenAIGPT5LargeLanguageModel()
    with pytest.raises(llm_module.CredentialsValidateFailedError) as exc:
        model.validate_credentials(
            "gpt-5.2",
            {
                "openai_api_key": "k",
                "openai_api_base": "http://127.0.0.1:8000",
            },
        )

    assert "openai_api_base must use https" in str(exc.value)


def test_validate_credentials_wraps_unexpected_error_with_safe_message(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Responses:
        def create(self, **_: Any) -> Any:
            raise RuntimeError("unexpected sensitive detail")

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    monkeypatch.setattr(llm_module, "OpenAI", _OpenAI)
    model = llm_module.OpenAIGPT5LargeLanguageModel()

    with pytest.raises(llm_module.CredentialsValidateFailedError) as exc:
        model.validate_credentials("gpt-5.2", {"openai_api_key": "k"})

    assert "OpenAI model credential validation failed." in str(exc.value)
    assert "unexpected sensitive detail" not in str(exc.value)


def test_invoke_sets_user_and_stop_truncation(
    llm_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class _Responses:
        def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return types.SimpleNamespace(
                model="gpt-5.2", usage=None, output_text="ok", output=[]
            )

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    model = llm_module.OpenAIGPT5LargeLanguageModel()
    llm_result = _build_llm_result(llm_module)
    monkeypatch.setattr(llm_module, "OpenAI", _OpenAI)
    monkeypatch.setattr(
        model, "_normalize_parameters", lambda **_: {"enable_stream": False}
    )
    monkeypatch.setattr(
        model, "_to_credential_kwargs", lambda _credentials: {}
    )
    monkeypatch.setattr(model, "_to_llm_result", lambda **_: llm_result)

    result = model._invoke(
        model="gpt-5.2",
        credentials={},
        prompt_messages=[],
        model_parameters={"enable_stream": False},
        tools=[],
        stream=True,
        user="user-id",
        stop=["END"],
    )

    assert result is llm_result
    assert captured["user"] == "user-id"
    assert captured["truncation"] == "disabled"


def test_invoke_emits_safe_audit_logs_on_success(
    llm_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Responses:
        def create(self, **_: Any) -> Any:
            return types.SimpleNamespace(
                model="gpt-5.2",
                usage=None,
                output_text="ok",
                output=[],
                _request_id="req_success_1",
            )

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    model = llm_module.OpenAIGPT5LargeLanguageModel()
    llm_result = _build_llm_result(llm_module)
    monkeypatch.setattr(llm_module, "OpenAI", _OpenAI)
    monkeypatch.setattr(
        model,
        "_normalize_parameters",
        lambda **_: {"enable_stream": "false", "response_format": "text"},
    )
    monkeypatch.setattr(model, "_to_llm_result", lambda **_: llm_result)
    monkeypatch.setenv("OPENAI_GPT5_AUDIT_LOG", "true")
    monkeypatch.setenv("OPENAI_GPT5_ALLOWED_BASE_URL_HOSTS", "example.test")

    caplog.set_level("INFO")

    result = model._invoke(
        model="gpt-5.2-pro",
        credentials={
            "openai_api_key": "sk-test-secret-key",
            "openai_api_base": "https://example.test/v1",
        },
        prompt_messages=[types.SimpleNamespace(role="user", content="hello")],
        model_parameters={"enable_stream": "false", "response_format": "text"},
        tools=[],
        stream=True,
    )

    assert result is llm_result
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "openai_gpt5_audit" in text
    assert "responses_api_request" in text
    assert "responses_api_success" in text
    assert '"model": "gpt-5.2-pro"' in text
    assert '"base_url_host": "example.test"' in text
    assert '"request_id": "req_success_1"' in text
    assert "sk-test-secret-key" not in text
    assert '"content": "hello"' not in text


def test_invoke_emits_safe_audit_logs_on_error(
    llm_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Responses:
        def create(self, **_: Any) -> Any:
            err = llm_module.APIStatusError("bad request")
            err.status_code = 400
            err.request_id = "req_error_1"
            err.code = "invalid_value"
            err.param = "input[0]"
            err.type = "invalid_request_error"
            raise err

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    model = llm_module.OpenAIGPT5LargeLanguageModel()
    monkeypatch.setattr(llm_module, "OpenAI", _OpenAI)
    monkeypatch.setattr(
        model,
        "_normalize_parameters",
        lambda **_: {"enable_stream": "false", "response_format": "text"},
    )
    monkeypatch.setenv("OPENAI_GPT5_AUDIT_LOG", "1")
    caplog.set_level("INFO")

    with pytest.raises(llm_module.APIStatusError):
        model._invoke(
            model="gpt-5.2",
            credentials={"openai_api_key": "sk-secret-key"},
            prompt_messages=[
                types.SimpleNamespace(role="system", content="secret prompt")
            ],
            model_parameters={
                "enable_stream": "false",
                "response_format": "text",
            },
            tools=[],
            stream=True,
        )

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "responses_api_request" in text
    assert "responses_api_error" in text
    assert '"status_code": 400' in text
    assert '"request_id": "req_error_1"' in text
    assert "sk-secret-key" not in text
    assert "secret prompt" not in text


def test_invoke_emits_audit_logs_even_if_root_is_warning(
    llm_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    root_logger = llm_module.logging.getLogger()
    original_level = root_logger.level

    class _Responses:
        def create(self, **_: Any) -> Any:
            return types.SimpleNamespace(
                model="gpt-5.2",
                usage=None,
                output_text="ok",
                output=[],
                _request_id="req_root_warning",
            )

    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            self.responses = _Responses()

    model = llm_module.OpenAIGPT5LargeLanguageModel()
    llm_result = _build_llm_result(llm_module)
    monkeypatch.setattr(llm_module, "OpenAI", _OpenAI)
    monkeypatch.setattr(
        model,
        "_normalize_parameters",
        lambda **_: {"enable_stream": "false", "response_format": "text"},
    )
    monkeypatch.setattr(model, "_to_llm_result", lambda **_: llm_result)
    monkeypatch.setenv("OPENAI_GPT5_AUDIT_LOG", "true")

    root_logger.setLevel("WARNING")
    caplog.set_level("INFO")

    try:
        result = model._invoke(
            model="gpt-5.2",
            credentials={"openai_api_key": "sk-hidden"},
            prompt_messages=[
                types.SimpleNamespace(role="user", content="ping")
            ],
            model_parameters={
                "enable_stream": "false",
                "response_format": "text",
            },
            tools=[],
            stream=True,
        )
    finally:
        root_logger.setLevel(original_level)

    assert result is llm_result
    assert any(
        "responses_api_request" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "responses_api_success" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        record.name == "dify_plugin.plugin.audit.openai_gpt5_responses"
        for record in caplog.records
    )
