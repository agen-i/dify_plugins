import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any, Literal

AuthMode = Literal["developer", "vertex"]

SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
SENSITIVE_CREDENTIAL_KEYS = (
    "api_key",
    "gemini_api_key",
    "vertex_service_account_key",
)
REQUIRED_SERVICE_ACCOUNT_FIELDS = (
    "client_email",
    "private_key",
    "token_uri",
)


@dataclass(frozen=True)
class AuthConfig:
    mode: AuthMode
    api_key: str
    vertex_project_id: str
    vertex_location: str
    service_account_info: dict[str, Any] | None


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def decode_service_account_key(key_b64: str) -> dict[str, Any]:
    normalized_key = "".join(key_b64.split())
    try:
        decoded = base64.b64decode(normalized_key, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Service account key must be base64 JSON.") from exc

    try:
        info = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Service account key must decode to JSON.") from exc

    if not isinstance(info, dict):
        raise ValueError("Service account key JSON must be an object.")
    missing_fields = [
        field
        for field in REQUIRED_SERVICE_ACCOUNT_FIELDS
        if not _clean_string(info.get(field))
    ]
    if missing_fields:
        raise ValueError(
            "Service account key JSON must include "
            + ", ".join(REQUIRED_SERVICE_ACCOUNT_FIELDS)
            + "."
        )
    return info


def resolve_auth_config(credentials: dict[str, Any]) -> AuthConfig:
    vertex_project_id = _clean_string(credentials.get("vertex_project_id"))
    vertex_location = (
        _clean_string(credentials.get("vertex_location")) or "global"
    )
    key_b64 = _clean_string(credentials.get("vertex_service_account_key"))

    if vertex_project_id:
        service_account_info = (
            decode_service_account_key(key_b64) if key_b64 else None
        )
        return AuthConfig(
            mode="vertex",
            api_key="",
            vertex_project_id=vertex_project_id,
            vertex_location=vertex_location,
            service_account_info=service_account_info,
        )

    api_key = _clean_string(
        credentials.get("api_key") or credentials.get("gemini_api_key")
    )
    if api_key:
        return AuthConfig(
            mode="developer",
            api_key=api_key,
            vertex_project_id="",
            vertex_location=vertex_location,
            service_account_info=None,
        )

    raise ValueError(
        "Configure either Vertex AI Project ID or Gemini API key."
    )


def make_genai_client(config: AuthConfig) -> Any:
    from google import genai

    if config.mode == "developer":
        return genai.Client(api_key=config.api_key)

    if config.service_account_info:
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_info(
            config.service_account_info,
            scopes=list(SCOPES),
        )
        return genai.Client(
            vertexai=True,
            project=config.vertex_project_id,
            location=config.vertex_location,
            credentials=credentials,
        )

    return genai.Client(
        vertexai=True,
        project=config.vertex_project_id,
        location=config.vertex_location,
    )


def sanitize_error_message(
    error: Exception, credentials: dict[str, Any] | None = None
) -> str:
    message = str(error) or error.__class__.__name__
    if credentials:
        for key in SENSITIVE_CREDENTIAL_KEYS:
            secret = _clean_string(credentials.get(key))
            if secret:
                message = message.replace(secret, "[REDACTED]")
    if len(message) > 1000:
        message = message[:1000] + "..."
    return message
