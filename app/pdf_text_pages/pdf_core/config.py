"""Fixed processing budgets and independently approved runtime file origins."""

import math
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
