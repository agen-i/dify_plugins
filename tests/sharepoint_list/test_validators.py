import pytest

from app.sharepoint_list.internal import validators


class TestValidateTarget:
    def test_requires_site(self) -> None:
        with pytest.raises(ValueError):
            validators.validate_target(
                site_identifier=None,
                list_identifier="list1",
            )

    def test_requires_list(self) -> None:
        with pytest.raises(ValueError):
            validators.validate_target(
                site_identifier="site1",
                list_identifier=None,
            )

    def test_accepts_site_identifier_and_list_identifier(self) -> None:
        target = validators.validate_target(
            site_identifier="site1", list_identifier="list1"
        )
        assert target.site_identifier == "site1"
        assert target.list_identifier == "list1"

    def test_strips_whitespace(self) -> None:
        target = validators.validate_target(
            site_identifier=" https://contoso.sharepoint.com/sites/demo ",
            list_identifier=" Tasks ",
        )
        assert (
            target.site_identifier
            == "https://contoso.sharepoint.com/sites/demo"
        )
        assert target.list_identifier == "Tasks"

    def test_rejects_blank_strings(self) -> None:
        with pytest.raises(ValueError):
            validators.validate_target(
                site_identifier="   ", list_identifier="x"
            )
        with pytest.raises(ValueError):
            validators.validate_target(
                site_identifier="x", list_identifier="   "
            )


class TestParseFieldsJson:
    def test_parses_valid_json_object(self) -> None:
        fields = validators.parse_fields_json('{"Title": "Widget"}')
        assert fields == {"Title": "Widget"}

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(ValueError):
            validators.parse_fields_json("not-json")

    def test_rejects_non_object(self) -> None:
        with pytest.raises(ValueError):
            validators.parse_fields_json('"just a string"')

    def test_none_or_empty_returns_empty_dict(self) -> None:
        assert validators.parse_fields_json(None) == {}
        assert validators.parse_fields_json("") == {}
        assert validators.parse_fields_json("   ") == {}


class TestEnsureItemId:
    def test_update_requires_item_id(self) -> None:
        with pytest.raises(ValueError):
            validators.ensure_item_id(operation="update", item_id=None)

    def test_read_requires_item_id(self) -> None:
        with pytest.raises(ValueError):
            validators.ensure_item_id(operation="read", item_id=None)

    def test_create_does_not_require_item_id(self) -> None:
        # Should not raise
        validators.ensure_item_id(operation="create", item_id=None)


class TestParseSiteUrl:
    def test_parses_site_url(self) -> None:
        host, path = validators.parse_site_url(
            "https://contoso.sharepoint.com/sites/demo"
        )
        assert host == "contoso.sharepoint.com"
        assert path == "sites/demo"

    def test_parses_with_trailing_slash(self) -> None:
        host, path = validators.parse_site_url(
            "https://contoso.sharepoint.com/sites/demo/"
        )
        assert host == "contoso.sharepoint.com"
        assert path == "sites/demo"

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError):
            validators.parse_site_url("https://example.com/not-sharepoint")

    def test_malformed_url_raises(self) -> None:
        with pytest.raises(ValueError):
            validators.parse_site_url("not-a-url")

    def test_missing_site_path_raises(self) -> None:
        with pytest.raises(ValueError):
            validators.parse_site_url("https://contoso.sharepoint.com/")


class TestIsGuid:
    def test_valid_guid(self) -> None:
        assert (
            validators.is_guid("c65709ac-de79-43e5-8004-3cb972a47f07") is True
        )

    def test_invalid_guid(self) -> None:
        assert validators.is_guid("not-a-guid") is False
