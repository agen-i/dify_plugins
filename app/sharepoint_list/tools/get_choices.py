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


class GetChoicesTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage]:
        try:
            credentials = self.runtime.credentials or {}
            access_token = credentials.get("access_token")
            access_token_len: int | None = (
                len(access_token) if isinstance(access_token, str) else None
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
            field_identifier = tool_parameters.get("field_identifier")
            if (
                not isinstance(field_identifier, str)
                or not field_identifier.strip()
            ):
                yield self.create_text_message("field_identifier is required.")
                yield self.create_json_message(
                    {"error": "missing_field_identifier"}
                )
                return

            result = operations.get_choice_field_info(
                access_token=access_token,
                site_identifier=target.site_identifier,
                list_identifier=target.list_identifier,
                field_identifier=field_identifier.strip(),
            )

            yield self.create_json_message(result or {})
            yield self.create_text_message(
                "Choice options fetched successfully."
            )
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
            yield self.create_text_message(f"Failed to fetch choices: {e}")
