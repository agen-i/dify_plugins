from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class TargetSpec:
    site_identifier: str
    list_identifier: str


def validate_target(
    site_identifier: str | None,
    list_identifier: str | None,
) -> TargetSpec:
    """
    Validate and normalize target identifiers.
    - site_identifier: site URL or site ID (host,siteId,webId) or site name token
    - list_identifier: list ID (GUID) or list display name
    """
    if not site_identifier or not str(site_identifier).strip():
        raise ValueError("site_identifier is required.")
    if not list_identifier or not str(list_identifier).strip():
        raise ValueError("list_identifier is required.")

    return TargetSpec(
        site_identifier=str(site_identifier).strip(),
        list_identifier=str(list_identifier).strip(),
    )


def parse_list_url(list_url: str) -> tuple[str, str]:
    """
    Parse SharePoint list URL (AllItems.aspx) into (site_url, list_name_or_id).
    Expected form: https://<host>/sites/<site>/Lists/<list>/AllItems.aspx
    """
    if not list_url or not list_url.strip():
        raise ValueError("list_url is required")

    from urllib.parse import urlparse

    parsed = urlparse(list_url)
    if not parsed.scheme or not parsed.netloc or not parsed.path:
        raise ValueError("Invalid list_url")

    if "sharepoint.com" not in parsed.netloc:
        raise ValueError("list_url must point to a SharePoint host")

    path_parts = parsed.path.strip("/").split("/")
    # Expect .../sites/<site>/Lists/<list>/AllItems.aspx (list segment at index -2)
    try:
        lists_idx = path_parts.index("Lists")
        list_segment = path_parts[lists_idx + 1]
    except (ValueError, IndexError):
        raise ValueError("list_url must include /Lists/<list>/") from None

    list_name_or_id = list_segment
    # site path is everything before "Lists/<list>"
    site_path_parts = path_parts[:lists_idx]
    if not site_path_parts:
        raise ValueError("list_url must include site path before Lists/")
    site_path = "/".join(site_path_parts)
    site_url = f"{parsed.scheme}://{parsed.netloc}/{site_path}"

    return site_url, list_name_or_id


def parse_fields_json(fields_json: str | None) -> dict[str, Any]:
    """
    Parse fields JSON string into dict.
    - None/empty: returns {}
    - invalid JSON: ValueError
    - non-object JSON: ValueError
    """
    if fields_json is None or fields_json.strip() == "":
        return {}

    try:
        data = json.loads(fields_json)
    except json.JSONDecodeError as exc:
        raise ValueError("fields_json is not valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("fields_json must be a JSON object")

    return data


def ensure_item_id(operation: str, item_id: str | None) -> None:
    """
    Ensure item_id is provided for operations that require it.
    - update/read: item_id is mandatory
    - create: not required
    """
    op = operation.lower()
    if op in {"update", "read"} and not item_id:
        raise ValueError("item_id is required for this operation")


def parse_site_url(site_url: str) -> tuple[str, str]:
    """
    Parse SharePoint site URL into (hostname, site_path).
    - hostname: contoso.sharepoint.com
    - site_path: sites/demo など（先頭末尾の / は除去）
    """
    from urllib.parse import urlparse

    parsed = urlparse(site_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid site_url")

    hostname = parsed.netloc
    if "sharepoint.com" not in hostname:
        raise ValueError("site_url must be a SharePoint URL")

    path = parsed.path.strip("/")
    if not path:
        raise ValueError("site_url must include site path (e.g., /sites/demo)")

    return hostname, path


GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_guid(value: str) -> bool:
    return bool(GUID_RE.match(value or ""))
