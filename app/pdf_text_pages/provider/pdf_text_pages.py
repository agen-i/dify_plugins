from typing import Any

from dify_plugin import ToolProvider


class PdfTextPagesProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        # No provider authentication. Trusted deployment configuration is checked
        # by invoke, before any file acquisition, with a sanitized node error.
        return None
