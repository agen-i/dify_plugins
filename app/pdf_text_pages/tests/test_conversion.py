import io
import json
import time
from dataclasses import replace

import pytest
from pdf_core.config import Limits
from pdf_core.formatting import format_text
from pdf_core.model import ConversionError, InputPDF
from pdf_core.runner import convert, execution_slot, runtime_root
from PIL import Image, ImageDraw, ImageFont

from tests.fixtures import make_pdf


def item(
    data: bytes, parameter: str = "pdf_files", index: int = 0
) -> InputPDF:
    return InputPDF("same.pdf", parameter, index, data)


def test_duplicate_mixed_full_records_and_pixel_labels():
    data = make_pdf(mixed=True)
    batch = convert([item(data), item(data, "pdf_files", 0)], 150, Limits())
    assert len(batch.documents) == 2 and len(batch.pages) == 8
    assert len({p.page_id for p in batch.pages}) == 8
    assert batch.documents[0].document_id != batch.documents[1].document_id
    assert [p.image_index for p in batch.pages] == list(range(8))
    assert [p.page_number for p in batch.documents[0].pages] == [1, 2, 3, 4]
    assert (
        batch.documents[0].pages[1].text
        == batch.documents[0].pages[2].text
        == ""
    )
    assert "日本語" in batch.documents[0].pages[3].text
    text = format_text(batch, Limits().text_chars)
    assert "資料の読み方" in text and "ALPHA" in text and "42 kg" in text
    for page in batch.pages:
        assert page.page_id in text
        image = Image.open(io.BytesIO(page.png))
        # Independent label rendering with exact ID must match the actual added pixels.
        expected = Image.new("RGB", (image.width, 80), "white")
        ImageDraw.Draw(expected).text(
            (20, 18),
            page.page_id,
            font=ImageFont.load_default(size=32),
            fill="black",
        )
        assert (
            image.crop((0, 0, image.width, 80)).tobytes() == expected.tobytes()
        )
        assert image.height > 80
        # Preserve a downscaled label example for manual LLM readability acceptance.
    metadata = json.dumps(batch.metadata())
    assert (
        "png" in metadata
        and "ALPHA" not in metadata
        and "base64" not in metadata
    )
    assert batch.metadata()["documents"][0]["source_parameter"] == "pdf_files"
    assert batch.metadata()["documents"][1]["source_parameter"] == "pdf_files"
    other = convert([item(make_pdf())], 36, Limits())
    assert other.batch_id != batch.batch_id


@pytest.mark.parametrize("data", [b"%PDF-invalid", make_pdf(encrypted=True)])
def test_corrupt_password_fail_position_and_recovery(data):
    with pytest.raises(ConversionError, match=r"pdf_files\[0\].*PDF_OPEN"):
        convert([item(data)], 150, Limits())
    assert convert([item(make_pdf())], 36, Limits()).pages
    assert not list(runtime_root().glob("run-*"))


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("max_files", 1, "file count"),
        ("input_file_bytes", 100, "input bytes"),
        ("input_total_bytes", 100, "input bytes"),
        ("pages_per_file", 1, "page count"),
        ("pages_total", 1, "page count"),
        ("max_width", 100, "dimensions"),
        ("max_height", 100, "dimensions"),
        ("max_pixels", 100, "dimensions"),
        ("output_file_bytes", 100, "PNG bytes"),
        ("output_total_bytes", 100, "total PNG"),
        ("text_chars", 1, "text characters"),
    ],
)
def test_actual_limit_failures(field, value, expected):
    inputs = [item(make_pdf(pages=2))]
    if field == "max_files":
        inputs *= 2
    with pytest.raises(ConversionError, match=expected):
        convert(inputs, 150, replace(Limits(), **{field: value}))
    assert not list(runtime_root().glob("run-*"))


