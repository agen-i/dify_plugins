"""Tests for debug logging in operations.py."""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

from app.sharepoint_list.internal import operations


def _logged_payloads(mock_logger: Mock) -> list[dict]:
    return [
        json.loads(call.args[0]) for call in mock_logger.info.call_args_list
    ]


class TestDebugLogEnabled:
    """_is_debug_log_enabled のテスト"""

    def test_disabled_by_default(self) -> None:
        """デフォルトでは無効"""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SHAREPOINT_LIST_DEBUG_LOG", None)
            assert operations._is_debug_log_enabled() is False

    def test_enabled_by_env_var_1(self) -> None:
        """SHAREPOINT_LIST_DEBUG_LOG=1 で有効"""
        with patch.dict(os.environ, {"SHAREPOINT_LIST_DEBUG_LOG": "1"}):
            assert operations._is_debug_log_enabled() is True

    def test_enabled_by_env_var_true(self) -> None:
        """SHAREPOINT_LIST_DEBUG_LOG=true で有効"""
        with patch.dict(os.environ, {"SHAREPOINT_LIST_DEBUG_LOG": "true"}):
            assert operations._is_debug_log_enabled() is True

    def test_enabled_by_env_var_yes(self) -> None:
        """SHAREPOINT_LIST_DEBUG_LOG=yes で有効"""
        with patch.dict(os.environ, {"SHAREPOINT_LIST_DEBUG_LOG": "yes"}):
            assert operations._is_debug_log_enabled() is True

    def test_enabled_by_env_var_on(self) -> None:
        """SHAREPOINT_LIST_DEBUG_LOG=on で有効"""
        with patch.dict(os.environ, {"SHAREPOINT_LIST_DEBUG_LOG": "on"}):
            assert operations._is_debug_log_enabled() is True

    def test_case_insensitive(self) -> None:
        """大文字小文字を区別しない"""
        with patch.dict(os.environ, {"SHAREPOINT_LIST_DEBUG_LOG": "TRUE"}):
            assert operations._is_debug_log_enabled() is True

    def test_disabled_with_invalid_value(self) -> None:
        """無効な値では無効"""
        with patch.dict(os.environ, {"SHAREPOINT_LIST_DEBUG_LOG": "invalid"}):
            assert operations._is_debug_log_enabled() is False


class TestLogDebug:
    """_log_debug のテスト"""

    @patch("app.sharepoint_list.internal.debug_logging.get_debug_logger")
    def test_emits_json_message_when_enabled(
        self, mock_get_debug_logger: Mock
    ) -> None:
        """有効時に JSON payload を logger へ送る"""
        mock_logger = Mock()
        mock_get_debug_logger.return_value = mock_logger

        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_LIST_DEBUG_LOG": "1",
                "SHAREPOINT_LIST_DEBUG_LOG_PATH": "/ignored/path.ndjson",
                "SHAREPOINT_LIST_DEBUG_RUN_ID": "test-run",
            },
        ):
            with patch(
                "builtins.open",
                side_effect=AssertionError("file open should not be used"),
            ):
                operations._log_debug(
                    location="test",
                    message="test message",
                    data={"key": "value"},
                )

        mock_logger.info.assert_called_once()
        payload = json.loads(mock_logger.info.call_args.args[0])
        assert list(payload.keys())[:2] == ["ts", "timestamp"]
        assert payload["location"] == "test"
        assert payload["message"] == "test message"
        assert payload["data"] == {"key": "value"}
        assert payload["runId"] == "test-run"

    @patch("app.sharepoint_list.internal.debug_logging.get_debug_logger")
    def test_does_not_log_when_disabled(
        self, mock_get_debug_logger: Mock
    ) -> None:
        """無効時には logger を呼ばない"""
        mock_logger = Mock()
        mock_get_debug_logger.return_value = mock_logger

        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_LIST_DEBUG_LOG": "0",
                "SHAREPOINT_LIST_DEBUG_LOG_PATH": "/ignored/path.ndjson",
            },
        ):
            operations._log_debug(
                location="test",
                message="test message",
                data={"key": "value"},
            )

        mock_logger.info.assert_not_called()


