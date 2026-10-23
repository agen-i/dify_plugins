from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator, Mapping
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

import openai
from dify_plugin import LargeLanguageModel
from dify_plugin.entities.model.llm import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageTool,
)
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeError,
)
from openai import APIConnectionError, APIStatusError, OpenAI

try:
    from app.openai_gpt5_responses.internal.credentials import (
        normalize_api_base,
    )
    from app.openai_gpt5_responses.internal.messages import (
        extract_output_text,
        extract_tool_calls,
        prompt_messages_to_responses_input,
    )
    from app.openai_gpt5_responses.internal.payloads import (
        build_responses_request,
        coerce_bool_strict,
    )
except ModuleNotFoundError:
    from internal.credentials import normalize_api_base
    from internal.messages import (
        extract_output_text,
        extract_tool_calls,
        prompt_messages_to_responses_input,
    )
    from internal.payloads import (
        build_responses_request,
        coerce_bool_strict,
    )

logger = logging.getLogger(__name__)
AUDIT_LOGGER_NAME = "dify_plugin.plugin.audit.openai_gpt5_responses"
_REQUEST_TIMEOUT_DEFAULT_SECONDS = 600
_REQUEST_TIMEOUT_MAX_SECONDS = 1200
audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)

# Emit audit logs through the plugin logger hierarchy.
# Keep level INFO explicitly so records survive root WARNING configurations.
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = True

_MODEL_CREDENTIALS_FAILED_MESSAGE = (
    "OpenAI model credential validation failed."
)
_MODEL_CREDENTIALS_CONNECTION_FAILED_MESSAGE = (
    "OpenAI model connection failed. Check network and API base settings."
)


class _FunctionToolCallState:
    __slots__ = ("item_id", "call_id", "name", "arguments")

    def __init__(
        self,
        *,
        item_id: str,
        call_id: str,
        name: str,
        arguments: str,
    ) -> None:
        self.item_id = item_id
        self.call_id = call_id
        self.name = name
        self.arguments = arguments


