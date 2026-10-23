from __future__ import annotations

import os
import urllib.parse
from datetime import UTC, datetime
from typing import Any

from . import debug_logging, filters, http_client, request_builders, validators


class GraphError(http_client.GraphAPIError):
    """Raised when Graph API returns an error response. (Legacy alias)"""


def _send_request(
    spec: request_builders.RequestSpec,
    access_token: str,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send request with retry logic. Wrapper for http_client."""
    if _is_debug_log_enabled():
        safe_headers = {
            k: v
            for k, v in (extra_headers or {}).items()
            if k.lower() != "authorization"
        }
        _log_debug(
            location="operations.py:_send_request",
            message="request",
            data={
                "url": spec.url,
                "params": spec.params,
                "json": spec.json is not None,
                "headers": safe_headers,
            },
        )

    try:
        return http_client.send_request_with_retry(
            spec=spec,
            access_token=access_token,
            extra_headers=extra_headers,
        )
    except http_client.GraphAPIError as e:
        if _is_debug_log_enabled():
            _log_debug(
                location="operations.py:_send_request",
                message="error",
                data={
                    "status": e.status_code,
                    "text": (e.response_text or "")[:200],
                    "error_type": type(e).__name__,
                },
            )
        raise


def _is_debug_log_enabled() -> bool:
    val = os.getenv("SHAREPOINT_LIST_DEBUG_LOG", "").lower()
    return val in {"1", "true", "yes", "on"}


def _log_debug(
    location: str,
    message: str,
    data: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> None:
    if not _is_debug_log_enabled():
        return
    try:
        now = datetime.now(UTC)
        ts = int(now.timestamp() * 1000)
        timestamp = now.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        log_payload = {
            "ts": ts,
            "timestamp": timestamp,
            "sessionId": "debug-session",
            "runId": os.getenv("SHAREPOINT_LIST_DEBUG_RUN_ID", "run1"),
            "location": location,
            "message": message,
            "data": data,
        }
        if extra:
            log_payload.update(extra)
        debug_logging.emit_debug_payload(log_payload)
    except Exception:
        # fail silently to avoid impacting main flow
        pass


def resolve_site_id(access_token: str, site_identifier: str) -> str:
    """
    Accepts site_identifier that may be:
    - URL (starts with http)
    - site ID (host,siteId,webId) or GUID-like token
    - site path token (best-effort; treated as site ID)
    """
    if site_identifier.startswith("http"):
        spec = request_builders.build_site_get_by_path_request(site_identifier)
        data = _send_request(spec, access_token)
        resolved = data.get("id")
        if not resolved:
            raise GraphError("Failed to resolve site_id from site_url")
        return resolved

    # If identifier already looks like site ID (contains commas or GUID), use as-is
    if "," in site_identifier or validators.is_guid(site_identifier):
        return site_identifier

    # Fallback: treat as ID token (best-effort)
    return site_identifier


def resolve_list_id(
    access_token: str, site_id: str, list_identifier: str
) -> str:
    _log_debug(
        location="operations.py:resolve_list_id",
        message="entry",
        data={
            "list_identifier_len": len(str(list_identifier)),
            "list_identifier_is_guid": validators.is_guid(list_identifier),
            "list_identifier_is_ascii": str(list_identifier).isascii(),
            "site_id_comma_count": str(site_id).count(","),
        },
    )

    if validators.is_guid(list_identifier):
        return list_identifier

    # Try filter by displayName
    filter_req = request_builders.build_list_filter_request(
        site_id=site_id, list_name=list_identifier
    )
    filter_data = _send_request(filter_req, access_token)
    values = filter_data.get("value") or []

    _log_debug(
        location="operations.py:resolve_list_id",
        message="displayName_filter_result",
        data={"filtered_count": len(values)},
    )

    if len(values) == 1:
        found_id = values[0].get("id")
        if found_id:
            return found_id

    # Fallback enumerate
    enum_req = request_builders.build_list_enumerate_request(site_id=site_id)
    # include webUrl for diagnostics/matching
    enum_req.params = {"$select": "id,displayName,webUrl"}
    enum_data = _send_request(enum_req, access_token)
    enum_values = enum_data.get("value", []) or []
    raw_identifier = str(list_identifier).strip()
    decoded_identifier = urllib.parse.unquote(raw_identifier)
    expected_path_fragments = {
        f"/lists/{raw_identifier}".lower(),
        f"/lists/{decoded_identifier}".lower(),
    }
    weburl_match_count = 0
    weburl_match_id: str | None = None
    first_weburl_match: dict[str, Any] | None = None
    for item in enum_values:
        if item.get("displayName") == list_identifier:
            found_id = item.get("id")
            if found_id:
                return found_id
        web_url = item.get("webUrl")
        if isinstance(web_url, str) and web_url:
            try:
                web_path = urllib.parse.urlparse(web_url).path or ""
            except Exception:
                web_path = ""
            web_path_decoded = urllib.parse.unquote(web_path)
            web_path_lower = web_path.lower()
            web_path_decoded_lower = web_path_decoded.lower()
            if any(
                frag in web_path_lower or frag in web_path_decoded_lower
                for frag in expected_path_fragments
            ):
                weburl_match_count += 1
                if first_weburl_match is None:
                    display_name = item.get("displayName")
                    display_name_str = (
                        display_name if isinstance(display_name, str) else ""
                    )
                    first_weburl_match = {
                        "webUrl_path": web_path,
                        "webUrl_path_decoded": web_path_decoded,
                        "displayName_equals_identifier": (
                            display_name_str == list_identifier
                        ),
                        "displayName_is_ascii": display_name_str.isascii(),
                        "displayName_len": len(display_name_str),
                        "id_present": bool(item.get("id")),
                    }
                if weburl_match_id is None and isinstance(item.get("id"), str):
                    weburl_match_id = item.get("id")

    _log_debug(
        location="operations.py:resolve_list_id",
        message="enumerate_result",
        data={
            "enumerated_count": len(enum_values),
            "expected_path_fragments": sorted(expected_path_fragments),
            "webUrl_match_count": weburl_match_count,
            "first_webUrl_match": first_weburl_match,
        },
    )

    if weburl_match_count == 1 and weburl_match_id:
        _log_debug(
            location="operations.py:resolve_list_id",
            message="resolved_via_webUrl",
            data={
                "resolved_list_id_present": True,
                "webUrl_match_count": weburl_match_count,
            },
        )
        return weburl_match_id

    if weburl_match_count > 1:
        _log_debug(
            location="operations.py:resolve_list_id",
            message="webUrl_match_ambiguous",
            data={"webUrl_match_count": weburl_match_count},
        )
        raise GraphError(
            "List identifier is ambiguous by webUrl. "
            "Please use list GUID in list_url."
        )

    raise GraphError(f"List '{list_identifier}' not found in site '{site_id}'")


def create_item(
    access_token: str, target: validators.TargetSpec, fields: dict[str, Any]
) -> dict[str, Any]:
    site_id = resolve_site_id(access_token, target.site_identifier)
    list_id = resolve_list_id(access_token, site_id, target.list_identifier)
    display_to_name, name_set, _ = _get_column_maps(
        access_token, site_id, list_id
    )
    mapped_fields = map_fields_to_internal(fields, display_to_name, name_set)
    spec = request_builders.build_create_item_request(
        site_id=site_id, list_id=list_id, fields=mapped_fields
    )
    return _send_request(spec, access_token)


def update_item(
    access_token: str,
    target: validators.TargetSpec,
    item_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    site_id = resolve_site_id(access_token, target.site_identifier)
    list_id = resolve_list_id(access_token, site_id, target.list_identifier)
    display_to_name, name_set, _ = _get_column_maps(
        access_token, site_id, list_id
    )
    mapped_fields = map_fields_to_internal(fields, display_to_name, name_set)
    spec = request_builders.build_update_item_request(
        site_id=site_id, list_id=list_id, item_id=item_id, fields=mapped_fields
    )
    return _send_request(spec, access_token)


def get_item(
    access_token: str,
    target: validators.TargetSpec,
    item_id: str,
    select_fields: list[str] | None = None,
) -> dict[str, Any]:
    site_id = resolve_site_id(access_token, target.site_identifier)
    list_id = resolve_list_id(access_token, site_id, target.list_identifier)
    mapped_select: list[str] | None = None
    columns_data: dict[str, Any] | None = None
    display_to_name: dict[str, str] = {}
    name_set: set[str] = set()
    if select_fields:
        display_to_name, name_set, columns_data = _get_column_maps(
            access_token, site_id, list_id
        )
        _validate_requested_fields(
            requested_fields=select_fields,
            display_to_name=display_to_name,
            name_set=name_set,
            allow_special={"id"},
        )
        mapped_select = resolve_select_fields_for_list(
            access_token=access_token,
            site_id=site_id,
            list_id=list_id,
            select_fields=select_fields,
            display_to_name=display_to_name,
            name_set=name_set,
            columns_data=columns_data,
        )
    else:
        mapped_select = resolve_select_fields_for_list(
            access_token=access_token,
            site_id=site_id,
            list_id=list_id,
            select_fields=None,
        )

    spec = request_builders.build_get_item_request(
        site_id=site_id,
        list_id=list_id,
        item_id=item_id,
        select_fields=mapped_select,
    )
    data = _send_request(spec, access_token)

    if mapped_select and isinstance(data, dict):
        fields_obj = data.get("fields")
        if isinstance(fields_obj, dict):
            lower_key_map = {
                k.lower(): k for k in fields_obj.keys() if isinstance(k, str)
            }
            for field_name in mapped_select:
                if not isinstance(field_name, str) or not field_name:
                    continue
                if field_name in fields_obj:
                    continue
                existing = lower_key_map.get(field_name.lower())
                if existing and existing in fields_obj:
                    fields_obj[field_name] = fields_obj.get(existing)
                    continue
                if field_name.startswith("_"):
                    alt = f"OData__{field_name.lstrip('_')}"
                    if alt in fields_obj:
                        fields_obj[field_name] = fields_obj.get(alt)
                        continue
                fields_obj[field_name] = None

    return data


def parse_select_fields(select_fields: str | None) -> list[str] | None:
    if not select_fields:
        return None
    text = select_fields.strip()
    # select_fields が '"Title"' のように全体をクォートして渡された場合に備え、
    # 外側クォートを除去
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1]
    parts = []
    for raw in text.split(","):
        cleaned = raw.strip().strip('"').strip("'")
        if cleaned:
            parts.append(cleaned)
    return parts or None


def _get_column_maps(
    access_token: str, site_id: str, list_id: str
) -> tuple[dict[str, str], set[str], dict[str, Any]]:
    """
    Fetch columns once and return (display_to_name, name_set, raw_columns_data).
    """
    columns_spec = request_builders.build_list_columns_request(
        site_id=site_id, list_id=list_id
    )
    columns_data = _send_request(columns_spec, access_token)
    display_to_name: dict[str, str] = {}
    name_set: set[str] = set()
    for col in columns_data.get("value", []):
        display = col.get("displayName")
        name = col.get("name")
        if isinstance(name, str):
            name_set.add(name.lower())
        if isinstance(display, str) and isinstance(name, str):
            display_to_name[display.lower()] = name
    return display_to_name, name_set, columns_data


def _validate_requested_fields(
    requested_fields: list[str] | None,
    display_to_name: dict[str, str],
    name_set: set[str],
    *,
    allow_special: set[str] | None = None,
) -> None:
    """
    Ensure all requested field identifiers exist in the list.
    - requested_fields: list of raw names (internal or display).
    - allow_special: lowercased names that are allowed even if not in columns
      (e.g., id, createdDateTime).
    Raises GraphError when any field is unknown.
    """
    if not requested_fields:
        return

    allow = {s.lower() for s in (allow_special or set())}
    unknown: list[str] = []

    for raw in requested_fields:
        if not isinstance(raw, str) or not raw.strip():
            unknown.append(str(raw))
            continue
        lowered = raw.lower()
        if lowered in allow:
            continue
        if lowered in name_set:
            continue
        if lowered in display_to_name:
            continue
        unknown.append(raw)

    if unknown:
        joined = ", ".join(unknown)
        raise GraphError(f"Field(s) not found in list: {joined}")


def _map_field_name(
    raw: str, display_to_name: dict[str, str], name_set: set[str]
) -> str:
    lowered = raw.lower()
    if lowered in name_set:
        return raw
    if lowered in display_to_name:
        return display_to_name[lowered]
    return raw


def map_fields_to_internal(
    fields: dict[str, Any],
    display_to_name: dict[str, str],
    name_set: set[str],
) -> dict[str, Any]:
    """
    Map field keys that may be given as displayName to internal column names.
    Unknown keys are kept as-is.
    """
    mapped: dict[str, Any] = {}
    for key, value in fields.items():
        mapped_key = _map_field_name(str(key), display_to_name, name_set)
        mapped[mapped_key] = value
    return mapped


def resolve_select_fields_for_list(
    access_token: str,
    site_id: str,
    list_id: str,
    select_fields: list[str] | None,
    *,
    display_to_name: dict[str, str] | None = None,
    name_set: set[str] | None = None,
    columns_data: dict[str, Any] | None = None,
) -> list[str] | None:
    """
    Map select_fields that may be given as displayName (e.g., 日本語の列表示名)
    to internal column names. If a field already matches an internal name, it is kept.
    """
    if not select_fields:
        return None

    if display_to_name is None or name_set is None:
        display_to_name, name_set, _ = _get_column_maps(
            access_token, site_id, list_id
        )

    resolved: list[str] = []
    for raw in select_fields:
        lower = raw.lower()
        if lower in name_set:
            resolved.append(raw)
        elif lower in display_to_name:
            resolved.append(display_to_name[lower])
        else:
            resolved.append(raw)
    return resolved or None


def get_choice_field_info(
    access_token: str,
    site_identifier: str,
    list_identifier: str,
    field_identifier: str,
) -> dict[str, Any]:
    """
    Return choice field metadata and choices.
    - field_identifier: internal name or display name (case-insensitive)
    """
    site_id = resolve_site_id(access_token, site_identifier)
    list_id = resolve_list_id(access_token, site_id, list_identifier)

    columns_spec = request_builders.build_list_columns_request(
        site_id=site_id, list_id=list_id
    )
    columns_data = _send_request(columns_spec, access_token)

    if _is_debug_log_enabled():
        _log_debug(
            location="operations.py:get_choice_field_info",
            message="columns fetched",
            data={
                "field_identifier": field_identifier,
                "columns_count": (
                    len(columns_data.get("value", []))
                    if isinstance(columns_data, dict)
                    else None
                ),
                "names": [
                    c.get("name")
                    for c in (
                        columns_data.get("value", [])
                        if isinstance(columns_data, dict)
                        else []
                    )
                ],
                "displayNames": [
                    c.get("displayName")
                    for c in (
                        columns_data.get("value", [])
                        if isinstance(columns_data, dict)
                        else []
                    )
                ],
            },
            extra={"hypothesisId": "H1"},
        )

    target_col = None
    lowered = field_identifier.lower()
    for col in columns_data.get("value", []):
        name = col.get("name")
        display = col.get("displayName")
        if isinstance(name, str) and name.lower() == lowered:
            target_col = col
            break
        if isinstance(display, str) and display.lower() == lowered:
            target_col = col
            break

    if not target_col:
        raise GraphError(
            f"Field '{field_identifier}' not found in list '{list_identifier}'"
        )

    if _is_debug_log_enabled():
        _log_debug(
            location="operations.py:get_choice_field_info",
            message="column matched",
            data={
                "field_identifier": field_identifier,
                "name": target_col.get("name"),
                "displayName": target_col.get("displayName"),
                "columnType": target_col.get("columnType"),
                "choice_keys": list((target_col.get("choice") or {}).keys()),
            },
            extra={"hypothesisId": "H2"},
        )

    column_type = target_col.get("columnType")
    choice = target_col.get("choice") or {}
    is_choice = (column_type == "choice") or bool(choice)
    if not is_choice:
        err_msg = (
            f"Field '{field_identifier}' is not a choice column "
            f"(columnType={column_type})"
        )
        raise GraphError(err_msg)

    if _is_debug_log_enabled():
        _log_debug(
            location="operations.py:get_choice_field_info",
            message="choice payload",
            data={
                "displayName": target_col.get("displayName"),
                "name": target_col.get("name"),
                "allowMultipleSelections": choice.get(
                    "allowMultipleSelections"
                ),
                "defaultValue": choice.get("defaultValue"),
                "choices_len": len(choice.get("choices") or []),
            },
            extra={"hypothesisId": "H3"},
        )

    return {
        "displayName": target_col.get("displayName"),
        "name": target_col.get("name"),
        "choices": choice.get("choices"),
        "allowMultipleSelections": choice.get("allowMultipleSelections"),
        "defaultValue": choice.get("defaultValue"),
    }


def list_items(
    access_token: str,
    target: validators.TargetSpec,
    select_fields: str | None,
    page_size: int = 20,
    page_token: str | None = None,
    filters_raw: str | None = None,
) -> dict[str, Any]:
    site_id = resolve_site_id(access_token, target.site_identifier)
    list_id = resolve_list_id(access_token, site_id, target.list_identifier)

    need_columns = bool(select_fields) or bool(filters_raw)
    display_to_name: dict[str, str] = {}
    name_set: set[str] = set()
    columns_data: dict[str, Any] | None = None
    if need_columns:
        display_to_name, name_set, columns_data = _get_column_maps(
            access_token, site_id, list_id
        )

    # resolve select fields (displayName or internal)
    parsed_select = parse_select_fields(select_fields)
    if need_columns:
        _validate_requested_fields(
            requested_fields=parsed_select,
            display_to_name=display_to_name,
            name_set=name_set,
            allow_special={"id"},
        )
    mapped_select = resolve_select_fields_for_list(
        access_token=access_token,
        site_id=site_id,
        list_id=list_id,
        select_fields=parsed_select,
        display_to_name=display_to_name or None,
        name_set=name_set or None,
        columns_data=columns_data,
    )

    if _is_debug_log_enabled():
        mapping: list[dict[str, Any]] = []
        for raw in parsed_select or []:
            lower = raw.lower()
            if lower in (name_set or set()):
                mapped = raw
                source = "internal"
            elif lower in (display_to_name or {}):
                mapped = (display_to_name or {})[lower]
                source = "display"
            else:
                mapped = raw
                source = "unknown"
            mapping.append({"raw": raw, "mapped": mapped, "source": source})
        _log_debug(
            location="operations.py:list_items",
            message="select_fields_mapping",
            data={
                "select_fields_raw": select_fields,
                "parsed_select": parsed_select,
                "mapped_select": mapped_select,
                "mapping": mapping,
                "columns_count": (
                    len(columns_data.get("value", []))
                    if isinstance(columns_data, dict)
                    else None
                ),
            },
            extra={"hypothesisId": "H1"},
        )

    clauses: list[str] = []

    uses_fields_clause = False

    # multiple filters
    if filters_raw:
        parsed_filters = filters.parse_filters(filters_raw)
        _validate_requested_fields(
            requested_fields=[c.field for c in parsed_filters],
            display_to_name=display_to_name,
            name_set=name_set,
            allow_special={"createddatetime"},
        )
        for cond in parsed_filters:
            mapped = _map_field_name(cond.field, display_to_name, name_set)
            field_ref = mapped
            if mapped != "createdDateTime":
                field_ref = f"fields/{mapped}"
                uses_fields_clause = True
            fragment = filters.build_filter_fragment(cond, field_ref)
            clauses.append(fragment)

    filter_expr = " and ".join(clauses) if clauses else None

    top = max(1, min(page_size, 100))

    prefer_added = False
    req = request_builders.build_list_items_request(
        site_id=site_id,
        list_id=list_id,
        top=top,
        skiptoken=page_token,
        filter_expr=filter_expr,
        select_fields=mapped_select,
        orderby="createdDateTime desc",
    )
    # SharePoint lists may reject filtering on non-indexed fields
    # unless Prefer header is provided.
    # Provide Prefer header as a best-effort mitigation.
    extra_headers = None
    if filter_expr and (uses_fields_clause or "fields/" in filter_expr):
        extra_headers = {"Prefer": "HonorNonIndexedQueriesWarning=true"}
        prefer_added = True

    if _is_debug_log_enabled():
        _log_debug(
            location="operations.py:list_items",
            message="request_args",
            data={
                "filters_raw": filters_raw,
                "filter_expr": filter_expr,
                "orderby": "createdDateTime desc",
                "page_size": top,
                "page_token": page_token,
                "prefer_added": prefer_added,
            },
        )

    data = _send_request(req, access_token, extra_headers=extra_headers)

    if _is_debug_log_enabled():
        items = data.get("value", []) if isinstance(data, dict) else []
        first_item = items[0] if items and isinstance(items[0], dict) else None
        fields_obj = (
            first_item.get("fields") if isinstance(first_item, dict) else None
        )
        fields_keys = (
            sorted([k for k in fields_obj.keys() if isinstance(k, str)])
            if isinstance(fields_obj, dict)
            else []
        )
        requested = [s for s in (mapped_select or []) if isinstance(s, str)]
        requested_presence = {s: (s in set(fields_keys)) for s in requested}
        missing_requested = [
            s for s, ok in requested_presence.items() if not ok
        ]
        _log_debug(
            location="operations.py:list_items",
            message="response_fields_presence",
            data={
                "items_count": len(items),
                "first_item_has_fields": isinstance(fields_obj, dict),
                "first_item_fields_keys_count": (
                    len(fields_keys) if isinstance(fields_obj, dict) else None
                ),
                "first_item_fields_keys_sample": fields_keys[:50],
                "requested_presence": requested_presence,
                "missing_requested": missing_requested,
            },
            extra={"hypothesisId": "H2"},
        )

    # Normalize: ensure requested select fields exist in each item's fields.
    # Graph may omit field keys when values are empty, which can be confusing for
    # downstream consumers (including Agents). Add missing keys with None, and
    # try to recover from common key variants (case differences / OData__ prefix).
    if mapped_select and isinstance(data, dict):
        items = data.get("value", []) or []
        filled_none_by_field: dict[str, int] = {}
        filled_alias_by_field: dict[str, int] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            fields_obj = item.get("fields")
            if not isinstance(fields_obj, dict):
                continue
            lower_key_map = {
                k.lower(): k for k in fields_obj.keys() if isinstance(k, str)
            }
            for field_name in mapped_select:
                if not isinstance(field_name, str) or not field_name:
                    continue
                if field_name in fields_obj:
                    continue
                # 1) case-insensitive match (e.g., ID vs id)
                existing = lower_key_map.get(field_name.lower())
                if existing and existing in fields_obj:
                    fields_obj[field_name] = fields_obj.get(existing)
                    filled_alias_by_field[field_name] = (
                        filled_alias_by_field.get(field_name, 0) + 1
                    )
                    continue
                # 2) SharePoint OData__ prefix variant (e.g., OData__x30... vs _x30...)
                if field_name.startswith("_"):
                    alt = f"OData__{field_name.lstrip('_')}"
                    if alt in fields_obj:
                        fields_obj[field_name] = fields_obj.get(alt)
                        filled_alias_by_field[field_name] = (
                            filled_alias_by_field.get(field_name, 0) + 1
                        )
                        continue
                # 3) default: explicitly include missing key
                fields_obj[field_name] = None
                filled_none_by_field[field_name] = (
                    filled_none_by_field.get(field_name, 0) + 1
                )

        if _is_debug_log_enabled():
            _log_debug(
                location="operations.py:list_items",
                message="normalized_missing_fields",
                data={
                    "items_count": (
                        len(items) if isinstance(items, list) else None
                    ),
                    "requested_fields": mapped_select,
                    "filled_none_by_field": filled_none_by_field,
                    "filled_alias_by_field": filled_alias_by_field,
                },
            )

        if _is_debug_log_enabled():
            # Check presence again after normalization (sample first item only).
            first_item = (
                items[0] if items and isinstance(items[0], dict) else None
            )
            fields_obj = (
                first_item.get("fields")
                if isinstance(first_item, dict)
                else None
            )
            fields_keys = (
                sorted([k for k in fields_obj.keys() if isinstance(k, str)])
                if isinstance(fields_obj, dict)
                else []
            )
            requested = [
                s for s in (mapped_select or []) if isinstance(s, str)
            ]
            requested_presence = {
                s: (s in set(fields_keys)) for s in requested
            }
            missing_requested = [
                s for s, ok in requested_presence.items() if not ok
            ]
            _log_debug(
                location="operations.py:list_items",
                message="response_fields_presence_normalized",
                data={
                    "first_item_has_fields": isinstance(fields_obj, dict),
                    "first_item_fields_keys_count": (
                        len(fields_keys)
                        if isinstance(fields_obj, dict)
                        else None
                    ),
                    "first_item_fields_keys_sample": fields_keys[:50],
                    "requested_presence": requested_presence,
                    "missing_requested": missing_requested,
                },
            )

    next_token = None
    next_link = data.get("@odata.nextLink") if isinstance(data, dict) else None
    if isinstance(next_link, str):
        parsed = urllib.parse.urlparse(next_link)
        qs = urllib.parse.parse_qs(parsed.query)
        tokens = qs.get("$skiptoken") or qs.get("%24skiptoken")
        if tokens:
            next_token = tokens[0]

    if _is_debug_log_enabled():
        items = data.get("value", []) if isinstance(data, dict) else []
        _log_debug(
            location="operations.py:list_items",
            message="return_summary",
            data={
                "returned_items_count": len(items),
                "next_page_token_present": bool(next_token),
            },
            extra={"hypothesisId": "H3"},
        )

    items = data.get("value", []) if isinstance(data, dict) else []
    return {
        "items": items,
        "next_page_token": next_token,
    }
