import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File
from pdf_core.config import Limits, load_sources
from pdf_core.fetch import fetch, select_source
from pdf_core.model import ConversionError
from tools.pdf_text_pages import PdfTextPagesTool, normalize

from tests.fixtures import make_pdf


@pytest.fixture
def server(monkeypatch):
    pdf = make_pdf()
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append((self.path, self.headers.get("Host")))
            if self.path.startswith("/files/redirect"):
                self.send_response(302)
                self.send_header(
                    "Location", "http://unapproved.example/secret"
                )
                self.end_headers()
                return
            if self.path.startswith("/files/drip"):
                # Never finish headers; each byte is inside socket idle timeout.
                try:
                    for _ in range(100):
                        self.wfile.write(b"H")
                        self.wfile.flush()
                        time.sleep(0.1)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            # No Content-Length: cap must use actual bytes.
            self.end_headers()
            self.wfile.write(pdf)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    port = httpd.server_address[1]
    raw = json.dumps(
        [
            {
                "scheme": "http",
                "host": "dify.test",
                "port": port,
                "path_prefix": "/files/",
                "address": "127.0.0.1",
            }
        ]
    )
    monkeypatch.setenv("INTERNAL_FILES_URL", f"http://dify.test:{port}")
    import pdf_core.fetch as fetch_module

    monkeypatch.setattr(
        fetch_module,
        "resolve_addresses",
        lambda source, deadline: (source.address or "127.0.0.1",),
    )
    yield f"http://dify.test:{port}", raw, calls, pdf
    httpd.shutdown()
    httpd.server_close()
    worker.join()


@pytest.mark.parametrize(
    "path",
    [
        "/files2/x",
        "/files/../secret",
        "/files/%2e%2e/secret",
        "/files/%2fx",
        "/files/%252fx",
        "/files/x#fragment",
        "/files/\\x",
        "/files/%5cx",
        "/files/%0ax",
    ],
)
def test_reject_path_boundaries_without_network(server, path):
    base, raw, calls, _ = server
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        fetch(
            base + path,
            load_sources(raw),
            Limits(),
            100000,
            time.monotonic() + 2,
        )
    assert calls == []


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://elsewhere:80/files/x",
        "http://u:secret@dify.test/files/x",
        "https://dify.test/files/x",
        "http://dify.test:1/files/x",
        "http://dify.test/files/x\n",
    ],
)
def test_url_rules(url, server):
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        select_source(url, load_sources(server[1]))
    assert server[2] == []


def test_pinned_host_proxy_disabled_and_actual_byte_limits(
    server, monkeypatch
):
    base, raw, calls, pdf = server
    monkeypatch.setenv("HTTP_PROXY", "http://invalid:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://invalid:9")
    monkeypatch.setenv("ALL_PROXY", "http://invalid:9")
    sources = load_sources(raw)
    assert (
        fetch(
            base + "/files/x?signed=DO_NOT_LOG",
            sources,
            Limits(),
            len(pdf),
            time.monotonic() + 2,
        )
        == pdf
    )
    assert calls[0][1] == base.removeprefix("http://")
    with pytest.raises(ConversionError, match="input bytes"):
        fetch(
            base + "/files/x/file-preview",
            sources,
            Limits(),
            len(pdf) - 1,
            time.monotonic() + 2,
        )
    assert (
        fetch(
            base + "/files/x/file-preview",
            sources,
            Limits(),
            len(pdf) + 1,
            time.monotonic() + 2,
        )
        == pdf
    )


def test_redirect_not_followed_and_signed_url_error_sanitized(server, caplog):
    base, raw, calls, _ = server
    secret = "NEVER_EXPOSE"
    with pytest.raises(ConversionError) as caught:
        fetch(
            base + "/files/redirect?token=" + secret,
            load_sources(raw),
            Limits(),
            10000,
            time.monotonic() + 2,
        )
    assert "FETCH_HTTP" in str(caught.value)
    assert secret not in str(caught.value) and secret not in caplog.text
    assert len(calls) == 1


