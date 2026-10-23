from __future__ import annotations


def format_runtime_error(message: str, *, category: str) -> str:
    return f"[{category}] {message}"
