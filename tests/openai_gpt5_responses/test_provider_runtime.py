from __future__ import annotations

import importlib
import sys
import types
from typing import Any

import pytest


def _install_provider_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
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


@pytest.fixture
def provider_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    _install_provider_stubs(monkeypatch)
    sys.modules.pop("app.openai_gpt5_responses.provider.openai_gpt5", None)
    importlib.invalidate_caches()
    return importlib.import_module(
        "app.openai_gpt5_responses.provider.openai_gpt5"
    )


def test_provider_safe_int_and_credential_kwargs(provider_module: Any) -> None:
    assert provider_module._safe_int("10", 1) == 10
    assert provider_module._safe_int("bad", 2) == 2

    kwargs = provider_module._to_credential_kwargs(
        {
            "openai_api_key": "k",
            "openai_api_base": "https://api.openai.com",
            "request_timeout_seconds": "10000",
            "max_retries": "10",
            "openai_organization": " org ",
        }
    )
    assert kwargs["api_key"] == "k"
    assert kwargs["timeout"] == 1200.0
    assert kwargs["max_retries"] == 5
    assert kwargs["base_url"] == "https://api.openai.com/v1"
    assert kwargs["organization"] == "org"


def test_validate_provider_credentials_requires_api_key(
    provider_module: Any,
) -> None:
    provider = provider_module.OpenAIGPT5ResponsesProvider()
    with pytest.raises(provider_module.CredentialsValidateFailedError):
        provider.validate_provider_credentials({})


def test_validate_provider_credentials_success(provider_module: Any) -> None:
    provider = provider_module.OpenAIGPT5ResponsesProvider()
    provider.validate_provider_credentials({"openai_api_key": "k"})


def test_validate_provider_credentials_wraps_api_status_error(
    provider_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            def _raise() -> list[str]:
                raise provider_module.APIStatusError(403, "forbidden")

            self.models = types.SimpleNamespace(list=_raise)

    monkeypatch.setattr(provider_module, "OpenAI", _OpenAI)
    provider = provider_module.OpenAIGPT5ResponsesProvider()

    with pytest.raises(provider_module.CredentialsValidateFailedError) as exc:
        provider.validate_provider_credentials({"openai_api_key": "k"})

    assert "OpenAI API status error (403)." in str(exc.value)


def test_validate_provider_credentials_wraps_connection_error(
    provider_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            def _raise() -> list[str]:
                raise provider_module.APIConnectionError("down")

            self.models = types.SimpleNamespace(list=_raise)

    monkeypatch.setattr(provider_module, "OpenAI", _OpenAI)
    provider = provider_module.OpenAIGPT5ResponsesProvider()

    with pytest.raises(provider_module.CredentialsValidateFailedError) as exc:
        provider.validate_provider_credentials({"openai_api_key": "k"})

    assert (
        "OpenAI provider connection failed. Check network and API base settings."
        in str(exc.value)
    )


def test_validate_provider_credentials_wraps_unexpected_error(
    provider_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _OpenAI:
        def __init__(self, **_: Any) -> None:
            def _raise() -> list[str]:
                raise RuntimeError("unexpected")

            self.models = types.SimpleNamespace(list=_raise)

    monkeypatch.setattr(provider_module, "OpenAI", _OpenAI)
    provider = provider_module.OpenAIGPT5ResponsesProvider()

    with pytest.raises(provider_module.CredentialsValidateFailedError) as exc:
        provider.validate_provider_credentials({"openai_api_key": "k"})

    assert "OpenAI provider credential validation failed." in str(exc.value)


def test_validate_provider_credentials_rejects_invalid_api_base(
    provider_module: Any,
) -> None:
    provider = provider_module.OpenAIGPT5ResponsesProvider()
    with pytest.raises(provider_module.CredentialsValidateFailedError) as exc:
        provider.validate_provider_credentials(
            {
                "openai_api_key": "k",
                "openai_api_base": "http://127.0.0.1:8000",
            }
        )

    assert "openai_api_base must use https" in str(exc.value)
