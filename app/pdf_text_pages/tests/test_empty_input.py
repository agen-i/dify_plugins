"""No-PDF requests return empty standard outputs without acquisition/work."""

import re
from pathlib import Path

import pytest
import yaml
from pdf_core.model import ConversionError
from tools.pdf_text_pages import PdfTextPagesTool


@pytest.mark.parametrize("parameters", [{"pdf_files": []}])
def test_empty_files_skip_config_dpi_network_and_conversion(
    monkeypatch, parameters
):
    import tools.pdf_text_pages as module

    monkeypatch.setenv("PDF_TEXT_PAGES_LIMITS", "HIDDEN_INVALID_CONFIG")
    for name in (
        "FILES_URL",
        "INTERNAL_FILES_URL",
        "CONSOLE_API_URL",
        "SERVER_CONSOLE_API_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    def forbidden(*args):
        pytest.fail(
            "Empty input must not load sources or run acquisition/conversion"
        )

    for name in (
        "discover_runtime_sources",
        "fetch",
        "execution_slot",
        "convert",
        "format_text",
    ):
        monkeypatch.setattr(module, name, forbidden)
    messages = list(
        PdfTextPagesTool.from_credentials({})._invoke(
            {**parameters, "dpi": "invalid"}
        )
    )
    assert [message.type.value for message in messages] == ["text", "json"]
    assert messages[0].message.text == ""
    obj = messages[1].message.json_object
    assert obj["schema_version"] == "1.0"
    assert re.fullmatch(r"B[0-9A-F]{32}", obj["batch_id"])
    assert obj["documents"] == []


def test_only_list_parameter_is_declared():
    data = yaml.safe_load(Path("tools/pdf_text_pages.yaml").read_text())
    assert [parameter["name"] for parameter in data["parameters"]] == [
        "pdf_files",
        "dpi",
    ]


@pytest.mark.parametrize("value", ["", {}, False])
def test_falsy_malformed_list_is_not_empty_success(monkeypatch, value):
    monkeypatch.setenv("INTERNAL_FILES_URL", "http://fixture.invalid")
    with pytest.raises(ConversionError, match="expected File list"):
        list(
            PdfTextPagesTool.from_credentials({})._invoke({"pdf_files": value})
        )


@pytest.mark.parametrize("parameters", [{}, {"pdf_files": None}])
def test_unconfigured_files_public_invoke_reports_required_input(parameters):
    with pytest.raises(
        ConversionError,
        match="pdf_files: INPUT: ファイルリストにPDF/画像を受け取る変数を設定してください",
    ):
        list(PdfTextPagesTool.from_credentials({}).invoke(parameters))