def test_cumulative_deadline_includes_drip_headers(server):
    base, raw, _, _ = server
    start = time.monotonic()
    with pytest.raises(ConversionError):
        fetch(
            base + "/files/drip?token=HIDDEN",
            load_sources(raw),
            Limits(),
            10000,
            start + 0.35,
        )
    assert time.monotonic() - start < 1.5


def dify_file(url, name="same.pdf", size=None):
    return File(
        url=url,
        type="document",
        mime_type="application/pdf",
        extension=".pdf",
        filename=name,
        size=size,
    )


def adapter(raw):
    return PdfTextPagesTool.from_credentials({})


@pytest.mark.parametrize("count", [1, 2, 3])
def test_sdk_inputs_output_messages_direct_contract(server, count):
    base, raw, _, _ = server
    files = [
        dify_file(base + "/files/a/file-preview"),
        dify_file(base + "/files/b/file-preview"),
    ]
    # Dify casts a selected single File to a one-element list before the SDK.
    selected = files[:count] if count <= 2 else [files[0], *files]
    parameters = {"dpi": 36, "pdf_files": selected}
    # Exercise the pinned SDK's native dict/list -> File normalization.
    raw_params = {
        k: (
            [f.model_dump() for f in v]
            if isinstance(v, list)
            else v.model_dump() if isinstance(v, File) else v
        )
        for k, v in parameters.items()
    }
    params = PdfTextPagesTool._convert_parameters(raw_params)
    messages = list(adapter(raw)._invoke(params))
    assert all(isinstance(m, ToolInvokeMessage) for m in messages)
    assert [m.type.value for m in messages] == ["text"] + ["blob"] * count + [
        "json"
    ]
    obj = messages[-1].message.json_object
    assert isinstance(obj, dict) and len(obj["documents"]) == count
    assert "ALPHA" in messages[0].message.text
    for message, document in zip(
        messages[1:-1], obj["documents"], strict=True
    ):
        assert message.message.blob.startswith(b"\x89PNG")
        assert message.meta["mime_type"] == "image/png"
        assert (
            message.meta["filename"] == document["pages"][0]["image_filename"]
        )
        assert document["pages"][0]["page_id"] in messages[0].message.text


def test_no_partial_yield_for_late_failure(server):
    base, raw, _, _ = server
    generator = adapter(raw)._invoke(
        {
            "pdf_files": [
                dify_file(base + "/files/a/file-preview"),
                dify_file(base + "/files/redirect/file-preview"),
            ]
        }
    )
    with pytest.raises(ConversionError, match=r"pdf_files\[1\].*FETCH_HTTP"):
        next(generator)


def test_no_partial_yield_for_conversion_failure(server, monkeypatch):
    import tools.pdf_text_pages as module

    base, raw, _, _ = server
    monkeypatch.setattr(module, "fetch", lambda *args: b"%PDF-invalid")
    generator = adapter(raw)._invoke(
        {"pdf_files": [dify_file(base + "/files/x/file-preview")]}
    )
    with pytest.raises(ConversionError, match=r"pdf_files\[0\].*PDF_OPEN"):
        next(generator)


def test_no_partial_yield_for_whole_request_deadline(server, monkeypatch):
    import tools.pdf_text_pages as module

    base, raw, _, pdf = server

    def delayed(*args):
        time.sleep(0.6)
        return pdf

    monkeypatch.setattr(module, "fetch", delayed)
    monkeypatch.setenv("PDF_TEXT_PAGES_LIMITS", '{"request_seconds":1}')
    generator = adapter(raw)._invoke(
        {
            "pdf_files": [
                dify_file(base + "/files/a/file-preview"),
                dify_file(base + "/files/b/file-preview"),
            ]
        }
    )
    with pytest.raises(ConversionError, match="PROCESS_TIMEOUT"):
        next(generator)


@pytest.mark.parametrize(
    "parameters",
    [
        {"pdf_files": "http://x"},
        {"pdf_files": "/tmp/x"},
        {"pdf_files": ["http://x"]},
    ],
)
def test_no_urls_or_paths(parameters):
    with pytest.raises(ConversionError):
        normalize(parameters, Limits())


