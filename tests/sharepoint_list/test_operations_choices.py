"""Tests for get_choice_field_info in operations.py."""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

import pytest

from app.sharepoint_list.internal import operations

# Use GUID format to bypass resolve functions
SITE_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
LIST_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


def _mock_columns_with_choice() -> dict:
    return {
        "value": [
            {"name": "Title", "displayName": "Title", "columnType": "text"},
            {
                "name": "Status",
                "displayName": "ステータス",
                "columnType": "choice",
                "choice": {
                    "choices": ["未着手", "処理中", "完了"],
                    "allowMultipleSelections": False,
                    "defaultValue": "未着手",
                },
            },
            {
                "name": "Priority",
                "displayName": "優先度",
                "columnType": "number",
            },
        ]
    }


class TestGetChoiceFieldInfo:
    """get_choice_field_info のテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_choice_field_returns_options(self, mock_request: Mock) -> None:
        """choice列で選択肢一覧を取得"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_columns_with_choice()
        mock_request.return_value = mock_resp

        result = operations.get_choice_field_info(
            access_token="test-token",
            site_identifier=SITE_ID,
            list_identifier=LIST_ID,
            field_identifier="Status",
        )

        assert "choices" in result
        assert result["choices"] == ["未着手", "処理中", "完了"]
        assert result["name"] == "Status"
        assert result["displayName"] == "ステータス"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_choice_field_by_display_name(self, mock_request: Mock) -> None:
        """表示名でchoice列を取得"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_columns_with_choice()
        mock_request.return_value = mock_resp

        result = operations.get_choice_field_info(
            access_token="test-token",
            site_identifier=SITE_ID,
            list_identifier=LIST_ID,
            field_identifier="ステータス",
        )

        assert result["name"] == "Status"
        assert result["choices"] == ["未着手", "処理中", "完了"]

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_non_choice_field_raises_error(self, mock_request: Mock) -> None:
        """非choice列でエラー"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_columns_with_choice()
        mock_request.return_value = mock_resp

        with pytest.raises(operations.GraphError) as exc_info:
            operations.get_choice_field_info(
                access_token="test-token",
                site_identifier=SITE_ID,
                list_identifier=LIST_ID,
                field_identifier="Priority",
            )

        assert "not a choice column" in str(exc_info.value)

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_unknown_field_raises_error(self, mock_request: Mock) -> None:
        """不明なフィールドでエラー"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_columns_with_choice()
        mock_request.return_value = mock_resp

        with pytest.raises(operations.GraphError) as exc_info:
            operations.get_choice_field_info(
                access_token="test-token",
                site_identifier=SITE_ID,
                list_identifier=LIST_ID,
                field_identifier="NonExistentField",
            )

        assert "not found" in str(exc_info.value)

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_choice_field_returns_metadata(self, mock_request: Mock) -> None:
        """choice列のメタデータを返す"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_columns_with_choice()
        mock_request.return_value = mock_resp

        result = operations.get_choice_field_info(
            access_token="test-token",
            site_identifier=SITE_ID,
            list_identifier=LIST_ID,
            field_identifier="Status",
        )

        assert result["allowMultipleSelections"] is False
        assert result["defaultValue"] == "未着手"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    @patch("app.sharepoint_list.internal.debug_logging.get_debug_logger")
    def test_emits_debug_logs_when_enabled(
        self,
        mock_get_debug_logger: Mock,
        mock_request: Mock,
    ) -> None:
        """デバッグ有効時に get_choice_field_info のログが書かれる"""
        mock_logger = Mock()
        mock_get_debug_logger.return_value = mock_logger

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_columns_with_choice()
        mock_request.return_value = mock_resp

        with patch.dict(
            os.environ,
            {
                "SHAREPOINT_LIST_DEBUG_LOG": "1",
                "SHAREPOINT_LIST_DEBUG_LOG_PATH": "/ignored/path.ndjson",
            },
        ):
            operations.get_choice_field_info(
                access_token="test-token",
                site_identifier=SITE_ID,
                list_identifier=LIST_ID,
                field_identifier="Status",
            )

        parsed = [
            json.loads(call.args[0])
            for call in mock_logger.info.call_args_list
        ]
        locations = {e.get("location") for e in parsed}
        hypothesis_ids = {e.get("hypothesisId") for e in parsed}
        assert "operations.py:get_choice_field_info" in locations
        assert {"H1", "H2", "H3"} <= hypothesis_ids
