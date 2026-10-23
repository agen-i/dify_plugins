"""Private child entrypoint. PDFium is imported and invoked only here, sequentially."""

import ctypes
import io
import json
import math
import os
import resource
import signal
import sys
import time
from contextlib import closing
from pathlib import Path

from pdf_core.config import Limits
from pdf_core.model import ConversionError


def run(request_path: Path) -> None:
    request = json.loads(request_path.read_text())
    root = request_path.parent
    limits = Limits(**request["limits"])
    resource.setrlimit(
        resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes)
    )
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (limits.process_seconds + 1, limits.process_seconds + 2),
    )
    # RLIMIT_FSIZE covers every child file, including JSON with extracted text.
    # A JSON codepoint can use up to 12 bytes (escaped UTF-16 surrogate pair).
    # Request metadata already bounds copied filenames; per-page overhead is small.
    json_file_bytes = (
        limits.text_chars * 12
        + request_path.stat().st_size
        + limits.pages_total * 1024
        + 65536
    )
    file_bytes = max(limits.output_file_bytes, json_file_bytes)
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
    # Kill owned native work if parent dies; this is not a network/filesystem sandbox.
    expected_parent = request["parent_pid"]
    ctypes.CDLL(None).prctl(1, signal.SIGKILL)
    if os.getppid() != expected_parent:
        return
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw, ImageFont

    total_pages = total_bytes = total_text = 0
    docs: list[dict] = []
    current = "INPUT"
    end = time.monotonic() + limits.process_seconds
    try:
        for d_index, item in enumerate(request["documents"], 1):
            position = f"{item['source_parameter']}[{item['source_index']}]"
            current = position
            (root / "progress.json").write_text(
                json.dumps({"position": current})
            )
            try:
                pdf = pdfium.PdfDocument(str(root / item["input_path"]))
            except Exception:
                raise ConversionError(
                    "PDF_OPEN: corrupt or password-protected PDF"
                ) from None
            with pdf:
                count = len(pdf)
                if (
                    not count
                    or count > limits.pages_per_file
                    or total_pages + count > limits.pages_total
                ):
                    raise ConversionError("LIMIT: PDF page count")
                doc_id = f"{request['batch_id']}-D{d_index:03d}"
                pages: list[dict] = []
                for p_index in range(count):
                    current = f"{position} page {p_index + 1}"
                    (root / "progress.json").write_text(
                        json.dumps({"position": current})
                    )
                    if time.monotonic() >= end:
                        raise ConversionError("PROCESS_TIMEOUT: PDF deadline")
                    page_id = f"{doc_id}-P{p_index + 1:04d}"
                    with closing(pdf[p_index]) as page:
                        width_pt, height_pt = page.get_size()
                        scale = request["dpi"] / 72
                        width, height = (
                            math.ceil(width_pt * scale),
                            math.ceil(height_pt * scale),
                        )
                        font = ImageFont.load_default(size=32)
                        bbox = font.getbbox(page_id)
                        label_width = bbox[2] - bbox[0] + 40
                        out_width, out_height = (
                            max(width, label_width),
                            height + 80,
                        )
                        if (
                            not all(
                                math.isfinite(n) and n > 0
                                for n in (width_pt, height_pt)
                            )
                            or out_width > limits.max_width
                            or out_height > limits.max_height
                            or out_width * out_height > limits.max_pixels
                        ):
                            raise ConversionError(
                                "LIMIT: image dimensions/pixels before render"
                            )
                        try:
                            with closing(page.get_textpage()) as textpage:
                                # Full text; no summary or stripping.
                                chars = textpage.count_chars()
                                if chars > limits.text_chars - total_text:
                                    raise ConversionError(
                                        "LIMIT: extracted text characters"
                                    )
                                text = textpage.get_text_range().replace(
                                    "\r\n", "\n"
                                )
                        except ConversionError:
                            raise
                        except Exception:
                            raise ConversionError(
                                "PDF_TEXT: extraction failed"
                            ) from None
                        total_text += len(text)
                        if total_text > limits.text_chars:
                            raise ConversionError(
                                "LIMIT: extracted text characters"
                            )
                        try:
                            bitmap = page.render(scale=scale)
                            try:
                                image = bitmap.to_pil()
                                if image.size != (width, height):
                                    # Validate actual raster dimensions.
                                    width, height = image.size
                                    out_width, out_height = (
                                        max(width, label_width),
                                        height + 80,
                                    )
                                    if (
                                        out_width > limits.max_width
                                        or out_height > limits.max_height
                                        or out_width * out_height
                                        > limits.max_pixels
                                    ):
                                        raise ConversionError(
                                            "LIMIT: rendered image dimensions"
                                        )
                                canvas = Image.new(
                                    "RGB", (out_width, out_height), "white"
                                )
                                canvas.paste(image, (0, 80))
                                ImageDraw.Draw(canvas).text(
                                    (20, 18), page_id, font=font, fill="black"
                                )

                                # Cap the compressed output buffer during encoding.
                                class BoundedPNG(io.BytesIO):
                                    def write(self, data: bytes) -> int:
                                        if (
                                            self.tell() + len(data)
                                            > limits.output_file_bytes
                                        ):
                                            raise ConversionError(
                                                "LIMIT: PNG bytes"
                                            )
                                        return super().write(data)

                                with BoundedPNG() as buf:
                                    canvas.save(buf, format="PNG")
                                    blob = buf.getvalue()
                                canvas.close()
                                image.close()
                            finally:
                                bitmap.close()
                        except ConversionError:
                            raise
                        except Exception:
                            raise ConversionError(
                                "PDF_RENDER: image generation failed"
                            ) from None
                    total_bytes += len(blob)
                    if total_bytes > limits.output_total_bytes:
                        raise ConversionError("LIMIT: total PNG bytes")
                    image_path = f"output-{total_pages:04d}.png"
                    (root / image_path).write_bytes(blob)
                    pages.append(
                        {
                            "page_id": page_id,
                            "page_number": p_index + 1,
                            "text": text,
                            "image_index": total_pages,
                            "image_filename": page_id + ".png",
                            "image_path": image_path,
                        }
                    )
                    total_pages += 1
                docs.append(
                    {
                        "document_id": doc_id,
                        "filename": item["filename"],
                        "source_parameter": item["source_parameter"],
                        "source_index": item["source_index"],
                        "pages": pages,
                    }
                )
        result = {"batch_id": request["batch_id"], "documents": docs}
    except ConversionError as exc:
        result = {"error": f"{current}: {exc}"}
    except Exception:
        result = {"error": f"{current}: PDF_FAILURE: processing failed"}
    (root / "result.json").write_text(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