@pytest.mark.parametrize(
    "raw", [None, "[]", "{}", '{"scheme":"http"}', '[{"scheme":"file"}]']
)
def test_admin_allowlist_fail_closed(raw):
    with pytest.raises(ConversionError, match="CONFIG"):
        load_sources(raw)


def test_https_pinned_ip_preserves_sni_and_verifies_hostname(
    tmp_path, monkeypatch
):
    import ssl
    import subprocess

    import pdf_core.fetch as module

    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=dify.test",
            "-addext",
            "subjectAltName=DNS:dify.test",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.headers["Host"])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"%PDF-test")

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    sni = []
    ctx.set_servername_callback(lambda sock, name, context: sni.append(name))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    original = ssl.create_default_context
    monkeypatch.setattr(
        module.ssl,
        "create_default_context",
        lambda: original(cafile=str(cert)),
    )
    port = httpd.server_address[1]
    try:
        raw = [
            {
                "scheme": "https",
                "host": "dify.test",
                "port": port,
                "path_prefix": "/files/",
                "address": "127.0.0.1",
            }
        ]
        assert (
            fetch(
                f"https://dify.test:{port}/files/a",
                load_sources(raw),
                Limits(),
                1000,
                time.monotonic() + 3,
            )
            == b"%PDF-test"
        )
        assert seen == [f"dify.test:{port}"] and sni == ["dify.test"]
        raw[0]["host"] = "other.test"
        with pytest.raises(ConversionError, match="FETCH_FAILURE"):
            fetch(
                f"https://other.test:{port}/files/a?token=HIDDEN",
                load_sources(raw),
                Limits(),
                1000,
                time.monotonic() + 3,
            )
        assert len(seen) == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def test_ipv6_authority_and_pinned_address():
    source = load_sources(
        [
            {
                "scheme": "http",
                "host": "::1",
                "port": 8765,
                "path_prefix": "/files/",
                "address": "::1",
            }
        ]
    )
    selected, path = select_source("http://[::1]:8765/files/a", source)
    assert selected.address == "::1" and path == "/files/a"
    with pytest.raises(ConversionError):
        select_source("http://[::1]:8766/files/a", source)


def test_output_stream_keeps_capacity_until_closed(server):
    from pdf_core.runner import execution_slot

    base, raw, _, _ = server
    generator = adapter(raw)._invoke(
        {"pdf_files": [dify_file(base + "/files/x/file-preview")], "dpi": 36}
    )
    assert next(generator).type.value == "text"
    with pytest.raises(ConversionError, match="BUSY"):
        with execution_slot(Limits()):
            pass
    generator.close()
    with execution_slot(Limits()):
        pass


def test_tool_file_route_without_credentials(server):
    base, _, _, _ = server
    messages = list(
        PdfTextPagesTool.from_credentials({})._invoke(
            {
                "pdf_files": [
                    dify_file(
                        base
                        + "/files/tools/01234567-89ab-cdef-0123-456789abcdef.pdf"
                    )
                ],
                "dpi": 36,
            }
        )
    )
    assert [message.type.value for message in messages] == [
        "text",
        "blob",
        "json",
    ]


def test_old_provider_credentials_are_unneeded_and_cannot_expand_policy(
    server,
):
    base, _, calls, _ = server
    legacy = [
        {
            "scheme": "http",
            "host": "attacker.test",
            "port": 80,
            "path_prefix": "/files/",
            "address": "127.0.0.1",
        }
    ]
    tool = PdfTextPagesTool.from_credentials(
        {"allowed_sources": json.dumps(legacy)}
    )
    messages = list(
        tool._invoke(
            {
                "pdf_files": [dify_file(base + "/files/x/file-preview")],
                "dpi": 36,
            }
        )
    )
    assert messages[0].type.value == "text"
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        list(
            tool._invoke(
                {
                    "pdf_files": [
                        dify_file("http://attacker.test/files/x/file-preview")
                    ]
                }
            )
        )
    assert len(calls) == 1