def test_exact_input_page_text_and_output_thresholds():
    data = make_pdf()
    baseline = convert([item(data)], 36, Limits())
    text_length = len(baseline.pages[0].text)
    for delta in (-1, 0, 1):
        limits = replace(Limits(), input_file_bytes=len(data) + delta)
        if delta < 0:
            with pytest.raises(ConversionError):
                convert([item(data)], 36, limits)
        else:
            assert len(convert([item(data)], 36, limits).pages) == 1
    assert convert(
        [item(data)], 36, replace(Limits(), pages_per_file=1, pages_total=1)
    ).pages
    assert convert(
        [item(data)], 36, replace(Limits(), text_chars=text_length)
    ).pages
    with pytest.raises(ConversionError):
        convert(
            [item(data)], 36, replace(Limits(), text_chars=text_length - 1)
        )
    full = format_text(baseline, 1000000)
    assert format_text(baseline, len(full)) == full
    with pytest.raises(ConversionError):
        format_text(baseline, len(full) - 1)


def test_deadline_terminates_child_cleans_and_recovers():
    with pytest.raises(ConversionError, match="PROCESS_TIMEOUT"):
        convert(
            [item(make_pdf())],
            150,
            Limits(),
            deadline=time.monotonic() + 0.001,
        )
    assert not list(runtime_root().glob("run-*"))
    assert convert([item(make_pdf())], 36, Limits()).pages


def test_memory_exit_cleans_and_recovers():
    with pytest.raises(ConversionError, match="PROCESS_EXIT"):
        convert(
            [item(make_pdf())], 150, replace(Limits(), memory_bytes=1_000_000)
        )
    assert not list(runtime_root().glob("run-*"))
    assert convert([item(make_pdf())], 36, Limits()).pages


def test_cross_process_slot_busy_recovers():
    import subprocess
    import sys

    with execution_slot(Limits()):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pdf_core.runner import execution_slot\n"
                    "from pdf_core.config import Limits\n"
                    "with execution_slot(Limits()): pass"
                ),
            ],
            capture_output=True,
        )
        assert result.returncode != 0 and b"BUSY" in result.stderr
    with execution_slot(Limits()):
        pass


@pytest.mark.parametrize(
    "dpi", [False, "150", float("nan"), float("inf"), 35, 201]
)
def test_dpi_invalid(dpi):
    with pytest.raises(ConversionError):
        Limits().dpi(dpi)


def test_terminate_then_sigkill_reaps_signal_resistant_native_work():
    import subprocess
    import sys

    from pdf_core.runner import stop_child

    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                "print('ready',flush=True);time.sleep(30)"
            ),
        ],
        stdout=subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdout.readline() == b"ready\n"
    start = time.monotonic()
    stop_child(process)
    assert process.poll() is not None and time.monotonic() - start < 3
    process.stdout.close()
    assert convert([item(make_pdf())], 36, Limits()).pages


def test_remaining_exact_budget_boundaries(monkeypatch):
    from uuid import UUID

    import pdf_core.runner as module

    monkeypatch.setattr(module, "uuid4", lambda: UUID(int=0))
    data = make_pdf(pages=2)
    inputs = [item(data)]
    baseline = convert(inputs, 36, Limits())
    first_image = Image.open(io.BytesIO(baseline.pages[0].png))
    boundaries = {
        "input_total_bytes": len(data),
        "pages_per_file": 2,
        "pages_total": 2,
        "max_width": first_image.width,
        "max_height": first_image.height,
        "max_pixels": first_image.width * first_image.height,
        "output_file_bytes": max(len(p.png) for p in baseline.pages),
        "output_total_bytes": sum(len(p.png) for p in baseline.pages),
    }
    for field, threshold in boundaries.items():
        for delta in (-1, 0, 1):
            limits = replace(Limits(), **{field: threshold + delta})
            if delta < 0:
                with pytest.raises(ConversionError):
                    convert(inputs, 36, limits)
            else:
                assert len(convert(inputs, 36, limits).pages) == 2
    pair = [item(make_pdf()), item(make_pdf(), "pdf_files", 0)]
    for count in (1, 2, 3):
        if count == 1:
            with pytest.raises(ConversionError):
                convert(pair, 36, replace(Limits(), max_files=count))
        else:
            assert (
                len(
                    convert(
                        pair, 36, replace(Limits(), max_files=count)
                    ).documents
                )
                == 2
            )
    for dpi in (199, 200, 201):
        if dpi > 200:
            with pytest.raises(ConversionError):
                Limits().dpi(dpi)
        else:
            assert Limits().dpi(dpi) == dpi


