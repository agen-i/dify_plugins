"""Read only native Dify upload previews signed by the owning host platform."""

from __future__ import annotations

import base64
import http.client
import re
import ssl
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit

from vision_core.images import ImageFailure, Limits


@dataclass(frozen=True)
class Origin:
    scheme: str
    host: str
    port: int


def native_origin(value: str | None) -> Origin:
    try:
        p = urlsplit(value or "")
        if (
            p.scheme not in ("http", "https")
            or not p.hostname
            or p.username
            or p.password
            or p.query
            or p.fragment
            or p.path not in ("", "/")
        ):
            raise ValueError("native origin")
        return Origin(
            p.scheme,
            p.hostname.lower(),
            p.port or (443 if p.scheme == "https" else 80),
        )
    except Exception:
        raise ImageFailure("UNSUPPORTED_NATIVE_FILE_CONTEXT") from None


def preview_path(url: str, origin: Origin) -> str:
    try:
        if (
            not isinstance(url, str)
            or len(url) > 2048
            or any(ord(c) <= 32 or ord(c) == 127 for c in url)
        ):
            raise ValueError("URL")
        p = urlsplit(url)
        if (
            p.scheme != origin.scheme
            or p.hostname != origin.host
            or (p.port or (443 if p.scheme == "https" else 80)) != origin.port
            or p.username
            or p.password
            or p.fragment
        ):
            raise ValueError("origin")
        if not re.fullmatch(
            r"/files/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/file-preview",
            p.path,
        ):
            raise ValueError("path")
        pairs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
        values = dict(pairs)
        if len(pairs) != 3 or set(values) != {"timestamp", "nonce", "sign"}:
            raise ValueError("query")
        if (
            not re.fullmatch(r"[0-9]{10,13}", values["timestamp"])
            or not re.fullmatch(r"[0-9a-f]{32}", values["nonce"])
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}=", values["sign"])
        ):
            raise ValueError("signature fields")
        if (
            len(
                base64.b64decode(values["sign"], altchars=b"-_", validate=True)
            )
            != 32
        ):
            raise ValueError("signature size")
        return p.path + "?" + urlencode(values)
    except Exception:
        raise ImageFailure("INVALID_NATIVE_FILE") from None


def download(url: str, origin: Origin, limits: Limits = Limits()) -> bytes:
    path = preview_path(url, origin)
    deadline = time.monotonic() + 20
    connection = (
        http.client.HTTPSConnection(
            origin.host,
            origin.port,
            timeout=5,
            context=ssl.create_default_context(),
        )
        if origin.scheme == "https"
        else http.client.HTTPConnection(origin.host, origin.port, timeout=5)
    )
    try:
        # http.client neither follows redirects nor consults environment proxies.
        connection.request(
            "GET", path, headers={"Accept-Encoding": "identity"}
        )
        socket = connection.sock
        response = connection.getresponse()
        if response.status != 200:
            raise ImageFailure("FILE_NOT_AVAILABLE")
        length = response.getheader("Content-Length")
        if length is not None and (
            not length.isdecimal() or int(length) > limits.input_bytes
        ):
            raise ImageFailure("INPUT_LIMIT_EXCEEDED")
        output = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ImageFailure("FILE_DOWNLOAD_TIMEOUT")
            if socket is not None:
                socket.settimeout(min(5, remaining))
            chunk = response.read1(
                min(65536, limits.input_bytes + 1 - len(output))
            )
            output.extend(chunk)
            if len(output) > limits.input_bytes:
                raise ImageFailure("INPUT_LIMIT_EXCEEDED")
            if not chunk:
                return bytes(output)
    except ImageFailure:
        raise
    except TimeoutError:
        raise ImageFailure("FILE_DOWNLOAD_TIMEOUT") from None
    except Exception:
        raise ImageFailure("FILE_DOWNLOAD_FAILED") from None
    finally:
        connection.close()
