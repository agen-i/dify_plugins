from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "app.sharepoint_list.debug"
_LOGGER: logging.Logger | None = None
_PLUGIN_LOGGER_HANDLER: logging.Handler | None | object = ...


def _get_plugin_logger_handler() -> logging.Handler | None:
    global _PLUGIN_LOGGER_HANDLER
    if _PLUGIN_LOGGER_HANDLER is not ...:
        return _PLUGIN_LOGGER_HANDLER

    try:
        from dify_plugin.config.logger_format import plugin_logger_handler
    except Exception:  # pragma: no cover - local/unit-test fallback
        _PLUGIN_LOGGER_HANDLER = None
    else:
        _PLUGIN_LOGGER_HANDLER = plugin_logger_handler

    return _PLUGIN_LOGGER_HANDLER


def get_debug_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    plugin_logger_handler = _get_plugin_logger_handler()
    if plugin_logger_handler is not None:
        if plugin_logger_handler not in logger.handlers:
            logger.addHandler(plugin_logger_handler)
    elif not logger.handlers:
        logger.addHandler(logging.NullHandler())

    _LOGGER = logger
    return logger


def emit_debug_payload(payload: dict[str, Any]) -> None:
    get_debug_logger().info(json.dumps(payload, ensure_ascii=False))
