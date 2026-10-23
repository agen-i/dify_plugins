from app.sharepoint_list.internal import operations


def test_map_fields_to_internal_resolves_display_name() -> None:
    display_to_name = {"ステータス": "StatusInternal"}
    name_set = {"title"}
    fields = {"ステータス": "処理中", "Title": "Hello"}

    mapped = operations.map_fields_to_internal(
        fields, display_to_name, name_set
    )

    assert mapped["StatusInternal"] == "処理中"
    # internal name (case-insensitive set) keeps the original key
    assert mapped["Title"] == "Hello"


def test_map_fields_to_internal_keeps_unknown() -> None:
    display_to_name = {"ステータス": "StatusInternal"}
    name_set: set[str] = set()
    fields = {"Unknown": 1}

    mapped = operations.map_fields_to_internal(
        fields, display_to_name, name_set
    )

    assert "Unknown" in mapped
    assert mapped["Unknown"] == 1
