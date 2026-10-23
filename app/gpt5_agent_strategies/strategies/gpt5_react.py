try:
    from app.gpt5_agent_strategies.strategies import (
        gpt5_function_calling as function_calling,
    )
except ModuleNotFoundError:
    from strategies import gpt5_function_calling as function_calling


class GPT5ReActParams(function_calling.GPT5FunctionCallingParams):
    """Reuse function-calling parameters for a ReAct-like strategy."""


class GPT5ReActStrategy(function_calling.GPT5FunctionCallingStrategy):
    """Reuse robust function-calling execution as a ReAct-like policy."""
