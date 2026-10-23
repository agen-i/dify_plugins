"""Administrator budgets; PDFs/tool parameters cannot override them."""

import ipaddress
import json
import math
import os
from dataclasses import dataclass, fields
from urllib.parse import unquote, urlsplit

from pdf_core.model import ConversionError


@dataclass(frozen=True)
class Limits:
    max_files: int = 5
    input_file_bytes: int = 10 * 1024 * 1024
    input_total_bytes: int = 25 * 1024 * 1024
    pages_per_file: int = 20
    pages_total: int = 30
    default_dpi: int = 150
    max_dpi: int = 200
    max_width: int = 5000
    max_height: int = 5000
    max_pixels: int = 16_000_000
    output_file_bytes: int = 8 * 1024 * 1024
    output_total_bytes: int = 40 * 1024 * 1024
    text_chars: int = 1_000_000
    fetch_seconds: int = 20
    process_seconds: int = 60
    request_seconds: int = 100
    memory_bytes: int = 1024 * 1024 * 1024
    concurrency: int = 1

    def __post_init__(self) -> None:
        if any(
            type(getattr(self, f.name)) is not int
            or getattr(self, f.name) <= 0
            for f in fields(self)
        ):
            raise ConversionError("CONFIG: limits must be positive integers")
        if self.default_dpi > self.max_dpi or self.concurrency > 8:
            raise ConversionError("CONFIG: invalid DPI/concurrency")

    @classmethod
    def from_env(cls) -> "Limits":
        try:
            raw = json.loads(os.environ.get("PDF_TEXT_PAGES_LIMITS", "{}"))
            return cls(**raw)
        except Exception:
            raise ConversionError(
                "CONFIG: invalid administrator limits"
            ) from None

    def dpi(self, value: object) -> float:
        if value is None:
            return float(self.default_dpi)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConversionError("INPUT: dpi must be a number")
        result = float(value)
        if not math.isfinite(result) or not 36 <= result <= self.max_dpi:
            raise ConversionError("LIMIT: dpi out of range")
        return result


@dataclass(frozen=True)
class AllowedSource:
    scheme: str
    host: str
    port: int
    path_prefix: str
    address: str | None = None
    download_routes: bool = False
    _target: "AllowedSource | None" = None


def parse_runtime_base(base: str, name: str) -> AllowedSource:
    try:
        if any(ord(c) < 33 or ord(c) == 127 for c in base) or "\\" in base:
            raise ValueError
        u = urlsplit(base)
        if (
            u.scheme not in ("http", "https")
            or not u.hostname
            or u.username is not None
            or u.password is not None
            or u.query
            or u.fragment
        ):
            raise ValueError
        host = u.hostname
        if any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789.-:" for c in host
        ):
            raise ValueError
        port = (
            u.port
            if u.port is not None
            else (443 if u.scheme == "https" else 80)
        )
        if not 1 <= port <= 65535:
            raise ValueError
        path = u.path
        if (
            unquote(path) != path
            or "//" in path
            or any(part in (".", "..") for part in path.split("/"))
        ):
            raise ValueError
        # Preserve raw base+file route; never normalize an incoming path/query.
        return AllowedSource(
            u.scheme, host, port, path + "/files/", download_routes=True
        )
    except Exception:
        raise ConversionError(
            f"CONFIG: {name}が不適合です。管理者はDifyの既存設定と"
            "プラグインへの継承を確認してください。"
        ) from None


def load_runtime_sources() -> tuple[AllowedSource, ...]:
    """Approved file origin first, then optional independent internal API target."""

    def setting(primary: str, alias: str) -> str:
        return (
            os.environ[primary]
            if primary in os.environ
            else os.environ.get(alias, "")
        )

    internal = setting("INTERNAL_FILES_URL", "SERVER_CONSOLE_API_URL")
    if internal:
        # An existing internal file URL preserves direct acquisition; unrelated
        # API settings must not introduce validation/mandatory input here.
        return (
            parse_runtime_base(
                internal, "INTERNAL_FILES_URL / SERVER_CONSOLE_API_URL"
            ),
        )
    external = setting("FILES_URL", "CONSOLE_API_URL")
    if not external:
        raise ConversionError(
            "CONFIG: FILES_URL / INTERNAL_FILES_URL"
            "（既存の別名設定を含む）が未設定です。"
            "管理者はDifyの既存配信設定とプラグインへの継承を確認してください。"
        )
    source = parse_runtime_base(external, "FILES_URL / CONSOLE_API_URL")
    api = os.environ.get("DIFY_INNER_API_URL")
    if not api:
        raise ConversionError(
            "CONFIG: DIFY_INNER_API_URLが未設定です。管理者は既存の内部API設定と"
            "プラグインへの継承を確認してください。"
        )
    # PLUGIN_DIFY_INNER_API_URL is compose interpolation, not a plugin alias.
    target = parse_runtime_base(api, "DIFY_INNER_API_URL")
    if (source.scheme, source.host, source.port) == (
        target.scheme,
        target.host,
        target.port,
    ):
        return (
            source,
        )  # Same-origin direct behavior, including existing prefix.
    # Cross-origin mapping is supported only for the verified API root /files
    # routes. Non-root prefixes are not silently stripped/rebased/appended.
    if urlsplit(external).path != "" or urlsplit(api).path not in ("", "/"):
        raise ConversionError(
            "CONFIG: FILES_URLとDIFY_INNER_API_URLのpath対応を確認できません。"
            "管理者は既存の配信設定と内部APIの対応を確認してください。"
        )
    return (
        AllowedSource(
            source.scheme,
            source.host,
            source.port,
            source.path_prefix,
            download_routes=True,
            _target=target,
        ),
    )


def load_sources(raw: object) -> tuple[AllowedSource, ...]:
    """Require explicit pinned IP and directory path boundary, fail closed."""
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(items, list) or not 1 <= len(items) <= 16:
            raise ValueError
        result = []
        for item in items:
            if "_target" in item:
                raise ValueError
            source = AllowedSource(**item)
            if source.scheme not in ("http", "https"):
                raise ValueError
            if not source.host or source.host != source.host.lower():
                raise ValueError
            if any(
                c not in "abcdefghijklmnopqrstuvwxyz0123456789.-:"
                for c in source.host
            ):
                raise ValueError
            if type(source.port) is not int or not 1 <= source.port <= 65535:
                raise ValueError
            prefix = source.path_prefix
            if (
                not prefix.startswith("/")
                or not prefix.endswith("/")
                or ".." in prefix
                or unquote(prefix) != prefix
                or any(c in prefix for c in "\\?#\r\n")
            ):
                raise ValueError
            ipaddress.ip_address(source.address)
            result.append(source)
        return tuple(result)
    except Exception:
        raise ConversionError(
            "CONFIG: explicit valid file-source allowlist required"
        ) from None
