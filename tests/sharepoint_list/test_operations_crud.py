"""Tests for CRUD operations in operations.py."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.sharepoint_list.internal import operations, validators

# Use GUID format to bypass resolve functions
SITE_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
LIST_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


def _mock_item_response(item_id: str = "item-1") -> dict:
    return {
        "id": item_id,
        "fields": {"Title": "Test Item", "Status": "Active"},
    }


def _mock_items_response_with_pagination() -> dict:
    return {
        "value": [
            {"id": "item-1", "fields": {"Title": "Item 1"}},
            {"id": "item-2", "fields": {"Title": "Item 2"}},
        ],
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/sites/site/lists/list/items?$skiptoken=abc123",
    }


def _mock_items_response_no_pagination() -> dict:
    return {
        "value": [
            {"id": "item-1", "fields": {"Title": "Item 1"}},
        ],
    }


class TestCreateItem:
    """create_item のテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_create_item_returns_response(self, mock_request: Mock) -> None:
        """アイテム作成でレスポンスが返る"""
        mock_resp = Mock()
        mock_resp.status_code = 201
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_item_response("new-item-1")
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.create_item(
            access_token="test-token",
            target=target,
            fields={"Title": "New Item"},
        )

        assert "id" in result
        assert result["id"] == "new-item-1"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_create_item_sends_fields_in_body(
        self, mock_request: Mock
    ) -> None:
        """フィールドがリクエストボディに含まれる"""
        mock_resp = Mock()
        mock_resp.status_code = 201
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_item_response()
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.create_item(
            access_token="test-token",
            target=target,
            fields={"Title": "Test", "Status": "Active"},
        )

        calls = mock_request.call_args_list
        create_call = calls[-1]
        json_body = create_call.kwargs.get("json")
        assert json_body is not None
        assert "fields" in json_body
        assert json_body["fields"]["Title"] == "Test"


class TestUpdateItem:
    """update_item のテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_update_item_modifies_fields(self, mock_request: Mock) -> None:
        """フィールド更新が正しく行われる"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {
            "id": "item-1",
            "fields": {"Title": "Updated Title", "Status": "Active"},
        }
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.update_item(
            access_token="test-token",
            target=target,
            item_id="item-1",
            fields={"Title": "Updated Title"},
        )

        assert result["fields"]["Title"] == "Updated Title"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_update_item_uses_patch_method(self, mock_request: Mock) -> None:
        """PATCHメソッドを使用"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_item_response()
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.update_item(
            access_token="test-token",
            target=target,
            item_id="item-1",
            fields={"Title": "Updated"},
        )

        calls = mock_request.call_args_list
        update_call = calls[-1]
        assert update_call.kwargs.get("method") == "PATCH"


class TestGetItem:
    """get_item のテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_get_item_by_id(self, mock_request: Mock) -> None:
        """IDでアイテム取得"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_item_response("item-123")
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.get_item(
            access_token="test-token",
            target=target,
            item_id="item-123",
        )

        assert result["id"] == "item-123"


class TestListItemsPagination:
    """list_items のページネーションテスト"""

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_returns_items(self, mock_request: Mock) -> None:
        """アイテム一覧取得"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_items_response_no_pagination()
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
        )

        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0]["id"] == "item-1"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_pagination_token_extracted(
        self, mock_request: Mock
    ) -> None:
        """next_page_token が @odata.nextLink から抽出される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_items_response_with_pagination()
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
        )

        assert "next_page_token" in result
        assert result["next_page_token"] == "abc123"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_no_pagination_returns_none(
        self, mock_request: Mock
    ) -> None:
        """ページネーションなしの場合 next_page_token は None"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_items_response_no_pagination()
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        result = operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
        )

        assert result.get("next_page_token") is None

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_with_page_token(self, mock_request: Mock) -> None:
        """page_token が $skiptoken として使用される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_items_response_no_pagination()
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            page_token="prev-token-123",
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        assert params.get("$skiptoken") == "prev-token-123"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_list_items_page_size_capped_at_100(
        self, mock_request: Mock
    ) -> None:
        """page_size は 100 以下に制限される"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = _mock_items_response_no_pagination()
        mock_request.return_value = mock_resp

        target = validators.TargetSpec(
            site_identifier=SITE_ID, list_identifier=LIST_ID
        )

        operations.list_items(
            access_token="test-token",
            target=target,
            select_fields=None,
            page_size=200,  # Over limit
        )

        calls = mock_request.call_args_list
        items_call = calls[-1]
        params = items_call.kwargs.get("params") or items_call[1].get(
            "params", {}
        )
        assert params.get("$top") == 100


class TestResolveSiteId:
    """resolve_site_id のテスト"""

    def test_guid_identifier_returned_as_is(self) -> None:
        """GUID形式はそのまま返す"""
        result = operations.resolve_site_id(
            access_token="token",
            site_identifier=SITE_ID,
        )
        assert result == SITE_ID

    def test_comma_separated_id_returned_as_is(self) -> None:
        """カンマ区切りのIDはそのまま返す"""
        site_id = "contoso.sharepoint.com,site-guid,web-guid"
        result = operations.resolve_site_id(
            access_token="token",
            site_identifier=site_id,
        )
        assert result == site_id

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_url_resolved_via_api(self, mock_request: Mock) -> None:
        """URL形式はAPIで解決"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "resolved-site-id"}
        mock_request.return_value = mock_resp

        result = operations.resolve_site_id(
            access_token="token",
            site_identifier="https://contoso.sharepoint.com/sites/TestSite",
        )

        assert result == "resolved-site-id"


class TestResolveListId:
    """resolve_list_id のテスト"""

    def test_guid_identifier_returned_as_is(self) -> None:
        """GUID形式はそのまま返す"""
        result = operations.resolve_list_id(
            access_token="token",
            site_id=SITE_ID,
            list_identifier=LIST_ID,
        )
        assert result == LIST_ID

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_name_resolved_via_filter(self, mock_request: Mock) -> None:
        """リスト名はフィルタで解決"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {
            "value": [{"id": "resolved-list-id", "displayName": "TestList"}]
        }
        mock_request.return_value = mock_resp

        result = operations.resolve_list_id(
            access_token="token",
            site_id=SITE_ID,
            list_identifier="TestList",
        )

        assert result == "resolved-list-id"

    @patch("app.sharepoint_list.internal.http_client.requests.request")
    def test_name_not_found_raises_error(self, mock_request: Mock) -> None:
        """リスト名が見つからない場合はエラー"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.side_effect = [
            {"value": []},  # filter returns empty
            {"value": []},  # enumerate returns empty
        ]
        mock_request.return_value = mock_resp

        with pytest.raises(operations.GraphError) as exc_info:
            operations.resolve_list_id(
                access_token="token",
                site_id=SITE_ID,
                list_identifier="NonExistentList",
            )

        assert "not found" in str(exc_info.value)
