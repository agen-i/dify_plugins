import json
import logging
import os
import re
import time
from collections.abc import Generator, Mapping
from copy import deepcopy
from typing import Any, cast

from dify_plugin.entities.agent import AgentInvokeMessage
from dify_plugin.entities.model import ModelFeature
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResult,
    LLMResultChunk,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageContentType,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.entities.tool import ToolInvokeMessage, ToolProviderType
from dify_plugin.interfaces.agent import (
    AgentModelConfig,
    AgentStrategy,
    ToolEntity,
    ToolInvokeMeta,
)
from pydantic import BaseModel

try:
    from app.gpt5_agent_strategies.internal.flow import (
        build_round_prompt_messages,
        extract_blocking_tool_calls,
        extract_stream_tool_calls,
        should_emit_response_text,
    )
    from app.gpt5_agent_strategies.internal.tooling import (
        parse_tool_arguments,
        resolve_tool_instance,
    )
except ModuleNotFoundError:
    from internal.flow import (
        build_round_prompt_messages,
        extract_blocking_tool_calls,
        extract_stream_tool_calls,
        should_emit_response_text,
    )
    from internal.tooling import (
        parse_tool_arguments,
        resolve_tool_instance,
    )

logger = logging.getLogger(__name__)


class LogMetadata:
    """Metadata keys for logging"""

    STARTED_AT = "started_at"
    PROVIDER = "provider"
    FINISHED_AT = "finished_at"
    ELAPSED_TIME = "elapsed_time"
    TOTAL_PRICE = "total_price"
    CURRENCY = "currency"
    TOTAL_TOKENS = "total_tokens"


class ExecutionMetadata(BaseModel):
    """Execution metadata with default values"""

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

    @classmethod
    def from_llm_usage(cls, usage: LLMUsage | None) -> "ExecutionMetadata":
        """Create ExecutionMetadata from LLMUsage, handling None case"""
        if usage is None:
            return cls()

        return cls(
            total_price=float(usage.total_price),
            currency=usage.currency,
            total_tokens=usage.total_tokens,
            prompt_tokens=usage.prompt_tokens,
            prompt_unit_price=float(usage.prompt_unit_price),
            prompt_price_unit=float(usage.prompt_price_unit),
            prompt_price=float(usage.prompt_price),
            completion_tokens=usage.completion_tokens,
            completion_unit_price=float(usage.completion_unit_price),
            completion_price_unit=float(usage.completion_price_unit),
            completion_price=float(usage.completion_price),
            latency=usage.latency,
        )


class ContextItem(BaseModel):
    content: str
    title: str
    metadata: dict[str, Any]


class GPT5FunctionCallingParams(BaseModel):
    query: str
    instruction: str | None
    prompt_policy_overrides: str | None = None
    model: AgentModelConfig
    tools: list[ToolEntity] | None
    maximum_iterations: int = 3
    invocation_timeout_seconds: int = 1200
    emit_intermediate_thoughts: bool = False
    allow_schemaless_tool_args: bool = False
    context: list[ContextItem] | None = None


