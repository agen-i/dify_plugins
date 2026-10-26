import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File
from pdf_core.config import Limits
from pdf_core.fetch import fetch
from pdf_core.formatting import format_text
from pdf_core.model import BatchRecord, ConversionError, InputPDF
from pdf_core.runner import convert, execution_slot
from pdf_core.runtime_source import discover_runtime_sources


def normalize(
    parameters: dict[str, Any], limits: Limits
) -> list[tuple[str, int, File]]:
    items: list[tuple[str, int, File]] = []
    files = parameters.get("pdf_files")
    if isinstance(files, File):
        files = [files]
    if files is not None:
        if not isinstance(files, list):
            raise ConversionError("pdf_files: INPUT: expected File list")
        if len(files) + len(items) > limits.max_files:
            raise ConversionError("LIMIT: input file count")
        items.extend(
            ("pdf_files", index, file) for index, file in enumerate(files)
        )
    if len(items) > limits.max_files:
        raise ConversionError("LIMIT: input file count")
    declared_total = 0
    for parameter, index, file in items:
        position = f"{parameter}[{index}]"
        if not isinstance(file, File):
            raise ConversionError(
                f"{position}: INPUT: expected Dify File (URL/path strings prohibited)"
            )
        if len(file.filename or "") > 4096:
            raise ConversionError(f"{position}: LIMIT: filename characters")
        if file.size is not None:
            if file.size < 0 or file.size > limits.input_file_bytes:
                raise ConversionError(
                    f"{position}: LIMIT: declared input bytes"
                )
            declared_total += file.size
    if declared_total > limits.input_total_bytes:
        raise ConversionError("LIMIT: declared total input bytes")
    return items


class PdfTextPagesTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        files = tool_parameters.get("pdf_files")
        if files is None:
            raise ConversionError(
                "pdf_files: INPUT: ファイルリストにPDF/画像を受け取る変数を設定してください"
            )
        if isinstance(files, list) and not files:
            # No input files means no source/config/DPI/slot/native work is necessary.
            # No BLOB messages preserves Dify's standard files=[] output.
            batch = BatchRecord("B" + uuid4().hex.upper(), [])
            yield self.create_text_message("")
            yield self.create_json_message(batch.metadata())
            return
        limits = Limits()
        dpi = limits.dpi(tool_parameters.get("dpi"))
        items = normalize(tool_parameters, limits)
        deadline = time.monotonic() + limits.request_seconds
        sources = discover_runtime_sources(self.session, limits, deadline)
        with execution_slot(limits):
            inputs: list[InputPDF] = []
            passthrough: dict[int, bytes] = {}
            total = 0
            for parameter, index, file in items:
                try:
                    data = fetch(
                        file.url,
                        sources,
                        limits,
                        limits.input_total_bytes - total,
                        deadline,
                    )
                    extension = (
                        file.extension or Path(file.filename or "").suffix
                    )
                    is_pdf = extension.lower() in ("pdf", ".pdf")
                    if not extension:
                        is_pdf = (file.mime_type or "").split(";", 1)[
                            0
                        ].strip().lower() == "application/pdf" or data.startswith(
                            b"%PDF-"
                        )
                    if is_pdf and not data.startswith(b"%PDF-"):
                        raise ConversionError(
                            "PDF_OPEN: invalid PDF signature"
                        )
                    if not is_pdf and len(data) > limits.output_file_bytes:
                        raise ConversionError(
                            "LIMIT: passthrough output bytes"
                        )
                except ConversionError as exc:
                    raise ConversionError(
                        f"{parameter}[{index}]: {exc}"
                    ) from None
                total += len(data)
                if is_pdf:
                    inputs.append(
                        InputPDF(
                            file.filename or "(unnamed PDF)",
                            parameter,
                            index,
                            data,
                        )
                    )
                else:
                    passthrough[index] = data
            batch = (
                convert(inputs, dpi, limits, deadline)
                if inputs
                else BatchRecord("B" + uuid4().hex.upper(), [])
            )
            text = format_text(batch, limits.text_chars) if inputs else ""
            if (
                sum(map(len, passthrough.values()))
                + sum(len(page.png) for page in batch.pages)
                > limits.output_total_bytes
            ):
                raise ConversionError("LIMIT: total output bytes")
            metadata = batch.metadata()
            documents = {
                doc.source_index: (doc, meta)
                for doc, meta in zip(
                    batch.documents, metadata["documents"], strict=True
                )
            }
            # All acquisition/conversion/budget checks precede the first yield.
            messages = [self.create_text_message(text)]
            for _, index, file in items:
                if index in passthrough:
                    messages.append(
                        self.create_blob_message(
                            passthrough[index],
                            {
                                "mime_type": (
                                    file.mime_type
                                    if file.mime_type is not None
                                    else "application/octet-stream"
                                ),
                                "filename": (
                                    file.filename
                                    if file.filename is not None
                                    else "file"
                                ),
                            },
                        )
                    )
                else:
                    doc, meta = documents[index]
                    for page, page_meta in zip(
                        doc.pages, meta["pages"], strict=True
                    ):
                        # Core PDF-only records remain contiguous; JSON describes
                        # the mixed files output position without changing them.
                        page_meta["image_index"] = len(messages) - 1
                        messages.append(
                            self.create_blob_message(
                                page.png,
                                {
                                    "mime_type": "image/png",
                                    "filename": page.image_filename,
                                },
                            )
                        )
            messages.append(self.create_json_message(metadata))
            if time.monotonic() >= deadline:
                raise ConversionError(
                    "PROCESS_TIMEOUT: request deadline before output"
                )
            for message in messages:
                if time.monotonic() >= deadline:
                    raise ConversionError("PROCESS_TIMEOUT: output deadline")
                yield message
