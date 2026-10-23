"""Authorized incoming origin maps only to an independently configured API."""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pdf_core.config import Limits, load_runtime_sources
from pdf_core.fetch import fetch, select_source
from pdf_core.model import ConversionError


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    for name in (
        "FILES_URL",
        "INTERNAL_FILES_URL",
        "CONSOLE_API_URL",
        "SERVER_CONSOLE_API_URL",
        "DIFY_INNER_API_URL",
        "PLUGIN_DIFY_INNER_API_URL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def internal_server():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append((self.path, self.headers["Host"]))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"%PDF-synthetic")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1], calls
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.mark.parametrize(
    "path", ["/files/abc/file-preview", "/files/tools/abc.pdf"]
)
def test_public_approved_url_connects_only_to_internal_same_path_query(
    monkeypatch, internal_server, path
):
    import pdf_core.fetch as module

    port, calls = internal_server
    monkeypatch.setenv("FILES_URL", "https://public.test")
    monkeypatch.setenv("DIFY_INNER_API_URL", f"http://internal.test:{port}")
    resolved = []

    def resolve(source, deadline):
        resolved.append(source.host)
        assert source.host == "internal.test"
        return ("127.0.0.1",)

    monkeypatch.setattr(module, "resolve_addresses", resolve)
    monkeypatch.setenv("HTTP_PROXY", "http://invalid:9")
    query = "?timestamp=1&nonce=SYNTHETIC&sign=HIDDEN%2Fvalue"
    data = fetch(
        "https://public.test" + path + query,
        load_runtime_sources(),
        Limits(),
        1000,
        time.monotonic() + 2,
    )
    assert data == b"%PDF-synthetic"
    assert resolved == ["internal.test"]
    assert calls == [(path + query, f"internal.test:{port}")]


@pytest.mark.parametrize(
    "url",
    [
        "https://other.test/files/a/file-preview",
        "https://public.test/admin/a",
        "https://public.test/files/%2e%2e/admin",
    ],
)
def test_mapping_does_not_authorize_foreign_origin_or_route(monkeypatch, url):
    monkeypatch.setenv("FILES_URL", "https://public.test")
    monkeypatch.setenv("DIFY_INNER_API_URL", "http://internal.test")
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source(url, load_runtime_sources())


@pytest.mark.parametrize(
    "inner",
    [
        None,
        "",
        "file:///HIDDEN",
        "http://user:HIDDEN@internal.test",
        "http://internal.test?token=HIDDEN",
    ],
)
def test_mapping_missing_or_invalid_internal_config_fails_before_network(
    monkeypatch, inner
):
    monkeypatch.setenv("FILES_URL", "https://public.test")
    if inner is not None:
        monkeypatch.setenv("DIFY_INNER_API_URL", inner)
    with pytest.raises(ConversionError, match="CONFIG") as caught:
        load_runtime_sources()
    message = str(caught.value)
    assert "DIFY_INNER_API_URL" in message and "管理者" in message
    assert "HIDDEN" not in message and "internal.test" not in message


def test_compose_input_name_is_not_a_plugin_alias(monkeypatch):
    monkeypatch.setenv("FILES_URL", "https://public.test")
    monkeypatch.setenv("PLUGIN_DIFY_INNER_API_URL", "http://internal.test")
    with pytest.raises(ConversionError, match="DIFY_INNER_API_URL"):
        load_runtime_sources()


def test_existing_internal_file_source_does_not_validate_unneeded_api(
    monkeypatch,
):
    monkeypatch.setenv("INTERNAL_FILES_URL", "http://internal.test/base")
    monkeypatch.setenv("DIFY_INNER_API_URL", "HIDDEN_INVALID")
    source, path = select_source(
        "http://internal.test/base/files/a/file-preview?sign=KEEP",
        load_runtime_sources(),
    )
    assert source.host == "internal.test" and path.endswith("?sign=KEEP")


def test_same_origin_preserves_direct_request(monkeypatch):
    monkeypatch.setenv("FILES_URL", "https://public.test/base")
    monkeypatch.setenv(
        "DIFY_INNER_API_URL", "https://public.test/other-api-path"
    )
    source, path = select_source(
        "https://public.test/base/files/a/file-preview?sign=KEEP",
        load_runtime_sources(),
    )
    assert source.host == "public.test" and source.scheme == "https"
    assert path == "/base/files/a/file-preview?sign=KEEP"


@pytest.mark.parametrize(
    "external,inner",
    [
        ("https://public.test/base", "http://internal.test"),
        ("https://public.test/base", "http://internal.test/base"),
    ],
)
def test_nonroot_cross_origin_prefix_is_not_silently_rebased(
    monkeypatch, external, inner
):
    monkeypatch.setenv("FILES_URL", external)
    monkeypatch.setenv("DIFY_INNER_API_URL", inner)
    with pytest.raises(ConversionError, match="CONFIG"):
        load_runtime_sources()


def test_cross_origin_public_trailing_slash_does_not_guess_api_double_slash_route(
    monkeypatch,
):
    monkeypatch.setenv("FILES_URL", "https://public.test/")
    monkeypatch.setenv("DIFY_INNER_API_URL", "http://internal.test/")
    with pytest.raises(ConversionError, match="CONFIG"):
        load_runtime_sources()
