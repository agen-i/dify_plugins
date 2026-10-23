"""Tests for select_fields functionality in operations.py."""

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


def _mock_item_response() -> dict:
    return {
        "id": "item-1",
        "fields": {"Title": "Test Item", "Status": "Active"},
    }


def _mock_items_response(items: list | None = None) -> dict:
    return {"value": items or [], "@odata.nextLink": None}


class TestParseSelectFields:
    """parse_select_fields のユニットテスト"""

    def test_parse_comma_separated(self) -> None:
        """カンマ区切りをリストに変換"""
        result = operations.parse_select_fields("Title,Status")
        assert result == ["Title", "Status"]

    def test_parse_with_spaces(self) -> None:
        """スペースを含む入力を処理"""
        result = operations.parse_select_fields("Title , Status , Priority")
        assert result == ["Title", "Status", "Priority"]

    def test_parse_removes_outer_quotes_double(self) -> None:
        """外側のダブルクォートを除去"""
        result = operations.parse_select_fields('"Title"')
        assert result == ["Title"]

    def test_parse_removes_outer_quotes_single(self) -> None:
        """外側のシングルクォートを除去"""
        result = operations.parse_select_fields("'Title'")
        assert result == ["Title"]

    def test_parse_removes_per_field_quotes(self) -> None:
        """各フィールドのクォートを除去"""
        result = operations.parse_select_fields('"Title", "Status"')
        assert result == ["Title", "Status"]

    def test_parse_mixed_quotes(self) -> None:
        """混在したクォートを処理"""
        result = operations.parse_select_fields(
            "Title, \"Status\", 'Priority'"
        )
        assert result == ["Title", "Status", "Priority"]

    def test_parse_empty_input_returns_none(self) -> None:
        """空入力はNoneを返す"""
        assert operations.parse_select_fields("") is None
        assert operations.parse_select_fields(None) is None

    def test_parse_whitespace_only_returns_none(self) -> None:
        """空白のみはNoneを返す"""
        assert operations.parse_select_fields("   ") is None
        assert operations.parse_select_fields("\t\n") is None


class TestMapFieldName:
    """_map_field_name のユニットテスト"""

    def test_internal_name_passed_through(self) -> None:
        """内部名はそのまま通過"""
        display_to_name = {"ステータス": "Status"}
        name_set = {"status", "title"}

        result = operations._map_field_name(
            "Status", display_to_name, name_set
        )
        assert result == "Status"

    def test_display_name_resolved_to_internal(self) -> None:
        """表示名が内部名に解決される"""
        display_to_name = {"ステータス": "Status"}
        name_set = {"status", "title"}

        result = operations._map_field_name(
            "ステータス", display_to_name, name_set
        )
        assert result == "Status"

    def test_unknown_field_passed_through(self) -> None:
        """不明なフィールドはそのまま通過"""
        display_to_name = {"ステータス": "Status"}
        name_set = {"status", "title"}

        result = operations._map_field_name(
            "UnknownField", display_to_name, name_set
        )
        assert result == "UnknownField"

    def test_case_insensitive_matching(self) -> None:
        """大文字小文字を区別しない"""
        display_to_name = {"ステータス": "Status"}
        name_set = {"status", "title"}

        # lowercase input should match
        result = operations._map_field_name(
            "status", display_to_name, name_set
        )
        assert result == "status"


