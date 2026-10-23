from __future__ import annotations

import pytest

from app.sharepoint_list.internal import filters


def test_parse_filters_json_list() -> None:
    raw = """
    [
      {"field": "ステータス", "op": "eq", "value": "処理中"},
      {"field": "Priority", "op": "ge", "value": 3}
    ]
    """
    result = filters.parse_filters(raw)
    assert len(result) == 2
    assert result[0].field == "ステータス"
    assert result[0].op == "eq"
    assert result[0].value == "処理中"
    assert result[1].op == "ge"
    assert result[1].value == 3


def test_build_filter_fragment_eq_escapes_string() -> None:
    cond = filters.FilterCondition(field="Title", op="eq", value="O'Reilly")
    fragment = filters.build_filter_fragment(cond, "fields/Title")
    assert fragment == "fields/Title eq 'O''Reilly'"


def test_build_filter_fragment_contains() -> None:
    cond = filters.FilterCondition(
        field="Title", op="contains", value="Sample"
    )
    fragment = filters.build_filter_fragment(cond, "fields/Title")
    assert fragment == "contains(fields/Title, 'Sample')"


def test_build_filter_fragment_bool_and_datetime() -> None:
    cond = filters.FilterCondition(
        field="Flag", op="eq", value=True, value_type="bool"
    )
    frag_bool = filters.build_filter_fragment(cond, "fields/Flag")
    assert frag_bool == "fields/Flag eq true"

    cond_dt = filters.FilterCondition(
        field="createdDateTime",
        op="ge",
        value="2025-12-15T00:00:00Z",
        value_type="datetime",
    )
    frag_dt = filters.build_filter_fragment(cond_dt, "createdDateTime")
    assert frag_dt == "createdDateTime ge 2025-12-15T00:00:00Z"

    cond_field_dt = filters.FilterCondition(
        field="Created",
        op="gt",
        value="2025-12-16T15:00:00Z",
        value_type="datetime",
    )
    frag_field_dt = filters.build_filter_fragment(
        cond_field_dt, "fields/Created"
    )
    assert frag_field_dt == "fields/Created gt '2025-12-16T15:00:00Z'"


def test_parse_filters_json_with_explicit_type() -> None:
    raw = '[{"field": "Priority", "op": "gt", "value": "3", "type": "number"}]'
    result = filters.parse_filters(raw)
    assert result[0].value_type == "number"
    assert result[0].value == "3"


def test_parse_filters_json_single_object() -> None:
    raw = '{"field": "Priority", "op": "ne", "value": 1}'
    result = filters.parse_filters(raw)
    assert len(result) == 1
    assert result[0].op == "ne"


def test_parse_filters_operator_alias_rejected() -> None:
    raw = '[{"field": "Status", "operator": "eq", "value": "処理中"}]'
    with pytest.raises(ValueError) as exc:
        filters.parse_filters(raw)
    assert "field and op" in str(exc.value)


def test_parse_filters_empty_string_returns_empty() -> None:
    assert filters.parse_filters("   ") == []


def test_parse_filters_unsupported_operator_raises() -> None:
    raw = '[{"field": "X", "op": "invalid", "value": 1}]'
    with pytest.raises(ValueError) as exc:
        filters.parse_filters(raw)
    assert "Unsupported operator" in str(exc.value)


def test_parse_filters_json_invalid_entry_raises() -> None:
    raw = "[1]"
    with pytest.raises(ValueError) as exc:
        filters.parse_filters(raw)
    assert "must be an object" in str(exc.value)


def test_parse_filters_json_missing_field_op_raises() -> None:
    raw = '[{"value": 1}]'
    with pytest.raises(ValueError) as exc:
        filters.parse_filters(raw)
    assert "field and op" in str(exc.value)


def test_format_odata_value_types() -> None:
    assert filters.format_odata_value(10, "number") == "10"
    assert filters.format_odata_value(True, "bool") == "true"
    assert filters.format_odata_value("txt", "string") == "'txt'"


def test_parse_filters_non_json_input_raises() -> None:
    with pytest.raises(ValueError) as exc:
        filters.parse_filters("field__eq=value")
    assert "JSON" in str(exc.value)
