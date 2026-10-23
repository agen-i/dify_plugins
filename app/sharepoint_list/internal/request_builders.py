from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import validators

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class RequestSpec:
    method: str
    url: str
    params: dict[str, Any] = field(default_factory=dict)
    json: dict[str, Any] | None = None


def build_site_get_by_path_request(site_url: str) -> RequestSpec:
    """
    Build Graph API request for resolving site by path.
    Endpoint: GET /sites/{hostname}:/{site-path}
    """
    if not site_url:
        raise ValueError("site_url is required")
    hostname, site_path = validators.parse_site_url(site_url)
    url = f"{GRAPH_BASE}/sites/{hostname}:/{site_path}"
    return RequestSpec(method="GET", url=url, params={})


def build_list_filter_request(site_id: str, list_name: str) -> RequestSpec:
    """
    Build request to find list by displayName within a site.
    Uses $filter=displayName eq 'name'.
    """
    if not site_id:
        raise ValueError("site_id is required")
    if not list_name:
        raise ValueError("list_name is required")

    url = f"{GRAPH_BASE}/sites/{site_id}/lists"
    safe_name = list_name.replace("'", "''")
    params = {"$filter": f"displayName eq '{safe_name}'"}
    return RequestSpec(method="GET", url=url, params=params)


def build_list_enumerate_request(site_id: str) -> RequestSpec:
    """
    Build request to enumerate lists in a site (fallback if filter not reliable).
    """
    if not site_id:
        raise ValueError("site_id is required")
    url = f"{GRAPH_BASE}/sites/{site_id}/lists"
    return RequestSpec(method="GET", url=url, params={})


def _ensure_fields_not_empty(fields: dict[str, Any]) -> None:
    if not fields:
        raise ValueError("fields must not be empty")


def build_create_item_request(
    site_id: str, list_id: str, fields: dict[str, Any]
) -> RequestSpec:
    """
    Build request to create a list item.
    Endpoint: POST /sites/{site-id}/lists/{list-id}/items
    Body: { \"fields\": { ... } }
    """
    if not site_id:
        raise ValueError("site_id is required")
    if not list_id:
        raise ValueError("list_id is required")
    _ensure_fields_not_empty(fields)

    url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items"
    return RequestSpec(
        method="POST", url=url, params={}, json={"fields": fields}
    )


def build_update_item_request(
    site_id: str, list_id: str, item_id: str, fields: dict[str, Any]
) -> RequestSpec:
    """
    Build request to update a list item fields.
    Endpoint: PATCH /sites/{site-id}/lists/{list-id}/items/{item-id}/fields
    """
    if not site_id:
        raise ValueError("site_id is required")
    if not list_id:
        raise ValueError("list_id is required")
    if not item_id:
        raise ValueError("item_id is required")
    _ensure_fields_not_empty(fields)

    url = (
        f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
    )
    return RequestSpec(method="PATCH", url=url, params={}, json=fields)


def build_get_item_request(
    site_id: str,
    list_id: str,
    item_id: str,
    select_fields: list[str] | None,
) -> RequestSpec:
    """
    Build request to get a list item with fields expansion.
    Endpoint: GET /sites/{site-id}/lists/{list-id}/items/{item-id}
    """
    if not site_id:
        raise ValueError("site_id is required")
    if not list_id:
        raise ValueError("list_id is required")
    if not item_id:
        raise ValueError("item_id is required")

    expand = "fields"
    if select_fields:
        select_clause = ",".join(select_fields)
        expand = f"fields($select={select_clause})"

    url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}"
    return RequestSpec(method="GET", url=url, params={"$expand": expand})


def build_list_columns_request(site_id: str, list_id: str) -> RequestSpec:
    """
    Build request to list columns (name/displayName) for a list.
    Used to map localized display names to internal names.
    """
    if not site_id:
        raise ValueError("site_id is required")
    if not list_id:
        raise ValueError("list_id is required")
    url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/columns"
    # Note: columnType is not supported in $select for columnDefinition.
    # Include only choice payload.
    params = {"$select": "name,displayName,choice"}
    return RequestSpec(method="GET", url=url, params=params)


def build_list_items_request(
    site_id: str,
    list_id: str,
    top: int = 20,
    skiptoken: str | None = None,
    filter_expr: str | None = None,
    select_fields: list[str] | None = None,
    orderby: str | None = None,
) -> RequestSpec:
    """
    Build request to list items with optional pagination, filter, orderby,
    and field selection.
    """
    if not site_id:
        raise ValueError("site_id is required")
    if not list_id:
        raise ValueError("list_id is required")
    if top <= 0:
        raise ValueError("top must be positive")

    params: dict[str, Any] = {"$top": top}
    if skiptoken:
        params["$skiptoken"] = skiptoken
    if filter_expr:
        params["$filter"] = filter_expr
    if orderby:
        params["$orderby"] = orderby

    expand = "fields"
    if select_fields:
        select_clause = ",".join(select_fields)
        expand = f"fields($select={select_clause})"
    params["$expand"] = expand

    url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items"
    return RequestSpec(method="GET", url=url, params=params)