@pytest.mark.parametrize(
    "method,code", [("render", "PDF_RENDER"), ("get_textpage", "PDF_TEXT")]
)
def test_injected_native_phase_failure_sanitizes_and_no_success(
    tmp_path, method, code
):
    import os
    import subprocess
    import sys
    from dataclasses import asdict

    (tmp_path / "input.pdf").write_bytes(make_pdf())
    request = {
        "batch_id": "BTEST",
        "limits": asdict(Limits()),
        "dpi": 36,
        "parent_pid": os.getpid(),
        "documents": [
            {
                "filename": "DO_NOT_LOG.pdf",
                "source_parameter": "pdf_files",
                "source_index": 1,
                "input_path": "input.pdf",
            }
        ],
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    source = (
        "import sys,pypdfium2\nfrom pathlib import Path\n"
        "from pdf_core.worker import run\n"
        "def fail(*args,**kwargs): raise RuntimeError('SIGNED_URL_SECRET')\n"
        f"pypdfium2.PdfPage.{method}=fail\nrun(Path(sys.argv[1]))"
    )
    process = subprocess.run(
        [sys.executable, "-c", source, str(path)], capture_output=True
    )
    assert process.returncode == 0
    result = json.loads((tmp_path / "result.json").read_text())
    assert list(result) == ["error"]
    assert code in result["error"] and "pdf_files[1] page 1" in result["error"]
    assert (
        "SIGNED_URL_SECRET" not in result["error"]
        and "DO_NOT_LOG" not in result["error"]
    )


def test_original_page_pixels_remain_unmodified_below_label():
    from contextlib import closing

    import pypdfium2

    data = make_pdf(mixed=True)
    batch = convert([item(data)], 150, Limits())
    with pypdfium2.PdfDocument(data) as pdf:
        for index, record in enumerate(batch.pages):
            with (
                closing(pdf[index]) as page,
                closing(page.render(scale=150 / 72)) as bitmap,
            ):
                original = bitmap.to_pil().convert("RGB")
                result = Image.open(io.BytesIO(record.png))
                body = result.crop(
                    (0, 80, original.width, 80 + original.height)
                )
                assert body.tobytes() == original.tobytes()
                original.close()


def test_text_result_json_can_exceed_png_limit_without_rejecting_in_budget_pdf():
    from reportlab.pdfgen.canvas import Canvas

    stream = io.BytesIO()
    canvas = Canvas(
        stream, pagesize=(595, 842), invariant=1, pageCompression=1
    )
    # Many short PDF text operands avoid native single-string parser limits.
    text = canvas.beginText(10, 800)
    text.setFont("Helvetica", 0.1)
    text.setLeading(0.1)
    for _ in range(100):
        text.textLine("A" * 1008)
    canvas.drawText(text)
    canvas.showPage()
    canvas.save()
    data = stream.getvalue()
    limits = replace(Limits(), output_file_bytes=32768)
    batch = convert([item(data)], 36, limits)
    assert len(batch.pages[0].text) >= 100000
    assert len(batch.pages[0].png) < limits.output_file_bytes
    assert len(data) < limits.input_file_bytes
    assert len(format_text(batch, limits.text_chars)) < limits.text_chars
    with pytest.raises(ConversionError, match="PNG bytes"):
        convert([item(data)], 36, replace(limits, output_file_bytes=100))
