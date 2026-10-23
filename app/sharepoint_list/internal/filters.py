from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

ALLOWED_OPS = {
    "eq",
    "ne",
    "gt",
    "ge",
    "lt",
    "le",
    "contains",
    "startswith",
    "endswith",
}


@dataclass
class FilterCondition:
    field: str
    op: str
    value: Any
    value_type: str | None = None


def _escape_string(value: str) -> str:
    return value.replace("'", "''")


def format_odata_value(value: Any, value_type: str | None) -> str:
    """
    Build OData literal. Strings are quoted; numbers/bools stay unquoted.
    Datetime stays as-is (to align with existing createdDateTime handling).
    """
    t = (value_type or "").lower()
    if t == "number":
        return str(value)
    if t == "bool":
        return "true" if bool(value) else "false"
    if t == "datetime":
        return str(value)

    # default: string
    if not isinstance(value, str):
        value = str(value)
    return f"'{_escape_string(value)}'"


def build_filter_fragment(cond: FilterCondition, mapped_field: str) -> str:
    op = cond.op.lower()
    if op not in ALLOWED_OPS:
        raise ValueError(f"Unsupported operator: {op}")

    value_type = cond.value_type.lower() if cond.value_type else None

    if op in {"contains", "startswith", "endswith"}:
        val_repr = format_odata_value(cond.value, value_type or "string")
        return f"{op}({mapped_field}, {val_repr})"

    if value_type == "datetime" and mapped_field.startswith("fields/"):
        # Graph list item fields are filtered as strings; quote datetime values.
        val_repr = format_odata_value(cond.value, "string")
    else:
        val_repr = format_odata_value(cond.value, value_type)
    return f"{mapped_field} {op} {val_repr}"


def parse_filters(filters_raw: str) -> list[FilterCondition]:
    """
    Parse filters string into FilterCondition list.
    Accepts JSON array (recommended) or single JSON object.
    """
    text = filters_raw.strip()
    if not text:
        return []

    if not (text.startswith("[") or text.startswith("{")):
        raise ValueError("filters must be provided as JSON array or object")

    parsed = json.loads(text)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise ValueError("filters JSON must be an array or object")

    results: list[FilterCondition] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("each filter entry must be an object")
        field = str(item.get("field") or "").strip()
        op_raw = item.get("op")
        op = str(op_raw or "").strip().lower()
        if not field or not op:
            raise ValueError("filter entry must include field and op")
        if op not in ALLOWED_OPS:
            raise ValueError(f"Unsupported operator: {op}")
        value = item.get("value")
        value_type = item.get("type")
        results.append(
            FilterCondition(
                field=field, op=op, value=value, value_type=value_type
            )
        )
    return results
