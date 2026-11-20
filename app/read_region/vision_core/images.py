"""Decode once, keep source pixels, and encode full image or an original ROI."""

from __future__ import annotations

import io
import math
import warnings
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any

from PIL import Image, ImageOps


class ImageFailure(Exception):
    """Safe fixed diagnostic, with no filename, URL or source content."""


@dataclass(frozen=True)
class Limits:
    input_bytes: int = 15 * 1024 * 1024
    source_pixels: int = 20_000_000
    source_side: int = 12_000
    output_bytes: int = 10 * 1024 * 1024


class BoundedBuffer(io.BytesIO):
    def __init__(self, maximum: int) -> None:
        super().__init__()
        self.maximum = maximum

    def write(self, data: bytes) -> int:
        if self.tell() + len(data) > self.maximum:
            raise ImageFailure("OUTPUT_LIMIT_EXCEEDED")
        return super().write(data)


def box_from_parameters(parameters: dict[str, Any]) -> list[float]:
    keys = ("x_min", "y_min", "x_max", "y_max")
    values = [
        parameters.get(key, default)
        for key, default in zip(keys, (0, 0, 1, 1), strict=True)
    ]
    if any(
        type(v) not in (int, float) or not 0 <= v <= 1 or not math.isfinite(v)
        for v in values
    ):
        raise ImageFailure("INVALID_BOX")
    if values[0] >= values[2] or values[1] >= values[3]:
        raise ImageFailure("INVALID_BOX")
    return [float(value) for value in values]


def view(
    data: bytes, box: list[float], limits: Limits = Limits()
) -> tuple[bytes, dict[str, Any]]:
    if not data or len(data) > limits.input_bytes:
        raise ImageFailure("INPUT_LIMIT_EXCEEDED")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if (
                    source.format not in ("PNG", "JPEG")
                    or getattr(source, "n_frames", 1) != 1
                ):
                    raise ImageFailure("UNSUPPORTED_IMAGE")
                if (
                    max(source.size) > limits.source_side
                    or source.width * source.height > limits.source_pixels
                ):
                    raise ImageFailure("INPUT_LIMIT_EXCEEDED")
                source_16bit_gray = source.format == "PNG" and data[24] == 16
                if source_16bit_gray and data[25] != 0:
                    raise ImageFailure("UNSUPPORTED_BIT_DEPTH")
                source.verify()
            with Image.open(io.BytesIO(data)) as source:
                oriented = ImageOps.exif_transpose(source)
                if source_16bit_gray:
                    # PNG color-type0 keeps its native 16-bit grayscale samples.
                    normalized = oriented
                else:
                    normalized = oriented.convert(
                        "RGBA"
                        if "A" in oriented.getbands()
                        or "transparency" in oriented.info
                        else "RGB"
                    )
                width, height = normalized.size
                pixels = [
                    int(
                        (
                            Decimal(str(value))
                            * (width if i % 2 == 0 else height)
                        ).to_integral_value(
                            rounding=ROUND_FLOOR if i < 2 else ROUND_CEILING
                        )
                    )
                    for i, value in enumerate(box)
                ]
                region = normalized.crop(tuple(pixels))
                save_options: dict[str, Any] = {}
                if source_16bit_gray and "transparency" in oriented.info:
                    transparency = oriented.info["transparency"]
                    if (
                        type(transparency) is not int
                        or not 0 <= transparency <= 65535
                    ):
                        raise ImageFailure("UNSUPPORTED_TRANSPARENCY")
                    save_options["transparency"] = transparency
                region.info.clear()
                out = BoundedBuffer(limits.output_bytes)
                region.save(out, format="PNG", **save_options)
                metadata = {
                    "coordinate_space": "normalized_original_after_exif",
                    "source_size": {"width": width, "height": height},
                    "requested_box": box,
                    "crop_pixels": pixels,
                    "output_size": {
                        "width": region.width,
                        "height": region.height,
                    },
                    "resized": False,
                    "operation": "original_pixels_only",
                }
                return out.getvalue(), metadata
    except ImageFailure:
        raise
    except Exception:
        raise ImageFailure("INVALID_IMAGE") from None
