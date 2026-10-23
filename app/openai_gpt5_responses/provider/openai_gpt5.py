from __future__ import annotations

from collections.abc import Mapping

from dify_plugin import ModelProvider
from dify_plugin.errors.model import CredentialsValidateFailedError
from openai import APIConnectionError, APIStatusError, OpenAI

try:
    from app.openai_gpt5_responses.internal.credentials import (
        normalize_api_base,
    )
except ModuleNotFoundError:
    from internal.credentials import normalize_api_base

_PROVIDER_CREDENTIALS_FAILED_MESSAGE = (
    "OpenAI provider credential validation failed."
)
_PROVIDER_CREDENTIALS_CONNECTION_FAILED_MESSAGE = (
    "OpenAI provider connection failed. Check network and API base settings."
)
_REQUEST_TIMEOUT_DEFAULT_SECONDS = 600
_REQUEST_TIMEOUT_MAX_SECONDS = 1200


def _safe_int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _to_credential_kwargs(credentials: Mapping) -> dict:
    api_base = normalize_api_base(credentials.get("openai_api_base"))
    timeout_seconds = max(
        30,
        min(
            _REQUEST_TIMEOUT_MAX_SECONDS,
            _safe_int(
                credentials.get("request_timeout_seconds"),
                _REQUEST_TIMEOUT_DEFAULT_SECONDS,
            ),
        ),
    )
    max_retries = max(0, min(5, _safe_int(credentials.get("max_retries"), 1)))

    kwargs: dict[str, object] = {
        "api_key": credentials.get("openai_api_key"),
        "timeout": float(timeout_seconds),
        "max_retries": max_retries,
    }

    if api_base:
        kwargs["base_url"] = api_base

    organization = str(credentials.get("openai_organization") or "").strip()
    if organization:
        kwargs["organization"] = organization

    return kwargs


class OpenAIGPT5ResponsesProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: Mapping) -> None:
        if not credentials.get("openai_api_key"):
            raise CredentialsValidateFailedError("openai_api_key is required")

        try:
            client = OpenAI(**_to_credential_kwargs(credentials))
            # Validate key reachability with a lightweight list call.
            _ = client.models.list()
        except APIStatusError as exc:
            raise CredentialsValidateFailedError(
                f"OpenAI API status error ({exc.status_code})."
            ) from exc
        except APIConnectionError as exc:
            raise CredentialsValidateFailedError(
                _PROVIDER_CREDENTIALS_CONNECTION_FAILED_MESSAGE
            ) from exc
        except ValueError as exc:
            raise CredentialsValidateFailedError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise CredentialsValidateFailedError(
                _PROVIDER_CREDENTIALS_FAILED_MESSAGE
            ) from exc
