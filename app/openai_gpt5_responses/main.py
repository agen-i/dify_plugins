import os

from dify_plugin import DifyPluginEnv, Plugin

_TIMEOUT_MIN_SECONDS = 60
_TIMEOUT_MAX_SECONDS = 3600
_DEFAULT_MAX_REQUEST_TIMEOUT = 1200
_DEFAULT_MAX_INVOCATION_TIMEOUT = 1200


def _read_timeout(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        timeout_value = int(raw_value)
    except (TypeError, ValueError):
        return default

    return max(_TIMEOUT_MIN_SECONDS, min(_TIMEOUT_MAX_SECONDS, timeout_value))


plugin = Plugin(
    DifyPluginEnv(
        MAX_REQUEST_TIMEOUT=_read_timeout(
            "MAX_REQUEST_TIMEOUT", _DEFAULT_MAX_REQUEST_TIMEOUT
        ),
        MAX_INVOCATION_TIMEOUT=_read_timeout(
            "MAX_INVOCATION_TIMEOUT", _DEFAULT_MAX_INVOCATION_TIMEOUT
        ),
    )
)

if __name__ == "__main__":
    plugin.run()
