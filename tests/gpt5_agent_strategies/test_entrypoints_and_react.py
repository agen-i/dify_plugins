from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any

from tests.gpt5_agent_strategies.test_strategy_invoke_paths import (
    _install_strategy_dify_stub,
)

BASE_DIR = Path(__file__).resolve().parents[2]
PLUGIN_DIR = BASE_DIR / "app" / "gpt5_agent_strategies"


def _install_main_provider_stub() -> None:
    dify_plugin_mod = types.ModuleType("dify_plugin")
    interfaces_agent_mod = types.ModuleType("dify_plugin.interfaces.agent")

    class DifyPluginEnv:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class Plugin:
        def __init__(self, env: DifyPluginEnv) -> None:
            self.env = env

        def run(self) -> None:
            return None

    class AgentProvider:
        pass

    dify_plugin_mod.DifyPluginEnv = DifyPluginEnv
    dify_plugin_mod.Plugin = Plugin
    interfaces_agent_mod.AgentProvider = AgentProvider

    sys.modules["dify_plugin"] = dify_plugin_mod
    sys.modules["dify_plugin.interfaces.agent"] = interfaces_agent_mod


def test_agent_main_and_provider_entrypoint() -> None:
    _install_main_provider_stub()
    sys.modules.pop("app.gpt5_agent_strategies.main", None)
    sys.modules.pop("app.gpt5_agent_strategies.provider.gpt5_agent", None)

    main_module = importlib.import_module("app.gpt5_agent_strategies.main")
    provider_module = importlib.import_module(
        "app.gpt5_agent_strategies.provider.gpt5_agent"
    )

    assert main_module.plugin.env.kwargs["MAX_REQUEST_TIMEOUT"] == 1800
    assert main_module.plugin.env.kwargs["MAX_INVOCATION_TIMEOUT"] == 1200
    assert (
        provider_module.GPT5AgentProvider.__mro__[1].__name__
        == "AgentProvider"
    )


def test_agent_main_and_provider_entrypoint_env_override(
    monkeypatch: Any,
) -> None:
    _install_main_provider_stub()
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", "9999")
    monkeypatch.setenv("MAX_INVOCATION_TIMEOUT", "1")
    sys.modules.pop("app.gpt5_agent_strategies.main", None)
    sys.modules.pop("app.gpt5_agent_strategies.provider.gpt5_agent", None)

    main_module = importlib.import_module("app.gpt5_agent_strategies.main")

    assert main_module.plugin.env.kwargs["MAX_REQUEST_TIMEOUT"] == 3600
    assert main_module.plugin.env.kwargs["MAX_INVOCATION_TIMEOUT"] == 60


def test_gpt5_react_reuses_function_calling_strategy(monkeypatch: Any) -> None:
    _install_strategy_dify_stub(monkeypatch)
    sys.modules.pop("app.gpt5_agent_strategies.strategies.gpt5_react", None)

    module = importlib.import_module(
        "app.gpt5_agent_strategies.strategies.gpt5_react"
    )

    assert (
        module.GPT5ReActParams.__mro__[1].__name__
        == "GPT5FunctionCallingParams"
    )
    assert (
        module.GPT5ReActStrategy.__mro__[1].__name__
        == "GPT5FunctionCallingStrategy"
    )


def test_gpt5_react_exposes_single_agent_strategy_subclass(
    monkeypatch: Any,
) -> None:
    _install_strategy_dify_stub(monkeypatch)
    sys.modules.pop(
        "app.gpt5_agent_strategies.strategies.gpt5_function_calling", None
    )
    sys.modules.pop("app.gpt5_agent_strategies.strategies.gpt5_react", None)

    module = importlib.import_module(
        "app.gpt5_agent_strategies.strategies.gpt5_react"
    )
    exported_types = {
        name for name, value in vars(module).items() if isinstance(value, type)
    }

    assert "GPT5ReActStrategy" in exported_types
    assert "GPT5FunctionCallingStrategy" not in exported_types
    assert "GPT5FunctionCallingParams" not in exported_types


def test_agent_strategy_importable_without_app_package(
    monkeypatch: Any,
) -> None:
    _install_strategy_dify_stub(monkeypatch)
    monkeypatch.setitem(sys.modules, "app", types.ModuleType("app"))
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    sys.modules.pop("strategies.gpt5_function_calling", None)
    importlib.invalidate_caches()

    module = importlib.import_module("strategies.gpt5_function_calling")
    assert module.GPT5FunctionCallingStrategy.__name__
