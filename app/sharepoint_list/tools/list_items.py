from __future__ import annotations

import json
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


class ListItemsTool(Tool):
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

            select_fields = tool_parameters.get("select_fields")
            page_token = tool_parameters.get("page_token")
            page_size_raw = tool_parameters.get("page_size")
            try:
                page_size = (
                    int(page_size_raw) if page_size_raw is not None else 20
                )
            except (TypeError, ValueError):
                page_size = 20
            if page_size <= 0:
                page_size = 20
            page_size = min(page_size, 100)

            created_after = tool_parameters.get("created_after")
            created_before = tool_parameters.get("created_before")
            if created_after or created_before:
                yield self.create_json_message(
                    {
                        "error": "deprecated_parameter",
                        "message": (
                            "Use filters with createdDateTime instead of "
                            "created_after/created_before."
                        ),
                    }
                )
                yield self.create_text_message(
                    "created_after / created_before は廃止しました。"
                    "filters の createdDateTime を使用してください。"
                )
                return

            filters_raw = tool_parameters.get("filters")
            if isinstance(filters_raw, (dict, list)):
                filters_raw = json.dumps(filters_raw)

            result = operations.list_items(
                access_token=access_token,
                target=target,
                select_fields=select_fields,
                page_size=page_size,
                page_token=page_token,
                filters_raw=filters_raw,
            )

            yield self.create_json_message(result or {})
            text = "Items fetched successfully."
            if result.get("next_page_token"):
                text += " More pages available."
            yield self.create_text_message(text)
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
            yield self.create_text_message(f"Failed to list items: {e}")
