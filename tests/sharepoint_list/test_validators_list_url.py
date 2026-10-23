import pytest

from app.sharepoint_list.internal import validators


class TestParseListUrl:
    def test_parses_allitems_url(self) -> None:
        site_url, list_name = validators.parse_list_url(
            "https://contoso.sharepoint.com/sites/demo/Lists/MyList/AllItems.aspx"
        )
        assert site_url == "https://contoso.sharepoint.com/sites/demo"
        assert list_name == "MyList"

    def test_parses_guid_list_id(self) -> None:
        site_url, list_id = validators.parse_list_url(
            "https://contoso.sharepoint.com/sites/demo/Lists/12345678-1234-1234-1234-1234567890ab/AllItems.aspx"
        )
        assert site_url == "https://contoso.sharepoint.com/sites/demo"
        assert list_id == "12345678-1234-1234-1234-1234567890ab"

    @pytest.mark.parametrize(
        "bad_url",
        [
            "not-a-url",
            "https://contoso.sharepoint.com/sites/demo",  # missing Lists segment
            "https://example.com/sites/demo/Lists/MyList/AllItems.aspx",  # not sharepoint host
        ],
    )
    def test_invalid_url_raises(self, bad_url: str) -> None:
        with pytest.raises(ValueError):
            validators.parse_list_url(bad_url)