class TestResolveSelectFieldsForList:
    """resolve_select_fields_for_list のテスト"""

    def test_none_input_returns_none(self) -> None:
        """None入力はNoneを返す"""
        result = operations.resolve_select_fields_for_list(
            access_token="token",
            site_id="site-123",
            list_id="list-456",
            select_fields=None,
            display_to_name={},
            name_set=set(),
        )
        assert result is None

    def test_empty_list_returns_none(self) -> None:
        """空リストはNoneを返す"""
        result = operations.resolve_select_fields_for_list(
            access_token="token",
            site_id="site-123",
            list_id="list-456",
            select_fields=[],
            display_to_name={},
            name_set=set(),
        )
        assert result is None

    def test_display_name_resolved_to_internal(self) -> None:
        """表示名が内部名に解決される"""
        display_to_name = {"ステータス": "Status", "優先度": "Priority"}
        name_set = {"status", "priority", "title"}

        result = operations.resolve_select_fields_for_list(
            access_token="token",
            site_id="site-123",
            list_id="list-456",
            select_fields=["ステータス", "Title"],
            display_to_name=display_to_name,
            name_set=name_set,
        )
        assert result == ["Status", "Title"]

    def test_internal_name_passed_through(self) -> None:
        """内部名はそのまま通過"""
        display_to_name = {"ステータス": "Status"}
        name_set = {"status", "title"}

        result = operations.resolve_select_fields_for_list(
            access_token="token",
            site_id="site-123",
            list_id="list-456",
            select_fields=["Status", "Title"],
            display_to_name=display_to_name,
            name_set=name_set,
        )
        assert result == ["Status", "Title"]

    def test_unknown_field_passed_through(self) -> None:
        """不明なフィールドはそのまま通過"""
        display_to_name = {"ステータス": "Status"}
        name_set = {"status", "title"}

        result = operations.resolve_select_fields_for_list(
            access_token="token",
            site_id="site-123",
            list_id="list-456",
            select_fields=["UnknownField"],
            display_to_name=display_to_name,
            name_set=name_set,
        )
        assert result == ["UnknownField"]

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_fetches_columns_if_not_provided(self, mock_request: Mock) -> None:
        """display_to_name/name_setがNoneならAPI呼び出しで取得"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_columns_response()
        mock_request.return_value = mock_resp

        result = operations.resolve_select_fields_for_list(
            access_token="token",
            site_id="site-123",
            list_id="list-456",
            select_fields=["ステータス"],
            display_to_name=None,
            name_set=None,
        )
        assert result == ["Status"]
        assert mock_request.called


class TestGetItemSelectFields:
    """get_item での select_fields 適用テスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_select_fields_in_expand_clause(self, mock_request: Mock) -> None:
        """select_fieldsが$expand=fields($select=...)に含まれる"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # With GUIDs: columns + item requests only
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_item_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.get_item(
            access_token="test-token",
            target=target,
            item_id="item-1",
            select_fields=["Title", "Status"],
        )

        calls = mock_request.call_args_list
        item_call = calls[-1]
        params = item_call.kwargs.get("params") or item_call[1].get(
            "params", {}
        )
        expand = params.get("$expand", "")
        assert "fields($select=" in expand
        assert "Title" in expand
        assert "Status" in expand

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_display_name_resolved_in_expand(self, mock_request: Mock) -> None:
        """表示名が内部名に解決されて$expandに含まれる"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # With GUIDs: columns + item requests only
        mock_resp.json.side_effect = [
            _mock_columns_response(),
            _mock_item_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        # Use Japanese display name
        operations.get_item(
            access_token="test-token",
            target=target,
            item_id="item-1",
            select_fields=["ステータス"],
        )

        calls = mock_request.call_args_list
        item_call = calls[-1]
        params = item_call.kwargs.get("params") or item_call[1].get(
            "params", {}
        )
        expand = params.get("$expand", "")
        # Should be resolved to internal name
        assert "Status" in expand

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_no_select_fields_expands_all(self, mock_request: Mock) -> None:
        """select_fieldsなしは全フィールド展開"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # No select_fields = no columns request needed
        mock_resp.json.side_effect = [
            _mock_item_response(),
        ]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.get_item(
            access_token="test-token",
            target=target,
            item_id="item-1",
            select_fields=None,
        )

        calls = mock_request.call_args_list
        item_call = calls[-1]
        params = item_call.kwargs.get("params") or item_call[1].get(
            "params", {}
        )
        expand = params.get("$expand", "")
        # Should be just "fields" without $select
        assert expand == "fields"


class TestListItemsSelectFields:
    """list_items での select_fields 適用テスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_select_fields_in_expand_clause(self, mock_request: Mock) -> None:
        """select_fieldsが$expand=fields($select=...)に含まれる"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # With GUIDs: columns + items requests only
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
            select_fields="Title,Status",
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        expand = params.get("$expand", "")
        assert "fields($select=" in expand
        assert "Title" in expand
        assert "Status" in expand

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_display_name_resolved_in_expand(self, mock_request: Mock) -> None:
        """表示名が内部名に解決されて$expandに含まれる"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # With GUIDs: columns + items requests only
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
            select_fields="ステータス,優先度",
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        expand = params.get("$expand", "")
        # Should be resolved to internal names
        assert "Status" in expand
        assert "Priority" in expand

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_quoted_select_fields_parsed_correctly(
        self, mock_request: Mock
    ) -> None:
        """クォートで囲まれたselect_fieldsが正しくパース"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # With GUIDs: columns + items requests only
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
            select_fields='"Title", "Status"',
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        expand = params.get("$expand", "")
        assert "Title" in expand
        assert "Status" in expand


class TestListItemsSelectFieldsNormalization:
    """list_items の返却 fields を正規化するテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_fills_missing_selected_fields(self, mock_request: Mock) -> None:
        """
        Graph が空値のフィールドキーを省略するケースに備え、
        選択されたフィールドが fields に存在しない場合は None として補完する。
        また、典型的な別名（ID vs id / OData__ プレフィックス）も補完する。
        """
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
                        "@odata.etag": "etag",
                        "Title": "Item 1",
                        "id": "1",
                        status_internal: "処理中",
                        # Graph may return a variant key for some fields
                        f"OData__{detail_internal.lstrip('_')}": "detail",
                        # category_internal is intentionally missing
                    },
                }
            ],
            "@odata.nextLink": None,
        }

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [columns_response, items_response]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )
        result = operations.list_items(
            access_token="test-token",
            target=target,
            select_fields="ID,Title,ステータス,詳細,カテゴリ",
        )

        assert "items" in result
        assert len(result["items"]) == 1
        fields = result["items"][0]["fields"]
        assert fields["ID"] == "1"
        assert fields[detail_internal] == "detail"
        assert fields[category_internal] is None


