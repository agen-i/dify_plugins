from __future__ import annotations

from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from internal.auth import resolve_auth_config, sanitize_error_message


class NanobanaProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            resolve_auth_config(credentials)
        except Exception as exc:
            message = sanitize_error_message(exc, credentials)
            raise ToolProviderCredentialValidationError(message) from exc