class GPT5FunctionCallingStrategy(AgentStrategy):
    _LOCAL_FILE_ROOT = "/files"
    _MAX_BLOB_FILE_BYTES = 5 * 1024 * 1024
    _TOOL_INVOKE_ERROR_MESSAGE = "tool invoke error: failed to execute tool"
    _REPEATED_TOOL_INVOKE_ERROR_MESSAGE = (
        "tool invoke error: repeated failure detected; skipped duplicate call"
    )
    _VERBOSE_LOG_ENV = "GPT5_AGENT_VERBOSE_LOGGING"
    _VERBOSE_LOG_PREVIEW_ENV = "GPT5_AGENT_VERBOSE_LOG_PREVIEW"
    _SCHEMELESS_OVERRIDE_ENV = "GPT5_AGENT_ALLOW_SCHEMELESS_OVERRIDE"
    _MAX_SCHEMELESS_ARG_KEYS = 16
    _MAX_SCHEMELESS_ARG_KEY_CHARS = 64
    _MAX_SCHEMELESS_ARG_VALUE_CHARS = 2048
    _SENSITIVE_LOG_KEYS = {
        "token",
        "secret",
        "authorization",
        "password",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "credential",
    }

    query: str = ""
    instruction: str | None = ""
    prompt_policy_overrides: str | None = None

    @property
    def _user_prompt_message(self) -> UserPromptMessage:
        return UserPromptMessage(content=self.query)

    @property
    def _system_prompt_message(self) -> SystemPromptMessage:
        try:
            from app.gpt5_agent_strategies.internal.policy import (
                build_system_instruction,
            )
        except ModuleNotFoundError:
            from internal.policy import (
                build_system_instruction,
            )

        return SystemPromptMessage(
            content=build_system_instruction(
                self.instruction or "",
                self.prompt_policy_overrides,
            )
        )

    def _invoke(
        self, parameters: dict[str, Any]
    ) -> Generator[AgentInvokeMessage, None, None]:
        """
        Run FunctionCall agent application
        """
        fc_params = GPT5FunctionCallingParams(**parameters)

        # init prompt messages
        query = fc_params.query
        self.query = query
        self.instruction = fc_params.instruction
        self.prompt_policy_overrides = fc_params.prompt_policy_overrides
        history_prompt_messages = build_round_prompt_messages(
            history_prompt_messages=fc_params.model.history_prompt_messages,
            system_message=self._system_prompt_message,
            user_message=self._user_prompt_message,
        )

        # convert tool messages
        tools = fc_params.tools
        tool_instances = (
            {tool.identity.name: tool for tool in tools} if tools else {}
        )
        prompt_messages_tools = self._init_prompt_tools(tools)

        # init model parameters
        stream = (
            ModelFeature.STREAM_TOOL_CALL in fc_params.model.entity.features
            if fc_params.model.entity and fc_params.model.entity.features
            else False
        )
        model = fc_params.model
        stop = (
            fc_params.model.completion_params.get("stop", [])
            if fc_params.model.completion_params
            else []
        )
        invocation_timeout_seconds = max(
            60, min(1800, int(fc_params.invocation_timeout_seconds))
        )
        if getattr(self, "session", None) is not None:
            self.session.max_invocation_timeout = invocation_timeout_seconds
        emit_intermediate_thoughts = fc_params.emit_intermediate_thoughts
        requested_schemaless_override = fc_params.allow_schemaless_tool_args
        allow_schemaless_tool_args = (
            requested_schemaless_override
            and self._is_schemaless_override_enabled()
        )
        if requested_schemaless_override and not allow_schemaless_tool_args:
            self._emit_security_event(
                "compat_mode_blocked",
                reason="override_env_missing_or_disabled",
                env=self._SCHEMELESS_OVERRIDE_ENV,
            )
        elif allow_schemaless_tool_args:
            self._emit_security_event(
                "compat_mode_enabled",
                env=self._SCHEMELESS_OVERRIDE_ENV,
            )

        # init function calling state
        iteration_step = 1
        max_iteration_steps = fc_params.maximum_iterations
        current_thoughts: list[PromptMessage] = []
        function_call_state = (
            True  # continue to run until there is not any tool call
        )
        llm_usage: dict[str, LLMUsage | None] = {"usage": None}
        final_answer = ""
        failed_tool_invocations: dict[tuple[str, str], str] = {}

        while function_call_state and iteration_step <= max_iteration_steps:
            # start a new round
            function_call_state = False
            round_started_at = time.perf_counter()
            round_log = self.create_log_message(
                label=f"ROUND {iteration_step}",
                data={},
                metadata={
                    LogMetadata.STARTED_AT: round_started_at,
                },
                status=ToolInvokeMessage.LogMessage.LogStatus.START,
            )
            yield round_log

            # recalc llm max tokens
            prompt_messages = self._organize_prompt_messages(
                history_prompt_messages=history_prompt_messages,
                current_thoughts=current_thoughts,
                model=model,
            )
            if model.entity and model.completion_params:
                self.recalc_llm_max_tokens(
                    model.entity, prompt_messages, model.completion_params
                )
            # invoke model
            model_started_at = time.perf_counter()
            model_log = self.create_log_message(
                label=f"{model.model} Thought",
                data={},
                metadata={
                    LogMetadata.STARTED_AT: model_started_at,
                    LogMetadata.PROVIDER: model.provider,
                },
                parent=round_log,
                status=ToolInvokeMessage.LogMessage.LogStatus.START,
            )
            yield model_log
            model_config = LLMModelConfig(**model.model_dump(mode="json"))
            chunks: Generator[LLMResultChunk, None, None] | LLMResult = (
                self.session.model.llm.invoke(
                    model_config=model_config,
                    prompt_messages=prompt_messages,
                    stop=stop,
                    stream=stream,
                    tools=prompt_messages_tools,
                )
            )

            tool_calls: list[tuple[str, str, dict[str, Any], str | None]] = []

            # save full response
            response = ""

            # save tool call names and inputs
            tool_call_names = ""

            current_llm_usage = None

            if isinstance(chunks, Generator):
                stream_text_fragments: list[str] = []
                deferred_stream_text_fragments: list[str] = []
                stream_text_emitted = False
                for chunk in chunks:
                    chunk_text_fragments: list[str] = []
                    # check if there is any tool call
                    if self.check_tool_calls(chunk):
                        function_call_state = True
                        tool_calls = self._merge_tool_calls(
                            tool_calls, self.extract_tool_calls(chunk) or []
                        )
                        tool_call_names = ";".join(
                            [tool_call[1] for tool_call in tool_calls]
                        )

                    if chunk.delta.message and chunk.delta.message.content:
                        if isinstance(chunk.delta.message.content, list):
                            for content in chunk.delta.message.content:
                                text_piece = str(content.data or "")
                                if not text_piece:
                                    continue
                                response += text_piece
                                stream_text_fragments.append(text_piece)
                                chunk_text_fragments.append(text_piece)
                        else:
                            chunk_text = str(chunk.delta.message.content)
                            if chunk_text:
                                response += chunk_text
                                stream_text_fragments.append(chunk_text)
                                chunk_text_fragments.append(chunk_text)

                    if chunk.delta.usage:
                        self.increase_usage(llm_usage, chunk.delta.usage)
                        current_llm_usage = chunk.delta.usage

                    if chunk_text_fragments and not function_call_state:
                        if emit_intermediate_thoughts:
                            for text_piece in chunk_text_fragments:
                                yield self.create_text_message(text_piece)
                            stream_text_emitted = True
                        else:
                            deferred_stream_text_fragments.extend(
                                chunk_text_fragments
                            )
                    elif chunk_text_fragments:
                        deferred_stream_text_fragments.extend(
                            chunk_text_fragments
                        )

                if should_emit_response_text(
                    has_tool_calls=bool(tool_calls),
                    iteration_step=iteration_step,
                    max_iteration_steps=max_iteration_steps,
                    emit_intermediate_thoughts=emit_intermediate_thoughts,
                ):
                    if tool_calls:
                        if emit_intermediate_thoughts:
                            if deferred_stream_text_fragments:
                                stream_text = "".join(
                                    deferred_stream_text_fragments
                                )
                                stream_text = self._format_thought_block(
                                    stream_text
                                )
                                yield self.create_text_message(stream_text)
                            elif (
                                not stream_text_emitted
                                and stream_text_fragments
                            ):
                                stream_text = "".join(stream_text_fragments)
                                stream_text = self._format_thought_block(
                                    stream_text
                                )
                                yield self.create_text_message(stream_text)
                            elif not stream_text_emitted:
                                yield self.create_text_message(
                                    self._fallback_tool_call_thought(
                                        tool_calls
                                    )
                                )
                        elif not stream_text_emitted:
                            stream_text = "".join(
                                deferred_stream_text_fragments
                                or stream_text_fragments
                            )
                            visible_text = (
                                self._strip_think_blocks_for_display(
                                    stream_text
                                )
                            )
                            if visible_text:
                                yield self.create_text_message(visible_text)
                    elif stream_text_fragments and not stream_text_emitted:
                        if emit_intermediate_thoughts:
                            for text_piece in stream_text_fragments:
                                yield self.create_text_message(text_piece)
                        else:
                            stream_text = "".join(
                                deferred_stream_text_fragments
                                or stream_text_fragments
                            )
                            visible_text = (
                                self._strip_think_blocks_for_display(
                                    stream_text
                                )
                            )
                            if visible_text:
                                yield self.create_text_message(visible_text)

            else:
                result = chunks
                result = cast(LLMResult, result)
                # check if there is any tool call
                if self.check_blocking_tool_calls(result):
                    function_call_state = True
                    tool_calls = self._merge_tool_calls(
                        tool_calls,
                        self.extract_blocking_tool_calls(result) or [],
                    )
                    tool_call_names = ";".join(
                        [tool_call[1] for tool_call in tool_calls]
                    )

                if result.usage:
                    self.increase_usage(llm_usage, result.usage)
                    current_llm_usage = result.usage

                result_message = result.message
                if result.message and result.message.content:
                    if isinstance(result.message.content, list):
                        for content in result.message.content:
                            response += content.data
                    else:
                        response += str(result.message.content)

                if result_message is not None and not result_message.content:
                    result_message.content = ""
                emitted_result_text = False
                if result_message is not None and should_emit_response_text(
                    has_tool_calls=bool(tool_calls),
                    iteration_step=iteration_step,
                    max_iteration_steps=max_iteration_steps,
                    emit_intermediate_thoughts=emit_intermediate_thoughts,
                ):
                    if isinstance(result_message.content, str):
                        if result_message.content:
                            text = result_message.content
                            if tool_calls:
                                if emit_intermediate_thoughts:
                                    text = self._format_thought_block(text)
                                else:
                                    text = (
                                        self._strip_think_blocks_for_display(
                                            text
                                        )
                                    )
                            elif not emit_intermediate_thoughts:
                                text = self._strip_think_blocks_for_display(
                                    text
                                )
                            if text:
                                yield self.create_text_message(text)
                                emitted_result_text = True
                    elif isinstance(result_message.content, list):
                        list_texts: list[str] = []
                        for content in result_message.content:
                            text = str(getattr(content, "data", "") or "")
                            if not text:
                                continue
                            list_texts.append(text)
                        if list_texts:
                            if tool_calls:
                                if emit_intermediate_thoughts:
                                    emitted_result_text = True
                                    yield self.create_text_message(
                                        self._format_thought_block(
                                            "\n".join(list_texts)
                                        )
                                    )
                                else:
                                    visible_text = (
                                        self._strip_think_blocks_for_display(
                                            "\n".join(list_texts)
                                        )
                                    )
                                    if visible_text:
                                        emitted_result_text = True
                                        yield self.create_text_message(
                                            visible_text
                                        )
                            elif emit_intermediate_thoughts:
                                emitted_result_text = True
                                for text in list_texts:
                                    yield self.create_text_message(text)
                            else:
                                for text in list_texts:
                                    visible_text = (
                                        self._strip_think_blocks_for_display(
                                            text
                                        )
                                    )
                                    if not visible_text:
                                        continue
                                    emitted_result_text = True
                                    yield self.create_text_message(
                                        visible_text
                                    )

                    if (
                        not emitted_result_text
                        and tool_calls
                        and emit_intermediate_thoughts
                    ):
                        yield self.create_text_message(
                            self._fallback_tool_call_thought(tool_calls)
                        )

            yield self.finish_log_message(
                log=model_log,
                data=self._build_model_log_data(
                    response=response,
                    tool_call_names=tool_call_names,
                    tool_calls=tool_calls,
                ),
                metadata={
                    LogMetadata.STARTED_AT: model_started_at,
                    LogMetadata.FINISHED_AT: time.perf_counter(),
                    LogMetadata.ELAPSED_TIME: time.perf_counter()
                    - model_started_at,
                    LogMetadata.PROVIDER: model.provider,
                    LogMetadata.TOTAL_PRICE: (
                        current_llm_usage.total_price
                        if current_llm_usage
                        else 0
                    ),
                    LogMetadata.CURRENCY: (
                        current_llm_usage.currency if current_llm_usage else ""
                    ),
                    LogMetadata.TOTAL_TOKENS: (
                        current_llm_usage.total_tokens
                        if current_llm_usage
                        else 0
                    ),
                },
            )

            # If there are tool calls, merge all tool calls into
            # a single assistant message.
            if tool_calls:
                tool_call_objects = [
                    AssistantPromptMessage.ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                            name=tool_call_name,
                            arguments=json.dumps(
                                tool_call_args, ensure_ascii=False
                            ),
                        ),
                    )
                    for (
                        tool_call_id,
                        tool_call_name,
                        tool_call_args,
                        _parse_error,
                    ) in tool_calls
                ]
                assistant_message = AssistantPromptMessage(
                    content=response,  # Preserve LLM returned content, even if empty
                    tool_calls=tool_call_objects,
                )
                current_thoughts.append(assistant_message)
            elif response.strip():
                # If no tool calls but has response, add a regular assistant message
                assistant_message = AssistantPromptMessage(
                    content=response, tool_calls=[]
                )
                current_thoughts.append(assistant_message)

            final_answer += response + "\n"

            # call tools
            tool_responses = []
            # Check if max iterations reached.
            # Allow tool calls when max_iteration_steps == 1.
            if (
                tool_calls
                and iteration_step == max_iteration_steps
                and max_iteration_steps > 1
            ):
                # Max iterations reached, return message instead of calling tools
                for (
                    tool_call_id,
                    tool_call_name,
                    tool_call_args,
                    _parse_error,
                ) in tool_calls:
                    # Create log entry for the skipped tool call
                    tool_call_started_at = time.perf_counter()
                    tool_call_log = self.create_log_message(
                        label=f"CALL {tool_call_name}",
                        data={},
                        metadata={
                            LogMetadata.STARTED_AT: time.perf_counter(),
                            LogMetadata.PROVIDER: (
                                tool_instances[
                                    tool_call_name
                                ].identity.provider
                                if tool_instances.get(tool_call_name)
                                else ""
                            ),
                        },
                        parent=round_log,
                        status=ToolInvokeMessage.LogMessage.LogStatus.START,
                    )
                    yield tool_call_log

                    # Return error message instead of calling tool
                    tool_response = {
                        "tool_call_id": tool_call_id,
                        "tool_call_name": tool_call_name,
                        "tool_response": (
                            f"Maximum iteration limit ({max_iteration_steps}) reached. "
                            f"Cannot call tool '{tool_call_name}'. "
                            f"Please consider increasing the iteration limit."
                        ),
                    }
                    tool_responses.append(tool_response)

                    yield self.finish_log_message(
                        log=tool_call_log,
                        data={"output": tool_response},
                        metadata={
                            LogMetadata.STARTED_AT: tool_call_started_at,
                            LogMetadata.PROVIDER: (
                                tool_instances[
                                    tool_call_name
                                ].identity.provider
                                if tool_instances.get(tool_call_name)
                                else ""
                            ),
                            LogMetadata.FINISHED_AT: time.perf_counter(),
                            LogMetadata.ELAPSED_TIME: time.perf_counter()
                            - tool_call_started_at,
                        },
                    )

                    # Add to current_thoughts for context
                    current_thoughts.append(
                        AssistantPromptMessage(
                            content="",
                            tool_calls=[
                                AssistantPromptMessage.ToolCall(
                                    id=tool_call_id,
                                    type="function",
                                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                                        name=tool_call_name,
                                        arguments=json.dumps(
                                            tool_call_args, ensure_ascii=False
                                        ),
                                    ),
                                )
                            ],
                        )
                    )
                    current_thoughts.append(
                        ToolPromptMessage(
                            content=tool_response["tool_response"],
                            tool_call_id=tool_call_id,
                            name=tool_call_name,
                        )
                    )
            else:
                for (
                    tool_call_id,
                    tool_call_name,
                    tool_call_args,
                    parse_error,
                ) in tool_calls:
                    tool_instance = resolve_tool_instance(
                        tool_instances, tool_call_name
                    )
                    tool_provider = (
                        tool_instance.identity.provider
                        if tool_instance
                        else ""
                    )
                    tool_call_started_at = time.perf_counter()
                    tool_call_log = self.create_log_message(
                        label=f"CALL {tool_call_name}",
                        data={},
                        metadata={
                            LogMetadata.STARTED_AT: time.perf_counter(),
                            LogMetadata.PROVIDER: tool_provider,
                        },
                        parent=round_log,
                        status=ToolInvokeMessage.LogMessage.LogStatus.START,
                    )
                    yield tool_call_log
                    if parse_error:
                        parse_error_message = (
                            f"tool arguments parse error: {parse_error}"
                        )
                        tool_response = {
                            "tool_call_id": tool_call_id,
                            "tool_call_name": tool_call_name,
                            "tool_response": parse_error_message,
                            "meta": ToolInvokeMeta.error_instance(
                                parse_error_message
                            ).to_dict(),
                        }
                    elif not tool_instance:
                        tool_not_found = (
                            f"there is not a tool named {tool_call_name}"
                        )
                        tool_response = {
                            "tool_call_id": tool_call_id,
                            "tool_call_name": tool_call_name,
                            "tool_response": tool_not_found,
                            "meta": ToolInvokeMeta.error_instance(
                                tool_not_found
                            ).to_dict(),
                        }
                    else:
                        # invoke tool
                        normalized_tool_input, validation_error = (
                            self._normalize_tool_invoke_parameters(
                                tool_instance=tool_instance,
                                runtime_parameters=dict(
                                    getattr(
                                        tool_instance,
                                        "runtime_parameters",
                                        {},
                                    )
                                    or {}
                                ),
                                tool_call_args=dict(tool_call_args),
                                allow_schemaless_tool_args=(
                                    allow_schemaless_tool_args
                                ),
                            )
                        )
                        tool_signature = self._tool_invocation_signature(
                            tool_call_name, normalized_tool_input
                        )
                        try:
                            if validation_error:
                                tool_result = validation_error
                                tool_response = {
                                    "tool_call_id": tool_call_id,
                                    "tool_call_name": tool_call_name,
                                    "tool_call_input": normalized_tool_input,
                                    "tool_response": tool_result,
                                    "meta": ToolInvokeMeta.error_instance(
                                        validation_error
                                    ).to_dict(),
                                }
                            elif tool_signature in failed_tool_invocations:
                                tool_result = failed_tool_invocations[
                                    tool_signature
                                ]
                                tool_response = {
                                    "tool_call_id": tool_call_id,
                                    "tool_call_name": tool_call_name,
                                    "tool_call_input": normalized_tool_input,
                                    "tool_response": (
                                        self._REPEATED_TOOL_INVOKE_ERROR_MESSAGE
                                    ),
                                    "meta": ToolInvokeMeta.error_instance(
                                        tool_result
                                    ).to_dict(),
                                }
                            else:
                                tool_invoke_responses = self.session.tool.invoke(
                                    provider_type=ToolProviderType(
                                        tool_instance.provider_type
                                    ),
                                    provider=tool_instance.identity.provider,
                                    tool_name=tool_instance.identity.name,
                                    parameters=normalized_tool_input,
                                )
                                tool_result = ""
                                for (
                                    tool_invoke_response
                                ) in tool_invoke_responses:
                                    if (
                                        tool_invoke_response.type
                                        == ToolInvokeMessage.MessageType.TEXT
                                    ):
                                        tool_result += cast(
                                            ToolInvokeMessage.TextMessage,
                                            tool_invoke_response.message,
                                        ).text
                                    elif (
                                        tool_invoke_response.type
                                        == ToolInvokeMessage.MessageType.LINK
                                    ):
                                        tool_result += (
                                            "result link: "
                                            + cast(
                                                ToolInvokeMessage.TextMessage,
                                                tool_invoke_response.message,
                                            ).text
                                            + "."
                                            + " please tell user to check it."
                                        )
                                    elif tool_invoke_response.type in {
                                        ToolInvokeMessage.MessageType.IMAGE_LINK,
                                        ToolInvokeMessage.MessageType.IMAGE,
                                    }:
                                        # Extract file path or URL from the message.
                                        if hasattr(
                                            tool_invoke_response.message,
                                            "text",
                                        ):
                                            file_info = cast(
                                                ToolInvokeMessage.TextMessage,
                                                tool_invoke_response.message,
                                            ).text
                                            # Try to create a blob response from file.
                                            try:
                                                read_local_file = (
                                                    self._read_local_file_for_blob
                                                )
                                                local_file = read_local_file(
                                                    file_info
                                                )
                                                if local_file is not None:
                                                    file_content, filename = (
                                                        local_file
                                                    )
                                                    blob = self.create_blob_message(
                                                        blob=file_content,
                                                        meta={
                                                            "mime_type": (
                                                                "image/png"
                                                            ),
                                                            "filename": filename,
                                                        },
                                                    )
                                                    yield blob
                                            except Exception:
                                                logger.exception(
                                                    "Failed to create blob message "
                                                    "from local image output"
                                                )
                                                yield self.create_text_message(
                                                    "Failed to process generated "
                                                    "image file."
                                                )
                                        tool_result += (
                                            "image generated and sent to user. "
                                            "Tell user to review it now."
                                        )
                                        yield self._to_agent_invoke_message(
                                            tool_invoke_response
                                        )
                                    elif (
                                        tool_invoke_response.type
                                        == ToolInvokeMessage.MessageType.JSON
                                    ):
                                        text = json.dumps(
                                            cast(
                                                ToolInvokeMessage.JsonMessage,
                                                tool_invoke_response.message,
                                            ).json_object,
                                            ensure_ascii=False,
                                        )
                                        tool_result += (
                                            f"tool response: {text}."
                                        )
                                    elif (
                                        tool_invoke_response.type
                                        == ToolInvokeMessage.MessageType.BLOB
                                    ):
                                        tool_result += "Generated file ... "
                                        yield self._to_agent_invoke_message(
                                            tool_invoke_response
                                        )
                                    else:
                                        response_repr = repr(
                                            tool_invoke_response.message
                                        )
                                        tool_result += (
                                            f"tool response: {response_repr}."
                                        )
                                tool_response = {
                                    "tool_call_id": tool_call_id,
                                    "tool_call_name": tool_call_name,
                                    "tool_call_input": normalized_tool_input,
                                    "tool_response": tool_result,
                                }
                        except Exception:
                            logger.exception(
                                "Tool invoke failed: tool=%s", tool_call_name
                            )
                            tool_result = self._TOOL_INVOKE_ERROR_MESSAGE
                            failed_tool_invocations[tool_signature] = (
                                tool_result
                            )
                            tool_response = {
                                "tool_call_id": tool_call_id,
                                "tool_call_name": tool_call_name,
                                "tool_call_input": normalized_tool_input,
                                "tool_response": tool_result,
                            }

                    yield self.finish_log_message(
                        log=tool_call_log,
                        data=self._build_tool_call_log_data(tool_response),
                        metadata={
                            LogMetadata.STARTED_AT: tool_call_started_at,
                            LogMetadata.PROVIDER: tool_provider,
                            LogMetadata.FINISHED_AT: time.perf_counter(),
                            LogMetadata.ELAPSED_TIME: time.perf_counter()
                            - tool_call_started_at,
                        },
                    )
                    tool_responses.append(tool_response)
                    if tool_response["tool_response"] is not None:
                        current_thoughts.append(
                            ToolPromptMessage(
                                content=str(tool_response["tool_response"]),
                                tool_call_id=tool_call_id,
                                name=tool_call_name,
                            )
                        )
            # Insert blank line so the next assistant thought
            # appears on a new line in the user interface.
            if tool_calls:
                yield self.create_text_message("\n")

            # update prompt tool
            for prompt_tool in prompt_messages_tools:
                self.update_prompt_message_tool(
                    tool_instances[prompt_tool.name], prompt_tool
                )
            yield self.finish_log_message(
                log=round_log,
                data=self._build_round_log_data(
                    llm_response=response,
                    tool_responses=tool_responses,
                ),
                metadata={
                    LogMetadata.STARTED_AT: round_started_at,
                    LogMetadata.FINISHED_AT: time.perf_counter(),
                    LogMetadata.ELAPSED_TIME: time.perf_counter()
                    - round_started_at,
                    LogMetadata.TOTAL_PRICE: (
                        current_llm_usage.total_price
                        if current_llm_usage
                        else 0
                    ),
                    LogMetadata.CURRENCY: (
                        current_llm_usage.currency if current_llm_usage else ""
                    ),
                    LogMetadata.TOTAL_TOKENS: (
                        current_llm_usage.total_tokens
                        if current_llm_usage
                        else 0
                    ),
                },
            )
            # If max_iteration_steps=1, need to return tool responses
            if tool_responses and max_iteration_steps == 1:
                for resp in tool_responses:
                    yield self.create_text_message(str(resp["tool_response"]))
            iteration_step += 1

        # If context is a list of dict, create retriever resource message
        if isinstance(fc_params.context, list):
            yield self.create_retriever_resource_message(
                retriever_resources=[
                    ToolInvokeMessage.RetrieverResourceMessage.RetrieverResource(
                        content=ctx.content,
                        position=ctx.metadata.get("position"),
                        dataset_id=ctx.metadata.get("dataset_id"),
                        dataset_name=ctx.metadata.get("dataset_name"),
                        document_id=ctx.metadata.get("document_id"),
                        document_name=ctx.metadata.get("document_name"),
                        data_source_type=ctx.metadata.get(
                            "document_data_source_type"
                        ),
                        segment_id=ctx.metadata.get("segment_id"),
                        retriever_from=ctx.metadata.get("retriever_from"),
                        score=ctx.metadata.get("score"),
                        hit_count=ctx.metadata.get("segment_hit_count"),
                        word_count=ctx.metadata.get("segment_word_count"),
                        segment_position=ctx.metadata.get("segment_position"),
                        index_node_hash=ctx.metadata.get(
                            "segment_index_node_hash"
                        ),
                        page=ctx.metadata.get("page"),
                        doc_metadata=ctx.metadata.get("doc_metadata"),
                    )
                    for ctx in fc_params.context
                ],
                context="",
            )

        metadata = ExecutionMetadata.from_llm_usage(llm_usage["usage"])
        yield self.create_json_message(
            {"execution_metadata": metadata.model_dump()}
        )

    def check_tool_calls(self, llm_result_chunk: LLMResultChunk) -> bool:
        """
        Check if there is any tool call in llm result chunk
        """
        return bool(extract_stream_tool_calls(llm_result_chunk))

    def check_blocking_tool_calls(self, llm_result: LLMResult) -> bool:
        """
        Check if there is any blocking tool call in llm result
        """
        return bool(extract_blocking_tool_calls(llm_result))

    def _merge_tool_calls(
        self,
        existing: list[tuple[str, str, dict[str, Any], str | None]],
        incoming: list[tuple[str, str, dict[str, Any], str | None]],
    ) -> list[tuple[str, str, dict[str, Any], str | None]]:
        merged = list(existing)
        index_by_id = {tool_call[0]: i for i, tool_call in enumerate(merged)}
        for tool_call in incoming:
            tool_call_id = tool_call[0]
            if tool_call_id in index_by_id:
                merged[index_by_id[tool_call_id]] = tool_call
                continue
            index_by_id[tool_call_id] = len(merged)
            merged.append(tool_call)
        return merged

    def _fallback_tool_call_thought(
        self, tool_calls: list[tuple[str, str, dict[str, Any], str | None]]
    ) -> str:
        tool_names: list[str] = []
        for (
            _tool_call_id,
            tool_call_name,
            _tool_call_args,
            _parse_error,
        ) in tool_calls:
            if not tool_call_name:
                continue
            if tool_call_name in tool_names:
                continue
            tool_names.append(tool_call_name)

        if not tool_names:
            return "<think>\nまず、必要な情報を確認して進めます。\n</think>"
        if len(tool_names) == 1:
            return (
                "<think>\n"
                f"まず、{tool_names[0]} ツールで必要な情報を確認します。\n"
                "</think>"
            )

        preview = ", ".join(tool_names[:3])
        suffix = "..." if len(tool_names) > 3 else ""
        return (
            "<think>\n"
            "必要な情報を得るため、次のツールを順に確認します: "
            f"{preview}{suffix}\n"
            "</think>"
        )

    @staticmethod
    def _looks_like_think_block(text: str) -> bool:
        stripped = text.strip()
        return stripped.startswith("<think>") and stripped.endswith("</think>")

    def _format_thought_block(self, text: str) -> str:
        normalized = self._normalize_thought_text(text)
        if self._looks_like_think_block(normalized):
            return normalized
        return f"<think>\n{normalized}\n</think>"

    @staticmethod
    def _strip_think_blocks_for_display(text: str) -> str:
        if not text:
            return ""

        without_think_blocks = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        without_dangling_opening = re.sub(
            r"<think>.*$",
            "",
            without_think_blocks,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(
            r"</think>",
            "",
            without_dangling_opening,
            flags=re.IGNORECASE,
        )
        return cleaned if cleaned.strip() else ""

    @staticmethod
    def _normalize_thought_text(text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return "まず、必要な情報を確認して進めます。"

        for prefix in (
            "意図：",
            "意図:",
            "Intent:",
            "intent:",
            "Thinking:",
            "thinking:",
        ):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].strip()
                break

        return normalized or "まず、必要な情報を確認して進めます。"

    def _is_verbose_logging_enabled(self) -> bool:
        raw = str(os.getenv(self._VERBOSE_LOG_ENV, "") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _is_schemaless_override_enabled(self) -> bool:
        raw = str(os.getenv(self._SCHEMELESS_OVERRIDE_ENV, "") or "").strip()
        return raw.lower() in {"1", "true", "yes", "on"}

    def _emit_security_event(self, event_type: str, **payload: Any) -> None:
        event_payload = {"event": event_type, **payload}
        logger.warning(
            "security_event %s",
            json.dumps(event_payload, ensure_ascii=False, sort_keys=True),
        )

    def _is_verbose_preview_enabled(self) -> bool:
        raw = str(os.getenv(self._VERBOSE_LOG_PREVIEW_ENV, "") or "").strip()
        return raw.lower() in {"1", "true", "yes", "on"}

    def _is_sensitive_log_key(self, key: str) -> bool:
        normalized = key.lower()
        return any(token in normalized for token in self._SENSITIVE_LOG_KEYS)

    @staticmethod
    def _truncate_text(text: str, max_chars: int = 160) -> str:
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars]}..."

    def _sanitize_for_log(self, value: Any, *, key: str = "") -> Any:
        if key and self._is_sensitive_log_key(key):
            return "***REDACTED***"

        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for item_key, item_value in value.items():
                key_str = str(item_key)
                sanitized[key_str] = self._sanitize_for_log(
                    item_value, key=key_str
                )
            return sanitized

        if isinstance(value, (list, tuple, set)):
            return [self._sanitize_for_log(item) for item in value]

        if isinstance(value, str):
            sanitized: dict[str, Any] = {"chars": len(value)}
            if self._is_verbose_preview_enabled():
                sanitized["preview"] = self._truncate_text(value)
            return sanitized

        return value

    @staticmethod
    def _tool_input_summary(
        tool_calls: list[tuple[str, str, dict[str, Any], str | None]],
    ) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for _tool_call_id, tool_name, tool_args, _parse_error in tool_calls:
            arg_keys = sorted(str(key) for key in tool_args.keys())
            summaries.append(
                {
                    "name": tool_name,
                    "arg_count": len(arg_keys),
                    "arg_keys": arg_keys,
                }
            )
        return summaries

    def _tool_response_summary(
        self, tool_responses: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []
        for response in tool_responses:
            text = str(response.get("tool_response") or "")
            has_meta_error = isinstance(
                response.get("meta"), Mapping
            ) and bool(response["meta"].get("error"))
            has_known_error_text = (
                text.startswith("tool invoke error")
                or "validation error" in text
            )
            summary.append(
                {
                    "tool_call_name": str(
                        response.get("tool_call_name") or ""
                    ),
                    "response_chars": len(text),
                    "is_error": has_meta_error or has_known_error_text,
                }
            )
        return summary

    def _build_model_log_data(
        self,
        *,
        response: str,
        tool_call_names: list[str],
        tool_calls: list[tuple[str, str, dict[str, Any], str | None]],
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "output_summary": {
                "response_chars": len(response),
                "tool_call_count": len(tool_calls),
            },
            "tool_name": list(tool_call_names),
            "tool_input_summary": self._tool_input_summary(tool_calls),
        }
        if self._is_verbose_logging_enabled():
            data["debug_output"] = self._sanitize_for_log(
                {
                    "response": response,
                    "tool_input": [
                        {"name": tool_call[1], "args": tool_call[2]}
                        for tool_call in tool_calls
                    ],
                }
            )
        return data

    def _build_round_log_data(
        self, *, llm_response: str, tool_responses: list[dict[str, Any]]
    ) -> dict[str, Any]:
        tool_summary = self._tool_response_summary(tool_responses)
        data: dict[str, Any] = {
            "output_summary": {
                "llm_response_chars": len(llm_response),
                "tool_response_count": len(tool_responses),
                "tool_error_count": sum(
                    1 for item in tool_summary if item["is_error"]
                ),
            },
            "tool_responses_summary": tool_summary,
        }
        if self._is_verbose_logging_enabled():
            data["debug_output"] = self._sanitize_for_log(
                {
                    "llm_response": llm_response,
                    "tool_responses": tool_responses,
                }
            )
        return data

    def _build_tool_call_log_data(
        self, tool_response: dict[str, Any]
    ) -> dict[str, Any]:
        response_text = str(tool_response.get("tool_response") or "")
        has_meta_error = isinstance(
            tool_response.get("meta"), Mapping
        ) and bool(tool_response["meta"].get("error"))
        data: dict[str, Any] = {
            "output_summary": {
                "tool_call_id": str(tool_response.get("tool_call_id") or ""),
                "tool_call_name": str(
                    tool_response.get("tool_call_name") or ""
                ),
                "response_chars": len(response_text),
                "is_error": has_meta_error
                or response_text.startswith("tool invoke error")
                or "validation error" in response_text,
            }
        }
        if self._is_verbose_logging_enabled():
            data["debug_output"] = self._sanitize_for_log(tool_response)
        return data

    def _normalize_tool_invoke_parameters(
        self,
        tool_instance: ToolEntity,
        runtime_parameters: dict[str, Any],
        tool_call_args: dict[str, Any],
        allow_schemaless_tool_args: bool = False,
    ) -> tuple[dict[str, Any], str | None]:
        normalized = {
            **runtime_parameters,
            **tool_call_args,
        }
        parameter_defs = {
            str(getattr(parameter, "name", "") or ""): parameter
            for parameter in getattr(tool_instance, "parameters", []) or []
            if str(getattr(parameter, "name", "") or "")
        }

        if (
            not parameter_defs
            and tool_call_args
            and not allow_schemaless_tool_args
        ):
            tool_name = self._tool_instance_name(tool_instance)
            self._emit_security_event(
                "tool_schema_missing_blocked",
                tool_name=tool_name,
                arg_keys=sorted(str(key) for key in tool_call_args.keys()),
                arg_count=len(tool_call_args),
            )
            return (
                normalized,
                (
                    "tool arguments validation error: schema is required "
                    f"for tool '{tool_name}'"
                ),
            )

        if (
            not parameter_defs
            and tool_call_args
            and allow_schemaless_tool_args
        ):
            tool_name = self._tool_instance_name(tool_instance)
            schemaless_error = self._validate_schemaless_tool_args(
                tool_name=tool_name,
                tool_call_args=tool_call_args,
            )
            if schemaless_error is not None:
                return normalized, schemaless_error

        if parameter_defs:
            unknown_keys = sorted(
                str(key)
                for key in tool_call_args
                if str(key) not in parameter_defs
            )
            if unknown_keys:
                return (
                    normalized,
                    (
                        "tool arguments validation error: unknown parameters "
                        f"{unknown_keys}"
                    ),
                )

        for parameter_name, parameter in parameter_defs.items():
            required = bool(getattr(parameter, "required", False))
            if parameter_name not in normalized:
                if required:
                    return (
                        normalized,
                        (
                            "tool arguments validation error: missing required "
                            f"parameter '{parameter_name}'"
                        ),
                    )
                continue

            raw_value = normalized[parameter_name]
            normalized_value, type_error = self._coerce_parameter_value(
                parameter_name=parameter_name,
                parameter=parameter,
                raw_value=raw_value,
            )
            if type_error:
                return normalized, type_error

            normalized[parameter_name] = normalized_value

            options = self._parameter_option_values(parameter)
            if not options:
                continue

            raw_value = normalized[parameter_name]
            normalized_value = (
                "true"
                if isinstance(raw_value, bool) and raw_value
                else "false" if isinstance(raw_value, bool) else str(raw_value)
            )

            if normalized_value not in options:
                return (
                    normalized,
                    (
                        f"tool arguments validation error: parameter "
                        f"'{parameter_name}' value {raw_value!r} "
                        f"not in options {options}"
                    ),
                )

            normalized[parameter_name] = normalized_value

        return normalized, None

    def _tool_instance_name(self, tool_instance: ToolEntity) -> str:
        tool_name = str(
            getattr(getattr(tool_instance, "identity", None), "name", "") or ""
        )
        if tool_name:
            return tool_name
        return str(getattr(tool_instance, "name", "") or "unknown-tool")

    def _validate_schemaless_tool_args(
        self, *, tool_name: str, tool_call_args: dict[str, Any]
    ) -> str | None:
        arg_keys = sorted(str(key) for key in tool_call_args.keys())
        arg_count = len(arg_keys)
        if arg_count > self._MAX_SCHEMELESS_ARG_KEYS:
            self._emit_security_event(
                "tool_schema_missing_compat_rejected",
                tool_name=tool_name,
                reason="too_many_keys",
                arg_count=arg_count,
                arg_keys=arg_keys[: self._MAX_SCHEMELESS_ARG_KEYS],
            )
            return (
                "tool arguments validation error: too many arguments without "
                f"schema for tool '{tool_name}' (max {self._MAX_SCHEMELESS_ARG_KEYS})"
            )

        for raw_key, raw_value in tool_call_args.items():
            key = str(raw_key)
            if len(key) > self._MAX_SCHEMELESS_ARG_KEY_CHARS:
                self._emit_security_event(
                    "tool_schema_missing_compat_rejected",
                    tool_name=tool_name,
                    reason="key_too_long",
                    key=key[: self._MAX_SCHEMELESS_ARG_KEY_CHARS],
                )
                return (
                    "tool arguments validation error: argument key is too long "
                    f"without schema for tool '{tool_name}'"
                )
            value_chars = len(
                json.dumps(raw_value, ensure_ascii=False, default=str)
            )
            if value_chars > self._MAX_SCHEMELESS_ARG_VALUE_CHARS:
                self._emit_security_event(
                    "tool_schema_missing_compat_rejected",
                    tool_name=tool_name,
                    reason="value_too_large",
                    key=key,
                    value_chars=value_chars,
                    max_chars=self._MAX_SCHEMELESS_ARG_VALUE_CHARS,
                )
                return (
                    "tool arguments validation error: argument value is too large "
                    f"without schema for tool '{tool_name}'"
                )

        self._emit_security_event(
            "tool_schema_missing_compat_allowed",
            tool_name=tool_name,
            arg_count=arg_count,
            arg_keys=arg_keys,
        )
        return None

    def _coerce_parameter_value(
        self,
        *,
        parameter_name: str,
        parameter: Any,
        raw_value: Any,
    ) -> tuple[Any, str | None]:
        parameter_type = str(getattr(parameter, "type", "") or "").lower()
        if parameter_type in {"", "string", "text", "select"}:
            return raw_value, None

        if parameter_type in {"number", "integer"}:
            if isinstance(raw_value, (int, float)):
                return raw_value, None
            if isinstance(raw_value, str):
                try:
                    return (
                        int(raw_value)
                        if parameter_type == "integer"
                        else float(raw_value)
                    ), None
                except ValueError:
                    pass
            return (
                raw_value,
                (
                    "tool arguments validation error: parameter "
                    f"'{parameter_name}' requires {parameter_type}"
                ),
            )

        if parameter_type in {"boolean", "bool"}:
            if isinstance(raw_value, bool):
                return raw_value, None
            if isinstance(raw_value, str) and raw_value.lower() in {
                "true",
                "false",
            }:
                return raw_value.lower() == "true", None
            return (
                raw_value,
                (
                    "tool arguments validation error: parameter "
                    f"'{parameter_name}' requires boolean"
                ),
            )

        if parameter_type in {"array", "list"} and isinstance(raw_value, list):
            return raw_value, None

        if parameter_type in {"object", "json"} and isinstance(
            raw_value, Mapping
        ):
            return raw_value, None

        return raw_value, None

    def _parameter_option_values(self, parameter: Any) -> list[str]:
        values: list[str] = []
        for option in getattr(parameter, "options", []) or []:
            if isinstance(option, Mapping):
                option_value = option.get("value")
            else:
                option_value = getattr(option, "value", None)
            if option_value is None:
                continue
            values.append(str(option_value))
        return values

    def _tool_invocation_signature(
        self, tool_call_name: str, parameters: dict[str, Any]
    ) -> tuple[str, str]:
        serialized = json.dumps(parameters, sort_keys=True, default=str)
        return tool_call_name, serialized

    def _tool_call_tuple(
        self, prompt_message: Any
    ) -> tuple[str, str, dict[str, Any], str | None] | None:
        tool_call_id = str(getattr(prompt_message, "id", "") or "").strip()
        function = getattr(prompt_message, "function", None)
        tool_call_name = str(getattr(function, "name", "") or "").strip()
        if not tool_call_id or not tool_call_name:
            return None

        parsed = parse_tool_arguments(getattr(function, "arguments", ""))
        return (
            tool_call_id,
            tool_call_name,
            parsed.args,
            parsed.error,
        )

    def extract_tool_calls(
        self, llm_result_chunk: LLMResultChunk
    ) -> list[tuple[str, str, dict[str, Any], str | None]]:
        """
        Extract tool calls from llm result chunk

        Returns:
            List[Tuple[str, str, Dict[str, Any], Optional[str]]]:
                [(tool_call_id, tool_call_name, tool_call_args, parse_error)]
        """
        tool_calls = []
        for prompt_message in extract_stream_tool_calls(llm_result_chunk):
            tool_call = self._tool_call_tuple(prompt_message)
            if tool_call is None:
                continue
            tool_calls.append(tool_call)

        return tool_calls

    def extract_blocking_tool_calls(
        self, llm_result: LLMResult
    ) -> list[tuple[str, str, dict[str, Any], str | None]]:
        """
        Extract blocking tool calls from llm result

        Returns:
            List[Tuple[str, str, Dict[str, Any], Optional[str]]]:
                [(tool_call_id, tool_call_name, tool_call_args, parse_error)]
        """
        tool_calls = []
        for prompt_message in extract_blocking_tool_calls(llm_result):
            tool_call = self._tool_call_tuple(prompt_message)
            if tool_call is None:
                continue
            tool_calls.append(tool_call)

        return tool_calls

    def _init_system_message(
        self, prompt_template: str, prompt_messages: list[PromptMessage]
    ) -> list[PromptMessage]:
        """
        Initialize system message
        """
        if not prompt_messages and prompt_template:
            return [
                SystemPromptMessage(content=prompt_template),
            ]

        if (
            prompt_messages
            and not isinstance(prompt_messages[0], SystemPromptMessage)
            and prompt_template
        ):
            prompt_messages.insert(
                0, SystemPromptMessage(content=prompt_template)
            )

        return prompt_messages or []

    def _clear_user_prompt_image_messages(
        self, prompt_messages: list[PromptMessage]
    ) -> list[PromptMessage]:
        """
        Clear image messages from prompt messages.
        Converts image content to "[image]" placeholder text.

        This is needed because:
        1. Some models don't support vision at all
        2. Some models support vision in the first iteration,
            but not in subsequent iterations
            (when tool calls are involved)
        """
        prompt_messages = deepcopy(prompt_messages)

        for prompt_message in prompt_messages:
            if isinstance(prompt_message, UserPromptMessage) and isinstance(
                prompt_message.content, list
            ):
                prompt_message.content = "\n".join(
                    [
                        (
                            content.data
                            if content.type == PromptMessageContentType.TEXT
                            else (
                                "[image]"
                                if content.type
                                == PromptMessageContentType.IMAGE
                                else "[file]"
                            )
                        )
                        for content in prompt_message.content
                    ]
                )

        return prompt_messages

    def _organize_prompt_messages(
        self,
        current_thoughts: list[PromptMessage],
        history_prompt_messages: list[PromptMessage],
        model: AgentModelConfig | None = None,
    ) -> list[PromptMessage]:
        prompt_messages = [
            *history_prompt_messages,
            *current_thoughts,
        ]

        # Check if model supports vision
        supports_vision = (
            ModelFeature.VISION in model.entity.features
            if model and model.entity and model.entity.features
            else False
        )

        # Clear images if: model doesn't support vision OR it's not the first iteration
        if not supports_vision or len(current_thoughts) != 0:
            prompt_messages = self._clear_user_prompt_image_messages(
                prompt_messages
            )

        return prompt_messages

    def _to_agent_invoke_message(
        self, tool_invoke_response: ToolInvokeMessage
    ) -> AgentInvokeMessage:
        """Normalize tool-invoke payloads to AgentInvokeMessage for downstream UI."""
        return cast(AgentInvokeMessage, tool_invoke_response)

    def _max_blob_file_bytes(self) -> int:
        return self._MAX_BLOB_FILE_BYTES

    def _resolve_safe_local_file_path(self, file_info: str) -> str | None:
        if not file_info.startswith(f"{self._LOCAL_FILE_ROOT}/"):
            return None

        root_real = os.path.realpath(self._LOCAL_FILE_ROOT)
        candidate_real = os.path.realpath(file_info)
        try:
            common = os.path.commonpath([root_real, candidate_real])
        except ValueError:
            return None

        if common != root_real:
            return None

        return candidate_real

    def _read_local_file_for_blob(
        self, file_info: str
    ) -> tuple[bytes, str] | None:
        safe_path = self._resolve_safe_local_file_path(file_info)
        if safe_path is None or not os.path.exists(safe_path):
            return None

        max_bytes = self._max_blob_file_bytes()
        file_size = os.path.getsize(safe_path)
        if file_size > max_bytes:
            raise ValueError("local file is too large")

        with open(safe_path, "rb") as f:
            content = f.read(max_bytes + 1)

        if len(content) > max_bytes:
            raise ValueError("local file is too large")

        return content, os.path.basename(safe_path)