class TestStrictSelectValidation:
    """select_fields / filters で未知列を指定した場合のエラー検証"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_unknown_select_field_raises(
        self, mock_request: Mock
    ) -> None:
        columns_response = {
            "value": [
                {"name": "Title", "displayName": "Title"},
                {
                    "name": "_x30b9__x30c6__x30fc__x30bf__x30",
                    "displayName": "ステータス",
                },
            ]
        }
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [columns_response]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        with pytest.raises(operations.GraphError):
            operations.list_items(
                access_token="test-token",
                target=target,
                select_fields="UnknownField",
            )

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_unknown_filter_field_raises(
        self, mock_request: Mock
    ) -> None:
        columns_response = {
            "value": [
                {"name": "Title", "displayName": "Title"},
                {
                    "name": "_x30b9__x30c6__x30fc__x30bf__x30",
                    "displayName": "ステータス",
                },
            ]
        }
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [columns_response]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        with pytest.raises(operations.GraphError):
            operations.list_items(
                access_token="test-token",
                target=target,
                select_fields=None,
                filters_raw='[{"field":"UnknownField","op":"eq","value":"x"}]',
            )

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_get_item_unknown_select_field_raises(
        self, mock_request: Mock
    ) -> None:
        columns_response = {
            "value": [
                {"name": "Title", "displayName": "Title"},
                {
                    "name": "_x30b9__x30c6__x30fc__x30bf__x30",
                    "displayName": "ステータス",
                },
            ]
        }
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [columns_response]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        with pytest.raises(operations.GraphError):
            operations.get_item(
                access_token="test-token",
                target=target,
                item_id="item-1",
                select_fields=["UnknownField"],
            )


class TestGetItemSelectFieldsNormalization:
    """get_item で select_fields 指定時に欠落フィールドを None で補完する"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_get_item_fills_missing_selected_fields(
        self, mock_request: Mock
    ) -> None:
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
        item_response = {
            "id": "item-1",
            "fields": {
                "Title": "Item 1",
                "id": "1",
                status_internal: "処理中",
                f"OData__{detail_internal.lstrip('_')}": "detail",
                # category_internal is missing
            },
        }

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [columns_response, item_response]
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.get_item(
            access_token="test-token",
            target=target,
            item_id="item-1",
            select_fields=["ID", "Title", "ステータス", "詳細", "カテゴリ"],
        )

        fields = result["fields"]
        assert fields["ID"] == "1"
        assert fields[detail_internal] == "detail"
        assert fields[category_internal] is None
