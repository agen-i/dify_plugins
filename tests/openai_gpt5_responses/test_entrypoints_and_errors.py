from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any

import pytest

BASE_DIR = Path(__file__).resolve().parents[2]
PLUGIN_DIR = BASE_DIR / "app" / "openai_gpt5_responses"


def _install_dify_plugin_stub() -> None:
    dify_plugin_mod = types.ModuleType("dify_plugin")

    class DifyPluginEnv:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class Plugin:
        def __init__(self, env: DifyPluginEnv) -> None:
            self.env = env

        def run(self) -> None:
            return None

    dify_plugin_mod.DifyPluginEnv = DifyPluginEnv
    dify_plugin_mod.Plugin = Plugin
    sys.modules["dify_plugin"] = dify_plugin_mod


def test_openai_main_plugin_entrypoint() -> None:
    _install_dify_plugin_stub()
    sys.modules.pop("app.openai_gpt5_responses.main", None)

    module = importlib.import_module("app.openai_gpt5_responses.main")
    assert module.plugin.env.kwargs["MAX_REQUEST_TIMEOUT"] == 1200
    assert module.plugin.env.kwargs["MAX_INVOCATION_TIMEOUT"] == 1200


def test_openai_main_plugin_entrypoint_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_dify_plugin_stub()
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", "7200")
    monkeypatch.setenv("MAX_INVOCATION_TIMEOUT", "bad")
    sys.modules.pop("app.openai_gpt5_responses.main", None)

    module = importlib.import_module("app.openai_gpt5_responses.main")
    assert module.plugin.env.kwargs["MAX_REQUEST_TIMEOUT"] == 3600
    assert module.plugin.env.kwargs["MAX_INVOCATION_TIMEOUT"] == 1200


def test_format_runtime_error() -> None:
    module = importlib.import_module(
        "app.openai_gpt5_responses.internal.errors"
    )
    assert (
        module.format_runtime_error("boom", category="tool") == "[tool] boom"
    )


def _install_provider_import_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    dify_plugin_mod = types.ModuleType("dify_plugin")
    errors_model_mod = types.ModuleType("dify_plugin.errors.model")
    openai_mod = types.ModuleType("openai")

    class ModelProvider:
        pass

    class CredentialsValidateFailedError(Exception):
        pass

    class APIError(Exception):
        pass

    class APIStatusError(APIError):
        def __init__(self, status_code: int, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code
            self.message = message

    class APIConnectionError(APIError):
        pass

    class _Models:
        def list(self) -> list[str]:
            return ["gpt-5.2"]

    class OpenAI:
        def __init__(self, **_: Any) -> None:
            self.models = _Models()

    dify_plugin_mod.ModelProvider = ModelProvider
    errors_model_mod.CredentialsValidateFailedError = (
        CredentialsValidateFailedError
    )
    openai_mod.APIError = APIError
    openai_mod.APIStatusError = APIStatusError
    openai_mod.APIConnectionError = APIConnectionError
    openai_mod.OpenAI = OpenAI

    monkeypatch.setitem(sys.modules, "dify_plugin", dify_plugin_mod)
    monkeypatch.setitem(
        sys.modules, "dify_plugin.errors.model", errors_model_mod
    )
    monkeypatch.setitem(sys.modules, "openai", openai_mod)


def test_openai_provider_importable_without_app_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_provider_import_stubs(monkeypatch)
    monkeypatch.setitem(sys.modules, "app", types.ModuleType("app"))
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    sys.modules.pop("provider.openai_gpt5", None)
    importlib.invalidate_caches()

    module = importlib.import_module("provider.openai_gpt5")
    assert module.OpenAIGPT5ResponsesProvider.__name__
