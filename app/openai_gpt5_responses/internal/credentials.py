from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

_DEFAULT_ALLOWED_BASE_URL_HOSTS = ("api.openai.com",)
_ALLOWED_BASE_URL_HOSTS_ENV = "OPENAI_GPT5_ALLOWED_BASE_URL_HOSTS"


def _allowed_base_url_hosts() -> set[str]:
    allowed = {host for host in _DEFAULT_ALLOWED_BASE_URL_HOSTS}
    raw_env = str(os.getenv(_ALLOWED_BASE_URL_HOSTS_ENV, "") or "").strip()
    if not raw_env:
        return allowed

    for item in raw_env.split(","):
        host = item.strip().lower().strip(".")
        if host:
            allowed.add(host)
    return allowed


def _validate_host_is_public(host: str) -> None:
    normalized_host = host.lower().strip(".")
    if not normalized_host:
        raise ValueError("openai_api_base host is required")

    if normalized_host in {"localhost", "metadata.google.internal"}:
        raise ValueError("openai_api_base host is not allowed")

    if normalized_host.endswith(".localhost"):
        raise ValueError("openai_api_base host is not allowed")

    try:
        ip = ipaddress.ip_address(normalized_host)
    except ValueError:
        return

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        raise ValueError("openai_api_base host is not allowed")


def normalize_api_base(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    if scheme != "https":
        raise ValueError("openai_api_base must use https")

    if parsed.username or parsed.password:
        raise ValueError("openai_api_base must not include credentials")

    host = (parsed.hostname or "").lower().strip(".")
    _validate_host_is_public(host)

    allowed_hosts = _allowed_base_url_hosts()
    if host not in allowed_hosts:
        raise ValueError("openai_api_base host is not allowed")

    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        normalized_path = "/v1"
    elif path == "/v1":
        normalized_path = "/v1"
    else:
        raise ValueError("openai_api_base path must be /v1")

    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    return f"https://{netloc}{normalized_path}"
