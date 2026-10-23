"""All inputs remain ordered and bounded; only PDFs create text/page groups."""

import pytest
from dify_plugin.file.file import File
from pdf_core.config import Limits
from pdf_core.model import (
    BatchRecord,
    ConversionError,
    DocumentRecord,
    PageRecord,
)
from tools.pdf_text_pages import PdfTextPagesTool

from tests.fixtures import make_pdf


def item(name, extension, mime="application/octet-stream"):
    return File(
        url="http://fixture.invalid/files/"
        + name.replace(".", "-")
        + "/file-preview",
        type="document",
        filename=name,
        extension=extension,
        mime_type=mime,
    )


@pytest.fixture
def invoke(monkeypatch):
    import tools.pdf_text_pages as module

    monkeypatch.setenv("INTERNAL_FILES_URL", "http://fixture.invalid")
    data = {}
    calls = []

    def acquire(url, sources, limits, remaining, deadline):
        calls.append(url)
        value = data[url]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(module, "fetch", acquire)

    def run(files, bodies, **parameters):
        data.update(
            (file.url, body) for file, body in zip(files, bodies, strict=True)
        )
        return PdfTextPagesTool.from_credentials({})._invoke(
            {"pdf_files": files, "dpi": 36, **parameters}
        )

    return run, calls


def test_mixed_order_pdf_groups_bytes_and_final_image_indices(invoke):
    run, _ = invoke
    files = [
        item("first.jpg", ".jpg", "image/jpeg"),
        item("alpha.PDF", ".PDF", "application/pdf"),
        item("note.txt", ".txt", "text/plain"),
        item("last.png", ".png", "image/png"),
        item("beta.pdf", ".pdf", "application/pdf"),
    ]
    bodies = [
        b"jpeg-unchanged",
        make_pdf(mixed=True),
        b"text-unchanged",
        b"png-unchanged",
        make_pdf(word="BETA"),
    ]
    messages = list(run(files, bodies))
    blobs = messages[1:-1]
    assert len(blobs) == 8
    for index, body, file in [
        (0, bodies[0], files[0]),
        (5, bodies[2], files[2]),
        (6, bodies[3], files[3]),
    ]:
        assert blobs[index].message.blob == body
        assert blobs[index].meta == {
            "filename": file.filename,
            "mime_type": file.mime_type,
        }
    assert all(
        blobs[index].message.blob.startswith(b"\x89PNG")
        for index in [1, 2, 3, 4, 7]
    )
    text = messages[0].message.text
    assert "ALPHA" in text and "BETA" in text
    assert all(
        file.filename not in text for file in [files[0], files[2], files[3]]
    )
    obj = messages[-1].message.json_object
    assert obj["schema_version"] == "1.0" and len(obj["documents"]) == 2
    assert [doc["source_index"] for doc in obj["documents"]] == [1, 4]
    assert [
        [page["image_index"] for page in doc["pages"]]
        for doc in obj["documents"]
    ] == [[1, 2, 3, 4], [7]]


def test_nonpdf_only_has_empty_text_no_conversion_and_exact_metadata(
    invoke, monkeypatch
):
    import tools.pdf_text_pages as module

    def forbidden(*args):
        pytest.fail("No PDF must not run native conversion or the PDF guide")

    monkeypatch.setattr(module, "convert", forbidden)
    monkeypatch.setattr(module, "format_text", forbidden)
    run, _ = invoke
    files = [
        item("raw.bin", ".bin", "application/pdf"),
        item("note.txt", ".txt", "text/plain"),
    ]
    bodies = [b"%PDF-unchanged-as-bin", b"unchanged note"]
    messages = list(run(files, bodies))
    assert messages[0].message.text == ""
    assert [message.message.blob for message in messages[1:-1]] == bodies
    assert messages[-1].message.json_object["documents"] == []


@pytest.mark.parametrize(
    "extension,name", [(".pDf", "case.bin"), (None, "case.PDF")]
)
def test_pdf_extension_dispatch_and_filename_fallback_ignore_mime(
    invoke, extension, name
):
    run, _ = invoke
    messages = list(run([item(name, extension, "text/plain")], [make_pdf()]))
    assert "ALPHA" in messages[0].message.text
    assert messages[1].meta["mime_type"] == "image/png"


def test_extension_field_wins_over_pdf_filename(invoke):
    run, _ = invoke
    body = make_pdf()
    messages = list(
        run([item("named.pdf", ".dat", "application/pdf")], [body])
    )
    assert messages[0].message.text == "" and messages[1].message.blob == body


def test_passthrough_output_file_cap_is_checked_before_yield(
    invoke, monkeypatch
):
    import tools.pdf_text_pages as module

    monkeypatch.setattr(
        module.Limits, "from_env", lambda: Limits(output_file_bytes=50)
    )
    run, _ = invoke
    with pytest.raises(ConversionError, match="LIMIT"):
        next(run([item("raw.bin", ".bin")], [b"x" * 51]))
    messages = list(run([item("raw.bin", ".bin")], [b"x" * 50]))
    assert messages[1].message.blob == b"x" * 50


def test_pdf_and_passthrough_share_total_output_budget(invoke, monkeypatch):
    import tools.pdf_text_pages as module

    monkeypatch.setattr(
        module.Limits,
        "from_env",
        lambda: Limits(output_file_bytes=50, output_total_bytes=70),
    )
    batch_id = "B" + "0" * 32
    doc_id = batch_id + "-D001"
    page_id = doc_id + "-P0001"
    page = PageRecord(page_id, 1, "synthetic", 0, page_id + ".png", b"x" * 40)
    monkeypatch.setattr(
        module,
        "convert",
        lambda *args: BatchRecord(
            batch_id,
            [DocumentRecord(doc_id, "pdf.pdf", "pdf_files", 1, [page])],
        ),
    )
    run, _ = invoke
    with pytest.raises(ConversionError, match="LIMIT"):
        next(
            run(
                [
                    item("raw.bin", ".bin"),
                    item("pdf.pdf", ".pdf", "application/pdf"),
                ],
                [b"x" * 40, b"%PDF-synthetic"],
            )
        )


def test_late_failure_never_yields_prior_passthrough(invoke):
    run, _ = invoke
    with pytest.raises(ConversionError, match="FETCH_FAILURE"):
        next(
            run(
                [
                    item("first.txt", ".txt"),
                    item("later.pdf", ".pdf", "application/pdf"),
                ],
                [b"unchanged", ConversionError("FETCH_FAILURE: synthetic")],
            )
        )


def test_corrupt_pdf_never_yields_prior_passthrough(invoke):
    run, _ = invoke
    with pytest.raises(ConversionError, match="PDF_OPEN"):
        next(
            run(
                [item("first.txt", ".txt"), item("bad.pdf", ".pdf")],
                [b"unchanged", b"%PDF-invalid"],
            )
        )


def test_all_inputs_share_file_count_limit_before_fetch(invoke):
    run, calls = invoke
    files = [item(f"raw{index}.bin", ".bin") for index in range(6)]
    with pytest.raises(ConversionError, match="input file count"):
        next(run(files, [b"x"] * 6))
    assert calls == []


def test_missing_passthrough_metadata_uses_only_declared_sdk_fallback(invoke):
    run, _ = invoke
    file = File(
        url="http://fixture.invalid/files/raw/file-preview",
        type="document",
        extension=".bin",
        filename=None,
        mime_type=None,
    )
    messages = list(run([file], [b"unchanged"]))
    assert messages[1].meta == {
        "filename": "file",
        "mime_type": "application/octet-stream",
    }
