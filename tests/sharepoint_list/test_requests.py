import pytest

from app.sharepoint_list.internal import request_builders


class TestBuildSiteGetRequest:
    def test_builds_from_site_url(self) -> None:
        req = request_builders.build_site_get_by_path_request(
            site_url="https://contoso.sharepoint.com/sites/demo"
        )
        assert req.method == "GET"
        assert (
            req.url
            == "https://graph.microsoft.com/v1.0/sites/contoso.sharepoint.com:/sites/demo"
        )
        assert req.params == {}

    def test_requires_site_url(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_site_get_by_path_request(site_url="")


class TestBuildListRequests:
    def test_builds_filter_request(self) -> None:
        req = request_builders.build_list_filter_request(
            site_id="site123", list_name="Tasks"
        )
        assert req.method == "GET"
        assert (
            req.url == "https://graph.microsoft.com/v1.0/sites/site123/lists"
        )
        assert req.params == {"$filter": "displayName eq 'Tasks'"}

    def test_filter_request_requires_inputs(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_list_filter_request(
                site_id="", list_name="Tasks"
            )
        with pytest.raises(ValueError):
            request_builders.build_list_filter_request(
                site_id="site123", list_name=""
            )

    def test_builds_enumerate_request(self) -> None:
        req = request_builders.build_list_enumerate_request(site_id="site123")
        assert req.method == "GET"
        assert (
            req.url == "https://graph.microsoft.com/v1.0/sites/site123/lists"
        )
        assert req.params == {}

    def test_enumerate_requires_site_id(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_list_enumerate_request(site_id="")


class TestBuildListItemRequests:
    def test_build_create_item_request(self) -> None:
        req = request_builders.build_create_item_request(
            site_id="site123", list_id="list456", fields={"Title": "Hello"}
        )
        assert req.method == "POST"
        assert (
            req.url
            == "https://graph.microsoft.com/v1.0/sites/site123/lists/list456/items"
        )
        assert req.json == {"fields": {"Title": "Hello"}}

    def test_create_requires_fields_object(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_create_item_request(
                site_id="site123", list_id="list456", fields={}
            )

    def test_create_requires_site_and_list(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_create_item_request(
                site_id="", list_id="list456", fields={"Title": "x"}
            )
        with pytest.raises(ValueError):
            request_builders.build_create_item_request(
                site_id="site123", list_id="", fields={"Title": "x"}
            )

    def test_build_update_item_request(self) -> None:
        req = request_builders.build_update_item_request(
            site_id="site123",
            list_id="list456",
            item_id="99",
            fields={"Title": "Updated"},
        )
        assert req.method == "PATCH"
        assert req.url == (
            "https://graph.microsoft.com/v1.0/sites/site123/lists/list456/items/99/fields"
        )
        assert req.json == {"Title": "Updated"}

    def test_update_requires_item_id_and_fields(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_update_item_request(
                site_id="site123",
                list_id="list456",
                item_id="",
                fields={"Title": "x"},
            )
        with pytest.raises(ValueError):
            request_builders.build_update_item_request(
                site_id="site123", list_id="list456", item_id="99", fields={}
            )

    def test_update_requires_site_and_list(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_update_item_request(
                site_id="",
                list_id="list456",
                item_id="99",
                fields={"Title": "x"},
            )
        with pytest.raises(ValueError):
            request_builders.build_update_item_request(
                site_id="site123",
                list_id="",
                item_id="99",
                fields={"Title": "x"},
            )

    def test_build_get_item_request_with_select(self) -> None:
        req = request_builders.build_get_item_request(
            site_id="site123",
            list_id="list456",
            item_id="99",
            select_fields=["Title", "Status"],
        )
        assert req.method == "GET"
        assert req.url == (
            "https://graph.microsoft.com/v1.0/sites/site123/lists/list456/items/99"
        )
        assert req.params == {"$expand": "fields($select=Title,Status)"}

    def test_build_get_item_request_without_select(self) -> None:
        req = request_builders.build_get_item_request(
            site_id="site123",
            list_id="list456",
            item_id="99",
            select_fields=None,
        )
        assert req.params == {"$expand": "fields"}

    def test_get_item_requires_inputs(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_get_item_request(
                site_id="", list_id="list456", item_id="99", select_fields=None
            )
        with pytest.raises(ValueError):
            request_builders.build_get_item_request(
                site_id="site123", list_id="", item_id="99", select_fields=None
            )
        with pytest.raises(ValueError):
            request_builders.build_get_item_request(
                site_id="site123",
                list_id="list456",
                item_id="",
                select_fields=None,
            )


class TestBuildListColumnsRequest:
    def test_build_list_columns_request(self) -> None:
        req = request_builders.build_list_columns_request(
            site_id="site123", list_id="list456"
        )
        assert req.method == "GET"
        assert (
            req.url
            == "https://graph.microsoft.com/v1.0/sites/site123/lists/list456/columns"
        )
        assert req.params == {"$select": "name,displayName,choice"}

    def test_list_columns_requires_inputs(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_list_columns_request(
                site_id="", list_id="x"
            )
        with pytest.raises(ValueError):
            request_builders.build_list_columns_request(
                site_id="x", list_id=""
            )


class TestBuildListItemsRequest:
    def test_build_list_items_request_minimal(self) -> None:
        req = request_builders.build_list_items_request(
            site_id="site123", list_id="list456", top=20
        )
        assert req.method == "GET"
        assert (
            req.url
            == "https://graph.microsoft.com/v1.0/sites/site123/lists/list456/items"
        )
        assert req.params["$top"] == 20
        assert req.params["$expand"] == "fields"

    def test_build_list_items_request_with_all_options(self) -> None:
        req = request_builders.build_list_items_request(
            site_id="site123",
            list_id="list456",
            top=10,
            skiptoken="token1",
            filter_expr="fields/Status eq 'InProgress'",
            select_fields=["Title", "Status"],
            orderby="createdDateTime desc",
        )
        assert req.params["$top"] == 10
        assert req.params["$skiptoken"] == "token1"
        assert req.params["$filter"] == "fields/Status eq 'InProgress'"
        assert req.params["$orderby"] == "createdDateTime desc"
        assert req.params["$expand"] == "fields($select=Title,Status)"

    def test_list_items_requires_inputs(self) -> None:
        with pytest.raises(ValueError):
            request_builders.build_list_items_request(
                site_id="", list_id="x", top=1
            )
        with pytest.raises(ValueError):
            request_builders.build_list_items_request(
                site_id="x", list_id="", top=1
            )
        with pytest.raises(ValueError):
            request_builders.build_list_items_request(
                site_id="x", list_id="y", top=0
            )
