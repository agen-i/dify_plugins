"""Independent runtime origins retain the required file route and network boundaries."""

import time
from pathlib import Path

import pytest
import yaml
from pdf_core import config
from pdf_core.fetch import select_source
from pdf_core.model import ConversionError
from provider.pdf_text_pages import PdfTextPagesProvider


def test_provider_has_empty_credentials_schema():
    provider = yaml.safe_load(Path("provider/pdf_text_pages.yaml").read_text())
    assert provider["credentials_for_provider"] == {}


def test_provider_does_not_require_credentials_or_file_settings():
    PdfTextPagesProvider()._validate_credentials({})


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


@pytest.mark.parametrize(
    "path",
    [
        "/base/files/01234567-89ab-cdef-0123-456789abcdef/file-preview",
        "/base/files/tools/01234567-89ab-cdef-0123-456789abcdef.pdf",
    ],
)
def test_approved_runtime_base_keeps_both_routes_and_exact_query(path):
    sources = (
        config.parse_runtime_base("http://internal.test:8080/base", "runtime"),
    )
    selected, target = select_source(
        "http://internal.test:8080" + path + "?sign=KEEP", sources
    )
    assert selected.host == "internal.test" and selected.port == 8080
    assert target == path + "?sign=KEEP"
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source("https://public.test/base/files/x/file-preview", sources)


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
def test_invalid_control_plane_base_is_rejected_without_exposing_value(base):
    with pytest.raises(ConversionError) as caught:
        config.parse_runtime_base(base, "runtime source")
    assert "CONFIG" in str(caught.value)
    assert "HIDDEN" not in str(caught.value) and "internal.test" not in str(
        caught.value
    )


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
def test_runtime_origin_limits_download_routes(path):
    sources = (
        config.parse_runtime_base("http://internal.test/base", "runtime"),
    )
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source("http://internal.test" + path, sources)


def test_input_url_cannot_expand_independently_approved_origin():
    sources = (
        config.parse_runtime_base("http://internal.test/base", "runtime"),
    )
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source(
            "http://attacker.test/base/files/x/file-preview?sign=HIDDEN",
            sources,
        )


def test_explicit_zero_port_is_not_default():
    sources = (config.parse_runtime_base("http://internal.test", "runtime"),)
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source("http://internal.test:0/files/x/file-preview", sources)