class TestSendRequestDebugLogging:
    """_send_request でのデバッグログテスト"""

    @patch("app.sharepoint_list.internal.debug_logging.get_debug_logger")
    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_authorization_header_excluded_from_log(
        self,
        mock_request: Mock,
        mock_get_debug_logger: Mock,
    ) -> None:
        """Authorization ヘッダーがログから除外される"""
        mock_logger = Mock()
        mock_get_debug_logger.return_value = mock_logger

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "test-site"}
        mock_request.return_value = mock_resp

        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_LIST_DEBUG_LOG": "1",
                "SHAREPOINT_LIST_DEBUG_LOG_PATH": "/ignored/path.ndjson",
            },
        ):
            from app.sharepoint_list.internal import request_builders

            spec = request_builders.RequestSpec(
                url="https://graph.microsoft.com/v1.0/test",
                method="GET",
            )
            operations._send_request(
                spec=spec,
                access_token="secret-token-12345",
                extra_headers={
                    "Authorization": "Bearer secret",
                    "Prefer": "test",
                },
            )

        payloads = _logged_payloads(mock_logger)
        request_payload = next(
            p
            for p in payloads
            if p["location"] == "operations.py:_send_request"
            and p["message"] == "request"
        )
        headers = request_payload["data"]["headers"]
        assert "Authorization" not in headers
        assert "authorization" not in headers
        assert headers.get("Prefer") == "test"

    @patch("app.sharepoint_list.internal.debug_logging.get_debug_logger")
    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_access_token_not_in_log_data(
        self,
        mock_request: Mock,
        mock_get_debug_logger: Mock,
    ) -> None:
        """アクセストークンがログデータに含まれない"""
        mock_logger = Mock()
        mock_get_debug_logger.return_value = mock_logger

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "test-site"}
        mock_request.return_value = mock_resp

        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_LIST_DEBUG_LOG": "1",
                "SHAREPOINT_LIST_DEBUG_LOG_PATH": "/ignored/path.ndjson",
            },
        ):
            from app.sharepoint_list.internal import request_builders

            spec = request_builders.RequestSpec(
                url="https://graph.microsoft.com/v1.0/test",
                method="GET",
            )
            operations._send_request(
                spec=spec,
                access_token="super-secret-token-xyz",
            )

        serialized_payloads = json.dumps(_logged_payloads(mock_logger))
        assert "super-secret-token-xyz" not in serialized_payloads


class TestListItemsDebugLogging:
    """list_items のデバッグログが出力されることを確認"""

    @patch("app.sharepoint_list.internal.debug_logging.get_debug_logger")
    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_emits_debug_entries(
        self,
        mock_request: Mock,
        mock_get_debug_logger: Mock,
    ) -> None:
        mock_logger = Mock()
        mock_get_debug_logger.return_value = mock_logger

        status_internal = "_x30b9__x30c6__x30fc__x30bf__x30"
        detail_internal = "_x8a73__x7d30_"
        category_internal = "_x30ab__x30c6__x30b4__x30ea_"

        columns_response = {
            "value": [
                {"name": "Title", "displayName": "Title"},
                {"name": "id", "displayName": "ID"},
                {"name": status_internal, "displayName": "ステータス"},
                {"name": detail_internal, "displayName": "詳細"},
                {"name": category_internal, "displayName": "カテゴリ"},
            ]
        }
        items_response = {
            "value": [
                {
                    "id": "item-1",
                    "fields": {
                        "Title": "Item 1",
                        "id": "1",
                        status_internal: "処理中",
                    },
                }
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/sites/site/lists/list/items?$skiptoken=abc123",
        }

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [columns_response, items_response]
        mock_request.return_value = mock_resp

        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_LIST_DEBUG_LOG": "1",
                "SHAREPOINT_LIST_DEBUG_LOG_PATH": "/ignored/path.ndjson",
                "SHAREPOINT_LIST_DEBUG_RUN_ID": "test",
            },
        ):
            from app.sharepoint_list.internal import validators

            target = validators.TargetSpec(
                site_identifier="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                list_identifier="b2c3d4e5-f6a7-8901-bcde-f12345678901",
            )
            operations.list_items(
                access_token="test-token",
                target=target,
                select_fields="ID,Title,ステータス,詳細,カテゴリ",
                filters_raw='[{"field":"ステータス","op":"eq","value":"処理中"}]',
            )

        payloads = _logged_payloads(mock_logger)
        messages = {payload.get("message") for payload in payloads}
        assert "select_fields_mapping" in messages
        assert "request_args" in messages
        assert "response_fields_presence" in messages
        assert "normalized_missing_fields" in messages
        assert "response_fields_presence_normalized" in messages
        assert "return_summary" in messages

        select_mapping = next(
            p for p in payloads if p.get("message") == "select_fields_mapping"
        )
        response_presence = next(
            p
            for p in payloads
            if p.get("message") == "response_fields_presence"
        )
        return_summary = next(
            p for p in payloads if p.get("message") == "return_summary"
        )
        assert select_mapping["hypothesisId"] == "H1"
        assert response_presence["hypothesisId"] == "H2"
        assert return_summary["hypothesisId"] == "H3"
