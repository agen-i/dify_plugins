from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File

from vision_core.fetch import download
from vision_core.origin import native_origin_from_session
from vision_core.images import ImageFailure, Limits, box_from_parameters, view


class ReadRegionTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        try:
            if set(tool_parameters) - {
                "source_image",
                "x_min",
                "y_min",
                "x_max",
                "y_max",
            }:
                raise ImageFailure("INVALID_ARGUMENTS")
            source = tool_parameters.get("source_image")
            if not isinstance(source, File) or source.mime_type not in (
                "image/png",
                "image/jpeg",
            ):
                raise ImageFailure("INVALID_NATIVE_FILE")
            limits = Limits()
            if (
                source.size is not None
                and not 0 < source.size <= limits.input_bytes
            ):
                raise ImageFailure("INPUT_LIMIT_EXCEEDED")
            box = box_from_parameters(tool_parameters)
            origin = native_origin_from_session(self.session)
            output, metadata = view(
                download(source.url, origin, limits), box, limits
            )
            yield self.create_json_message(metadata)
            yield self.create_blob_message(
                output, {"mime_type": "image/png", "filename": "region.png"}
            )
        except ImageFailure as exc:
            if str(exc) == "OUTPUT_LIMIT_EXCEEDED":
                raise ValueError(
                    "OUTPUT_LIMIT_EXCEEDED: choose a narrower original-image crop"
                ) from None
            raise ValueError(str(exc)) from None
        except Exception:
            raise ValueError("IMAGE_VIEW_FAILED") from None
