from __future__ import annotations

import base64
import importlib
import json
import sys
import types
from typing import Any

import pytest


def _service_account_key(
    overrides: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "service_account",
        "client_email": "svc@example.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\\nredacted\\n-----END PRIVATE KEY-----\\n",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    if overrides:
        for key, value in overrides.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
    return base64.b64encode(json.dumps(payload).encode()).decode()


def test_resolve_developer_api_credentials(nanobana_imports: None) -> None:
    auth = importlib.import_module("internal.auth")

    config = auth.resolve_auth_config({"api_key": "  developer-key  "})

    assert config.mode == "developer"
    assert config.api_key == "developer-key"
    assert config.vertex_location == "global"


def test_resolve_vertex_credentials_prefer_vertex(
    nanobana_imports: None,
) -> None:
    auth = importlib.import_module("internal.auth")

    config = auth.resolve_auth_config(
        {
            "api_key": "legacy-key",
            "vertex_project_id": "project-a",
            "vertex_location": "",
        }
    )

    assert config.mode == "vertex"
    assert config.vertex_project_id == "project-a"
    assert config.vertex_location == "global"
    assert config.api_key == ""


def test_decode_service_account_key(nanobana_imports: None) -> None:
    auth = importlib.import_module("internal.auth")

    key = _service_account_key()
    wrapped_key = f"{key[:16]}\n{key[16:]}"
    info = auth.decode_service_account_key(wrapped_key)

    assert info["client_email"] == "svc@example.iam.gserviceaccount.com"
    assert info["token_uri"] == "https://oauth2.googleapis.com/token"


def test_decode_service_account_key_rejects_missing_token_uri(
    nanobana_imports: None,
) -> None:
    auth = importlib.import_module("internal.auth")

    with pytest.raises(ValueError, match="token_uri"):
        auth.decode_service_account_key(
            _service_account_key({"token_uri": None})
        )


def test_decode_service_account_key_rejects_wif_or_invalid_json(
    nanobana_imports: None,
) -> None:
    auth = importlib.import_module("internal.auth")
    encoded = base64.b64encode(b'{"type":"external_account"}').decode()

    with pytest.raises(ValueError, match="client_email"):
        auth.decode_service_account_key(encoded)


def test_make_vertex_adc_client_without_service_account(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = importlib.import_module("internal.auth")
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    calls: list[dict[str, Any]] = []

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    genai_mod.Client = Client
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)

    config = auth.resolve_auth_config({"vertex_project_id": "project-a"})
    auth.make_genai_client(config)

    assert calls == [
        {
            "vertexai": True,
            "project": "project-a",
            "location": "global",
        }
    ]


def test_provider_validation_requires_one_auth_mode(
    nanobana_imports: None,
) -> None:
    provider = importlib.import_module("provider.nanobana")

    with pytest.raises(Exception, match="Configure either"):
        provider.NanobanaProvider()._validate_credentials({})


def test_provider_validation_accepts_vertex_adc(
    nanobana_imports: None,
) -> None:
    provider = importlib.import_module("provider.nanobana")

    provider.NanobanaProvider()._validate_credentials(
        {"vertex_project_id": "project-a"}
    )


def test_provider_validation_rejects_incomplete_service_account_key(
    nanobana_imports: None,
) -> None:
    provider = importlib.import_module("provider.nanobana")

    with pytest.raises(Exception, match="token_uri"):
        provider.NanobanaProvider()._validate_credentials(
            {
                "vertex_project_id": "project-a",
                "vertex_service_account_key": _service_account_key(
                    {"token_uri": None}
                ),
            }
        )
