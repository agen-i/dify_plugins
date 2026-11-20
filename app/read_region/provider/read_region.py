from typing import Any

from dify_plugin import ToolProvider


class ReadRegionProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        if credentials:
            raise ValueError("NO_CREDENTIAL_CONFIGURATION_SUPPORTED")
