"""Credential-free operation must retain independent Dify source boundaries."""

import time
from pathlib import Path

import pytest
import yaml
from dify_plugin.file.file import File
from pdf_core import config
from pdf_core.fetch import select_source
from pdf_core.model import ConversionError
from provider.pdf_text_pages import PdfTextPagesProvider
from tools.pdf_text_pages import PdfTextPagesTool


@pytest.fixture(autouse=True)
def clean_file_settings(monkeypatch):
    for name in (
        "FILES_URL",
        "INTERNAL_FILES_URL",
        "CONSOLE_API_URL",
        "SERVER_CONSOLE_API_URL",
        "DIFY_INNER_API_URL",
        "PLUGIN_DIFY_INNER_API_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_provider_has_empty_credentials_schema():
    provider = yaml.safe_load(Path("provider/pdf_text_pages.yaml").read_text())
    assert provider["credentials_for_provider"] == {}


def test_provider_does_not_require_credentials_or_file_settings():
    PdfTextPagesProvider()._validate_credentials({})


def test_missing_settings_are_japanese_node_error_before_network(monkeypatch):
    def forbidden(*args):
        pytest.fail("Missing trusted configuration must fail before network")

    monkeypatch.setattr("tools.pdf_text_pages.fetch", forbidden)
    file = File(
        url="http://input.invalid/files/x/file-preview?sign=HIDDEN",
        type="document",
        filename="x.pdf",
        extension=".pdf",
        mime_type="application/pdf",
    )
    with pytest.raises(ConversionError) as caught:
        list(
            PdfTextPagesTool.from_credentials({})._invoke(
                {"pdf_files": [file]}
            )
        )
    message = str(caught.value)
    assert "FILES_URL" in message and "INTERNAL_FILES_URL" in message
    assert "管理者" in message and "継承" in message
    assert "input.invalid" not in message and "HIDDEN" not in message


@pytest.mark.parametrize(
    "path",
    [
        "/base/files/01234567-89ab-cdef-0123-456789abcdef/file-preview",
        "/base/files/tools/01234567-89ab-cdef-0123-456789abcdef.pdf",
    ],
)
def test_plugin_files_use_internal_source_for_both_routes(monkeypatch, path):
    monkeypatch.setenv("FILES_URL", "https://public.test/public")
    monkeypatch.setenv("INTERNAL_FILES_URL", "http://internal.test:8080/base")
    sources = config.load_runtime_sources()
    selected, target = select_source(
        "http://internal.test:8080" + path + "?sign=KEEP", sources
    )
    assert selected.host == "internal.test" and selected.port == 8080
    assert target == path + "?sign=KEEP"
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source(
            "https://public.test/public/files/x/file-preview", sources
        )


@pytest.mark.parametrize("internal", [None, ""])
def test_files_url_fallback_when_internal_base_is_absent(
    monkeypatch, internal
):
    monkeypatch.setenv("FILES_URL", "https://public.test/base/")
    monkeypatch.setenv("DIFY_INNER_API_URL", "https://public.test")
    if internal is not None:
        monkeypatch.setenv("INTERNAL_FILES_URL", internal)
    source, _ = select_source(
        "https://public.test/base//files/01234567-89ab-cdef-0123-456789abcdef/file-preview",
        config.load_runtime_sources(),
    )
    assert source.host == "public.test"


@pytest.mark.parametrize(
    "base",
    [
        "http://user:HIDDEN@internal.test/base",
        "file:///tmp/HIDDEN",
        "http://internal.test/base?token=HIDDEN",
        "http://internal.test/base#HIDDEN",
        "http://internal.test/base/%2e%2e/HIDDEN",
        "http://internal.test:0/base/HIDDEN",
    ],
)
def test_invalid_internal_setting_does_not_fallback_or_expose_value(
    monkeypatch, base
):
    monkeypatch.setenv("FILES_URL", "https://public.test")
    monkeypatch.setenv("INTERNAL_FILES_URL", base)
    with pytest.raises(ConversionError) as caught:
        config.load_runtime_sources()
    message = str(caught.value)
    assert "INTERNAL_FILES_URL" in message and "管理者" in message
    assert "HIDDEN" not in message and "internal.test" not in message


@pytest.mark.parametrize(
    "path",
    [
        "/base/files/x/other",
        "/base/files/tools/x.pdf/extra",
        "/base/files/../admin",
        "/base/files/%2fx/file-preview",
        "/base2/files/x/file-preview",
        "/base/files/x/file-preview#secret",
    ],
)
def test_runtime_sources_limit_required_download_routes(monkeypatch, path):
    monkeypatch.setenv("INTERNAL_FILES_URL", "http://internal.test/base")
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source(
            "http://internal.test" + path, config.load_runtime_sources()
        )


def test_input_url_cannot_supply_or_expand_trusted_configuration(monkeypatch):
    monkeypatch.setenv("INTERNAL_FILES_URL", "http://internal.test/base")
    sources = config.load_runtime_sources()
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source(
            "http://attacker.test/base/files/x/file-preview?sign=HIDDEN",
            sources,
        )
    assert config.load_runtime_sources() == sources


def test_absent_primary_settings_use_existing_console_aliases(monkeypatch):
    monkeypatch.setenv("CONSOLE_API_URL", "https://public.test/base")
    monkeypatch.setenv("SERVER_CONSOLE_API_URL", "http://internal.test/base")
    source, _ = select_source(
        "http://internal.test/base/files/x/file-preview",
        config.load_runtime_sources(),
    )
    assert source.host == "internal.test"


def test_present_empty_internal_primary_does_not_use_its_alias(monkeypatch):
    monkeypatch.setenv("INTERNAL_FILES_URL", "")
    monkeypatch.setenv("SERVER_CONSOLE_API_URL", "http://ignored.test")
    monkeypatch.setenv("FILES_URL", "https://public.test")
    monkeypatch.setenv("DIFY_INNER_API_URL", "https://public.test")
    source, _ = select_source(
        "https://public.test/files/x/file-preview",
        config.load_runtime_sources(),
    )
    assert source.host == "public.test"


def test_present_empty_files_primary_does_not_use_its_alias(monkeypatch):
    monkeypatch.setenv("FILES_URL", "")
    monkeypatch.setenv("CONSOLE_API_URL", "https://ignored.test")
    with pytest.raises(ConversionError) as caught:
        config.load_runtime_sources()
    assert "FILES_URL" in str(caught.value)


def test_dns_deadline_terminates_resolver_and_does_not_expose_host(
    monkeypatch,
):
    import pdf_core.fetch as module

    monkeypatch.setattr(module, "_DNS_QUERY", "import time; time.sleep(10)")
    start = time.monotonic()
    with pytest.raises(ConversionError, match="FETCH_TIMEOUT") as caught:
        module.resolve_address(
            config.AllowedSource("http", "secret.test", 80, "/files/"),
            start + 0.15,
        )
    assert time.monotonic() - start < 1.0
    assert "secret.test" not in str(caught.value)


def test_actual_resolver_snapshot_is_pinned_and_peer_is_verified():
    import pdf_core.fetch as module

    source = config.AllowedSource("http", "localhost", 80, "/files/")
    address = module.resolve_address(source, time.monotonic() + 2)
    assert address in ("127.0.0.1", "::1")

    class Peer:
        def getpeername(self):
            return "192.0.2.66", 80

    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        module.verify_peer(Peer(), address, 80)


def test_explicit_zero_port_is_not_treated_as_default(monkeypatch):
    monkeypatch.setenv("INTERNAL_FILES_URL", "http://internal.test")
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source(
            "http://internal.test:0/files/x/file-preview",
            config.load_runtime_sources(),
        )
