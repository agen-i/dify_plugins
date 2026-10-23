from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from internal import operations, validators
from internal.http_client import (
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
)


class CreateItemTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage]:
        try:
            credentials = self.runtime.credentials or {}
            access_token = credentials.get("access_token")
            access_token_len = (
                len(access_token)
                if isinstance(access_token, str)
                else "non-str"
            )
            if not isinstance(access_token, str) or not access_token.strip():
                yield self.create_text_message(
                    "Missing or empty access_token. Please authorize again."
                )
                yield self.create_json_message(
                    {
                        "error": "missing_access_token",
                        "debug": {"access_token_len": access_token_len},
                    }
                )
                return
            access_token = access_token.strip()

            list_url = tool_parameters.get("list_url")
            site_identifier, list_identifier = validators.parse_list_url(
                list_url=list_url
            )
            target = validators.validate_target(
                site_identifier=site_identifier,
                list_identifier=list_identifier,
            )
            fields = validators.parse_fields_json(
                tool_parameters.get("fields_json")
            )

            result = operations.create_item(
                access_token=access_token, target=target, fields=fields
            )
            yield self.create_json_message(result or {})
            yield self.create_text_message("Item created successfully.")
        except AuthenticationError as e:
            yield self.create_json_message(
                {
                    "error": "authentication_failed",
                    "error_type": "AuthenticationError",
                    "message": str(e),
                }
            )
            yield self.create_text_message(
                "Authentication failed. Your access token may have expired. "
                "Please re-authorize the SharePoint List connection."
            )
        except AuthorizationError as e:
            yield self.create_json_message(
                {
                    "error": "authorization_failed",
                    "error_type": "AuthorizationError",
                    "message": str(e),
                }
            )
            yield self.create_text_message(
                f"Permission denied: {e}. "
                "Please check your SharePoint permissions."
            )
        except RateLimitError as e:
            yield self.create_json_message(
                {
                    "error": "rate_limit_exceeded",
                    "error_type": "RateLimitError",
                    "retry_after": e.retry_after,
                    "message": str(e),
                }
            )
            yield self.create_text_message(
                f"Rate limit exceeded. Please try again later. "
                f"(Retry after: {e.retry_after or 'unknown'} seconds)"
            )
        except Exception as e:  # noqa: BLE001
            yield self.create_json_message({"error": str(e)})
            yield self.create_text_message(f"Failed to create item: {e}")