class OpenAIGPT5LargeLanguageModel(LargeLanguageModel):
    @staticmethod
    def _is_audit_enabled() -> bool:
        raw = str(os.getenv("OPENAI_GPT5_AUDIT_LOG", "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _safe_base_url_host(credential_kwargs: Mapping[str, Any]) -> str:
        base_url = credential_kwargs.get("base_url")
        if isinstance(base_url, str) and base_url.strip():
            parsed = urlparse(base_url)
            if parsed.netloc:
                return parsed.netloc
        return "api.openai.com"

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _attr_or_key(value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(key, default)
        return getattr(value, key, default)

    def _emit_audit(self, event: str, **fields: Any) -> None:
        if not self._is_audit_enabled():
            return

        payload = {"event": event}
        for key, value in fields.items():
            if value is None:
                continue
            if value == "":
                continue
            payload[key] = value

        audit_logger.info(
            "openai_gpt5_audit %s",
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )

    @staticmethod
    def _extract_error_fields(exc: Exception) -> dict[str, Any]:
        return {
            "error_type": type(exc).__name__,
            "status_code": getattr(exc, "status_code", None),
            "request_id": getattr(exc, "request_id", None),
            "code": getattr(exc, "code", None),
            "param": getattr(exc, "param", None),
            "api_error_type": getattr(exc, "type", None),
        }

    def _extract_stream_error_fields(self, event: Any) -> dict[str, Any]:
        event_type = str(self._attr_or_key(event, "type", "") or "")
        fields: dict[str, Any] = {
            "event_type": event_type,
            "code": self._attr_or_key(event, "code", None),
            "param": self._attr_or_key(event, "param", None),
            "message": self._attr_or_key(event, "message", None),
        }

        response = self._attr_or_key(event, "response", None)
        if response is not None:
            fields["request_id"] = self._extract_response_request_id(response)
            fields["response_status"] = self._attr_or_key(
                response, "status", None
            )
            error_obj = self._attr_or_key(response, "error", None)
            if error_obj is not None:
                fields["code"] = fields.get("code") or self._attr_or_key(
                    error_obj, "code", None
                )
                fields["param"] = fields.get("param") or self._attr_or_key(
                    error_obj, "param", None
                )
                fields["message"] = fields.get("message") or self._attr_or_key(
                    error_obj, "message", None
                )

        return fields

    @property
    def _invoke_error_mapping(
        self,
    ) -> dict[type[InvokeError], list[type[Exception]]]:
        return {
            InvokeError: [
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.AuthenticationError,
                openai.PermissionDeniedError,
                openai.RateLimitError,
                openai.InternalServerError,
                openai.BadRequestError,
                openai.NotFoundError,
                openai.UnprocessableEntityError,
                openai.APIError,
            ]
        }

    def _to_credential_kwargs(
        self, credentials: Mapping[str, Any]
    ) -> dict[str, Any]:
        api_base = normalize_api_base(credentials.get("openai_api_base"))
        timeout_seconds = self._safe_int(
            credentials.get("request_timeout_seconds"),
            _REQUEST_TIMEOUT_DEFAULT_SECONDS,
        )
        timeout_seconds = max(
            30, min(_REQUEST_TIMEOUT_MAX_SECONDS, timeout_seconds)
        )
        max_retries = self._safe_int(credentials.get("max_retries"), 1)
        max_retries = max(0, min(5, max_retries))

        kwargs: dict[str, Any] = {
            "api_key": credentials.get("openai_api_key"),
            "timeout": float(timeout_seconds),
            "max_retries": max_retries,
        }

        if api_base:
            kwargs["base_url"] = api_base

        organization = str(
            credentials.get("openai_organization") or ""
        ).strip()
        if organization:
            kwargs["organization"] = organization

        return kwargs

    @staticmethod
    def _safe_int(value: object, default: int) -> int:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return default

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        if not credentials.get("openai_api_key"):
            raise CredentialsValidateFailedError("openai_api_key is required")

        try:
            client = OpenAI(**self._to_credential_kwargs(credentials))
            payload = build_responses_request(
                model=model,
                user_input="ping",
                model_parameters={
                    "max_output_tokens": 8,
                    "enable_stream": False,
                },
                tools=[],
                stream=False,
            )
            payload["store"] = False
            client.responses.create(**payload)
        except APIStatusError as exc:
            raise CredentialsValidateFailedError(
                f"OpenAI API status error ({exc.status_code})."
            ) from exc
        except APIConnectionError as exc:
            raise CredentialsValidateFailedError(
                _MODEL_CREDENTIALS_CONNECTION_FAILED_MESSAGE
            ) from exc
        except ValueError as exc:
            raise CredentialsValidateFailedError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise CredentialsValidateFailedError(
                _MODEL_CREDENTIALS_FAILED_MESSAGE
            ) from exc

    def get_num_tokens(
        self,
        model: str,
        credentials: Mapping,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        joined_text = "\n".join(
            [
                str(message.content)
                for message in prompt_messages
                if getattr(message, "content", None)
            ]
        )
        return self._get_num_tokens_by_gpt2(joined_text)

    def _build_stream_chunk(
        self,
        *,
        model: str,
        prompt_messages: list[PromptMessage],
        index: int,
        message: AssistantPromptMessage,
        usage: Any = None,
        finish_reason: str | None = None,
    ) -> LLMResultChunk:
        return LLMResultChunk(
            model=model,
            prompt_messages=prompt_messages,
            system_fingerprint=None,
            delta=LLMResultChunkDelta(
                index=index,
                message=message,
                finish_reason=finish_reason,
                usage=usage,
            ),
        )

    def _stream_tool_call_chunk(
        self,
        *,
        model: str,
        prompt_messages: list[PromptMessage],
        index: int,
        state: _FunctionToolCallState,
    ) -> LLMResultChunk:
        tool_call = AssistantPromptMessage.ToolCall(
            id=state.call_id,
            type="function",
            function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                name=state.name,
                arguments=state.arguments or "{}",
            ),
        )
        return self._build_stream_chunk(
            model=model,
            prompt_messages=prompt_messages,
            index=index,
            message=AssistantPromptMessage(content="", tool_calls=[tool_call]),
        )

    def _extract_response_request_id(self, response: Any) -> str | None:
        request_id = self._attr_or_key(response, "_request_id", None)
        if request_id:
            return str(request_id)
        request_id = self._attr_or_key(response, "request_id", None)
        if request_id:
            return str(request_id)
        return None

    def _extract_response_model(
        self, fallback_model: str, response: Any
    ) -> str:
        value = self._attr_or_key(response, "model", None)
        return str(value or fallback_model)

    def _extract_usage(
        self,
        *,
        model: str,
        credentials: Mapping,
        response: Any,
    ) -> Any:
        usage_obj = self._attr_or_key(response, "usage", None)
        if usage_obj is None:
            return None

        prompt_tokens = int(
            self._attr_or_key(usage_obj, "input_tokens", 0) or 0
        )
        completion_tokens = int(
            self._attr_or_key(usage_obj, "output_tokens", 0) or 0
        )

        return self._calc_response_usage(
            model=model,
            credentials=dict(credentials),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _stream_finish_reason(self, response: Any) -> str:
        status = str(self._attr_or_key(response, "status", "") or "").lower()
        if status == "incomplete":
            return "length"
        if status == "failed":
            return "error"
        return "stop"

    def _close_stream(self, stream_obj: Any) -> None:
        close = getattr(stream_obj, "close", None)
        if callable(close):
            close()

    def _stream_event_error_message(self, event: Any) -> str:
        event_type = str(self._attr_or_key(event, "type", "") or "")
        message = str(
            self._attr_or_key(event, "message", "")
            or self._attr_or_key(event, "error", "")
            or "responses stream failed"
        )

        if event_type in {"response.failed", "response.incomplete"}:
            response = self._attr_or_key(event, "response", None)
            if response is not None:
                error_obj = self._attr_or_key(response, "error", None)
                if error_obj is not None:
                    message = str(
                        self._attr_or_key(error_obj, "message", "") or message
                    )
                if not message.strip():
                    status = self._attr_or_key(response, "status", event_type)
                    message = str(status or event_type)

        code = self._attr_or_key(event, "code", None)
        if code:
            return f"{message} (code={code})"
        return message

    def _invoke_streaming(
        self,
        *,
        model: str,
        credentials: Mapping,
        prompt_messages: list[PromptMessage],
        client: OpenAI,
        request_payload: Mapping[str, Any],
        audit_id: str,
    ) -> Generator[LLMResultChunk, None, None]:
        stream_obj: Any = None
        tool_calls: dict[str, _FunctionToolCallState] = {}
        chunk_index = 0
        event_count = 0
        reasoning_open = False
        completed_response: Any = None
        response_model = model
        request_id = None
        current_event_type = ""
        stream_error_fields: dict[str, Any] = {}

        try:
            stream_obj = client.responses.create(**dict(request_payload))
            for event in stream_obj:
                event_count += 1
                current_event_type = str(
                    self._attr_or_key(event, "type", "") or ""
                )

                if current_event_type in {
                    "response.reasoning_text.delta",
                    "response.reasoning_summary_text.delta",
                }:
                    reasoning_delta = str(
                        self._attr_or_key(event, "delta", "") or ""
                    )
                    if not reasoning_delta:
                        continue
                    if not reasoning_open:
                        reasoning_delta = f"<think>\n{reasoning_delta}"
                        reasoning_open = True

                    chunk_index += 1
                    yield self._build_stream_chunk(
                        model=model,
                        prompt_messages=prompt_messages,
                        index=chunk_index,
                        message=AssistantPromptMessage(
                            content=reasoning_delta,
                            tool_calls=[],
                        ),
                    )
                    continue

                if current_event_type == "response.output_text.delta":
                    text_delta = str(
                        self._attr_or_key(event, "delta", "") or ""
                    )
                    if not text_delta:
                        continue
                    if reasoning_open:
                        text_delta = f"\n</think>{text_delta}"
                        reasoning_open = False

                    chunk_index += 1
                    yield self._build_stream_chunk(
                        model=model,
                        prompt_messages=prompt_messages,
                        index=chunk_index,
                        message=AssistantPromptMessage(
                            content=text_delta,
                            tool_calls=[],
                        ),
                    )
                    continue

                if (
                    current_event_type
                    == "response.function_call_arguments.delta"
                ):
                    item_id = str(
                        self._attr_or_key(event, "item_id", "") or ""
                    )
                    arguments_delta = str(
                        self._attr_or_key(event, "delta", "") or ""
                    )
                    if not item_id or not arguments_delta:
                        continue

                    state = tool_calls.get(item_id)
                    if state is None:
                        state = _FunctionToolCallState(
                            item_id=item_id,
                            call_id=item_id,
                            name="",
                            arguments="",
                        )
                        tool_calls[item_id] = state

                    state.arguments += arguments_delta
                    tool_calls[item_id] = state
                    continue

                if current_event_type == "response.output_item.done":
                    item = self._attr_or_key(event, "item", None)
                    if item is None:
                        continue

                    item_type = str(self._attr_or_key(item, "type", "") or "")
                    if item_type != "function_call":
                        continue

                    item_id = str(self._attr_or_key(item, "id", "") or "")
                    call_id = str(
                        self._attr_or_key(item, "call_id", "") or item_id or ""
                    )
                    key = item_id or call_id
                    if not key:
                        continue

                    state = tool_calls.get(key)
                    if state is None:
                        state = _FunctionToolCallState(
                            item_id=item_id or key,
                            call_id=call_id or key,
                            name="",
                            arguments="",
                        )

                    name = str(
                        self._attr_or_key(item, "name", "") or state.name
                    )
                    raw_arguments = self._attr_or_key(item, "arguments", None)
                    if raw_arguments is None:
                        arguments = state.arguments
                    elif isinstance(raw_arguments, Mapping):
                        arguments = json.dumps(
                            raw_arguments,
                            ensure_ascii=False,
                        )
                    else:
                        arguments = str(raw_arguments)

                    state.item_id = item_id or state.item_id or key
                    state.call_id = call_id or state.call_id
                    state.name = name
                    state.arguments = arguments

                    tool_calls[state.item_id] = state
                    if state.call_id:
                        tool_calls[state.call_id] = state

                    if not state.call_id or not state.name:
                        continue

                    chunk_index += 1
                    yield self._stream_tool_call_chunk(
                        model=model,
                        prompt_messages=prompt_messages,
                        index=chunk_index,
                        state=state,
                    )
                    continue

                if current_event_type == "response.completed":
                    completed_response = self._attr_or_key(
                        event, "response", None
                    )
                    if completed_response is not None:
                        response_model = self._extract_response_model(
                            model,
                            completed_response,
                        )
                        request_id = self._extract_response_request_id(
                            completed_response
                        )
                    continue

                if current_event_type in {
                    "error",
                    "response.failed",
                    "response.incomplete",
                }:
                    stream_error_fields = self._extract_stream_error_fields(
                        event
                    )
                    raise InvokeError(self._stream_event_error_message(event))

            if reasoning_open:
                chunk_index += 1
                yield self._build_stream_chunk(
                    model=model,
                    prompt_messages=prompt_messages,
                    index=chunk_index,
                    message=AssistantPromptMessage(
                        content="\n</think>",
                        tool_calls=[],
                    ),
                )

            usage = None
            finish_reason = "stop"
            if completed_response is not None:
                usage = self._extract_usage(
                    model=model,
                    credentials=credentials,
                    response=completed_response,
                )
                finish_reason = self._stream_finish_reason(completed_response)

            self._emit_audit(
                "responses_api_success",
                audit_id=audit_id,
                model=model,
                response_model=response_model,
                request_id=request_id,
                stream_event_count=event_count,
                stream=True,
            )

            chunk_index += 1
            yield self._build_stream_chunk(
                model=response_model,
                prompt_messages=prompt_messages,
                index=chunk_index,
                message=AssistantPromptMessage(content="", tool_calls=[]),
                usage=usage,
                finish_reason=finish_reason,
            )
        except (APIStatusError, APIConnectionError, openai.APIError) as exc:
            self._emit_audit(
                "responses_api_error",
                audit_id=audit_id,
                model=model,
                stream=True,
                stream_event_type=current_event_type,
                **self._extract_error_fields(exc),
            )
            raise self._transform_invoke_error(exc) from exc
        except Exception as exc:  # noqa: BLE001
            self._emit_audit(
                "responses_api_error",
                audit_id=audit_id,
                model=model,
                stream=True,
                stream_event_type=current_event_type,
                **stream_error_fields,
                error_type=type(exc).__name__,
            )

            if isinstance(exc, InvokeError):
                raise self._transform_invoke_error(exc) from exc

            logger.exception("OpenAI GPT-5 responses stream invoke failed")
            raise self._transform_invoke_error(exc) from exc
        finally:
            if stream_obj is not None:
                self._close_stream(stream_obj)

    def _invoke(
        self,
        model: str,
        credentials: Mapping,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> LLMResult | Generator[LLMResultChunk, None, None]:
        audit_id = uuid4().hex[:12]
        try:
            model_parameters = self._normalize_parameters(
                model=model,
                credentials=credentials,
                model_parameters=model_parameters,
            )

            effective_stream = (
                coerce_bool_strict(
                    model_parameters.get("enable_stream", True),
                    field_name="enable_stream",
                )
                and stream
            )

            user_input = prompt_messages_to_responses_input(prompt_messages)
            request_payload = build_responses_request(
                model=model,
                user_input=user_input,
                model_parameters=model_parameters,
                tools=tools or [],
                stream=effective_stream,
            )

            # Responses API stop tokens are not consistent across all models.
            if user:
                request_payload["user"] = user

            if stop:
                request_payload["truncation"] = "disabled"

            credential_kwargs = self._to_credential_kwargs(credentials)
            client = OpenAI(**credential_kwargs)

            self._emit_audit(
                "responses_api_request",
                audit_id=audit_id,
                model=model,
                response_format=str(
                    model_parameters.get("response_format") or "text"
                ),
                enable_stream=coerce_bool_strict(
                    model_parameters.get("enable_stream", True),
                    field_name="enable_stream",
                ),
                stream=bool(request_payload.get("stream")),
                input_message_count=self._to_int_or_none(
                    len(user_input) if isinstance(user_input, list) else 1
                ),
                tool_count=self._to_int_or_none(
                    len(request_payload.get("tools", []) or [])
                ),
                max_output_tokens=self._to_int_or_none(
                    request_payload.get("max_output_tokens")
                ),
                has_user=bool(user),
                has_stop=bool(stop),
                base_url_host=self._safe_base_url_host(credential_kwargs),
                use_custom_base_url="base_url" in credential_kwargs,
            )

            # LargeLanguageModel.invoke() already wraps _invoke with
            # timing_context(), so starting another timing context here
            # triggers race-condition guards in multi-thread execution.
            if effective_stream:
                return self._invoke_streaming(
                    model=model,
                    credentials=credentials,
                    prompt_messages=prompt_messages,
                    client=client,
                    request_payload=request_payload,
                    audit_id=audit_id,
                )

            response = client.responses.create(**request_payload)

            self._emit_audit(
                "responses_api_success",
                audit_id=audit_id,
                model=model,
                response_model=str(getattr(response, "model", model)),
                request_id=getattr(response, "_request_id", None),
            )

            llm_result = self._to_llm_result(
                model=model,
                credentials=credentials,
                prompt_messages=prompt_messages,
                response=response,
            )

            return llm_result
        except (APIStatusError, APIConnectionError, openai.APIError) as exc:
            self._emit_audit(
                "responses_api_error",
                audit_id=audit_id,
                model=model,
                **self._extract_error_fields(exc),
            )
            raise self._transform_invoke_error(exc) from exc
        except Exception as exc:  # noqa: BLE001
            self._emit_audit(
                "responses_api_error",
                audit_id=audit_id,
                model=model,
                error_type=type(exc).__name__,
            )
            logger.exception("OpenAI GPT-5 responses invoke failed")
            raise self._transform_invoke_error(exc) from exc

    def _normalize_parameters(
        self,
        *,
        model: str,
        credentials: Mapping,
        model_parameters: Mapping[str, Any],
    ) -> dict[str, Any]:
        allowed = {
            "max_output_tokens",
            "reasoning_effort",
            "reasoning_summary",
            "verbosity",
            "response_format",
            "json_schema",
            "tool_choice",
            "parallel_tool_calls",
            "enable_stream",
        }

        try:
            filtered = self._validate_and_filter_model_parameters(
                model=model,
                model_parameters=dict(model_parameters),
                credentials=dict(credentials),
            )
            if filtered:
                return filtered
        except ValueError:
            # Fall back to minimal filtering to preserve API-compatible parameters
            pass

        return {k: v for k, v in model_parameters.items() if k in allowed}

    def _to_llm_result(
        self,
        *,
        model: str,
        credentials: Mapping,
        prompt_messages: list[PromptMessage],
        response: Any,
    ) -> LLMResult:
        output_text = extract_output_text(response)
        tool_calls = extract_tool_calls(response)

        converted_tool_calls: list[AssistantPromptMessage.ToolCall] = []
        for tool_call in tool_calls:
            converted_tool_calls.append(
                AssistantPromptMessage.ToolCall(
                    id=tool_call["id"],
                    type="function",
                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                        name=tool_call["name"],
                        arguments=tool_call["arguments"],
                    ),
                )
            )

        assistant_prompt_message = AssistantPromptMessage(
            content=output_text,
            tool_calls=converted_tool_calls,
        )

        usage = None
        usage_obj = getattr(response, "usage", None)
        if usage_obj is not None:
            prompt_tokens = int(getattr(usage_obj, "input_tokens", 0) or 0)
            completion_tokens = int(
                getattr(usage_obj, "output_tokens", 0) or 0
            )
            usage = self._calc_response_usage(
                model=model,
                credentials=dict(credentials),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        return LLMResult(
            model=str(getattr(response, "model", model)),
            prompt_messages=prompt_messages,
            message=assistant_prompt_message,
            usage=usage,
            system_fingerprint=None,
        )

    def _as_single_chunk_stream(
        self,
        llm_result: LLMResult,
        prompt_messages: list[PromptMessage],
    ) -> Generator[LLMResultChunk, None, None]:
        yield LLMResultChunk(
            model=llm_result.model,
            prompt_messages=prompt_messages,
            system_fingerprint=llm_result.system_fingerprint,
            delta=LLMResultChunkDelta(
                index=0,
                message=cast(AssistantPromptMessage, llm_result.message),
                finish_reason="stop",
                usage=llm_result.usage,
            ),
        )
