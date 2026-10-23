"""Tests for list_items filter functionality in operations.py."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.sharepoint_list.internal import operations, validators

# Use GUID format to bypass resolve functions
SITE_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
LIST_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


# Mock response helpers
def _mock_site_response(site_id: str = SITE_ID) -> dict:
    return {"id": site_id}


def _mock_list_response(list_id: str = LIST_ID) -> dict:
    return {"value": [{"id": list_id, "displayName": "TestList"}]}


def _mock_columns_response() -> dict:
    return {
        "value": [
            {"name": "Title", "displayName": "Title"},
            {"name": "Status", "displayName": "ステータス"},
            {"name": "Priority", "displayName": "優先度"},
            {"name": "Flag", "displayName": "Flag"},
        ]
    }


def _mock_items_response(items: list | None = None) -> dict:
    return {"value": items or [], "@odata.nextLink": None}


class TestListItemsFiltersContract:
    """list_items のフィルタ入力契約をテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_filters_json_array_accepted(self, mock_request: Mock) -> None:
        """[{"field": "Status", "op": "eq", "value": "Active"}] が正しく処理される"""
        # Setup mock responses
        # With GUID identifiers, resolve_site_id and resolve_list_id are skipped
        # So only columns + items requests are made
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "Status", "op": "eq", "value": "Active"}]',
        )

        assert "items" in result
        # Verify the filter was applied in request params
        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        assert "$filter" in params
        assert "fields/Status" in params["$filter"]

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_filters_single_object_accepted(self, mock_request: Mock) -> None:
        """{"field": "Status", "op": "eq", "value": "Active"} が配列に変換される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        # Single object instead of array
        result = operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='{"field": "Status", "op": "eq", "value": "Active"}',
        )

        assert "items" in result
        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        assert "$filter" in params
        assert "fields/Status" in params["$filter"]

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_filters_empty_string_returns_no_filter(
        self, mock_request: Mock
    ) -> None:
        """空文字列はフィルタなしとして処理"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # No filters_raw = no need to fetch columns
        mock_resp.json.side_effect = [
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw="",
        )

        assert "items" in result
        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        assert "$filter" not in params or params.get("$filter") is None

    def test_filters_invalid_json_raises_error(self) -> None:
        """不正なJSONはValueErrorを発生"""
        from app.sharepoint_list.internal import filters

        with pytest.raises(ValueError):
            filters.parse_filters("not valid json")


class TestListItemsFilterConstruction:
    """list_items のODataフィルタ構築をテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_created_datetime_is_top_level_field(
        self, mock_request: Mock
    ) -> None:
        """createdDateTime はfields/プレフィックスなしで処理"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "createdDateTime", "op": "ge", "value": "2025-12-15T00:00:00Z", "type": "datetime"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        filter_expr = params.get("$filter", "")
        # Should NOT have fields/ prefix
        assert "createdDateTime ge" in filter_expr
        assert "fields/createdDateTime" not in filter_expr

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_custom_field_uses_fields_prefix(self, mock_request: Mock) -> None:
        """カスタム列は fields/<internalName> 形式"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "Status", "op": "eq", "value": "Active"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        filter_expr = params.get("$filter", "")
        assert "fields/Status" in filter_expr

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_display_name_resolved_to_internal_name(
        self, mock_request: Mock
    ) -> None:
        """日本語表示名が内部名に解決される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        # Use Japanese display name
        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "ステータス", "op": "eq", "value": "処理中"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        filter_expr = params.get("$filter", "")
        # Should be resolved to internal name "Status"
        assert "fields/Status" in filter_expr
        assert "ステータス" not in filter_expr

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_prefer_header_added_for_fields_filter(
        self, mock_request: Mock
    ) -> None:
        """fields/を含むフィルタにPreferヘッダが付与"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "Status", "op": "eq", "value": "Active"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        headers = items_call.kwargs.get("headers") or items_call[1].get(
            "headers", {}
        )
        assert headers.get("Prefer") == "HonorNonIndexedQueriesWarning=true"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_prefer_header_not_added_for_created_datetime_only(
        self, mock_request: Mock
    ) -> None:
        """createdDateTimeのみのフィルタにはPreferヘッダなし"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "createdDateTime", "op": "ge", "value": "2025-12-15T00:00:00Z", "type": "datetime"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        headers = items_call.kwargs.get("headers") or items_call[1].get(
            "headers", {}
        )
        # Prefer header should NOT be present
        assert "Prefer" not in headers or headers.get("Prefer") is None

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_created_datetime_ge_in_filters(self, mock_request: Mock) -> None:
        """filters の createdDateTime ge が $filter に反映される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "createdDateTime", "op": "ge", "value": "2025-12-15T00:00:00Z", "type": "datetime"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        filter_expr = params.get("$filter", "")
        assert "createdDateTime ge 2025-12-15T00:00:00Z" in filter_expr

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_created_datetime_le_in_filters(self, mock_request: Mock) -> None:
        """filters の createdDateTime le が $filter に反映される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "createdDateTime", "op": "le", "value": "2025-12-31T23:59:59Z", "type": "datetime"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        filter_expr = params.get("$filter", "")
        assert "createdDateTime le 2025-12-31T23:59:59Z" in filter_expr

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_combined_filters_joined_with_and(
        self, mock_request: Mock
    ) -> None:
        """複数フィルタが and で結合される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_items_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            filters_raw='[{"field": "createdDateTime", "op": "ge", "value": "2025-12-15T00:00:00Z", "type": "datetime"}, {"field": "Status", "op": "eq", "value": "Active"}, {"field": "Priority", "op": "ge", "value": 3, "type": "number"}]',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        filter_expr = params.get("$filter", "")
        assert " and " in filter_expr
        assert "createdDateTime ge" in filter_expr
        assert "fields/Status" in filter_expr
        assert "fields/Priority" in filter_expr
