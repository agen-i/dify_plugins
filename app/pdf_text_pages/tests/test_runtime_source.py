"""Necessary source-authentication cases reused from prior 0.1.7 evidence."""

import json
from concurrent.futures import ThreadPoolExecutor
import gevent
import pytest
from dify_plugin.config.config import InstallMethod
from dify_plugin.core.entities.plugin.io import (
    PluginInStream,
    PluginInStreamEvent,
)
from dify_plugin.core.runtime import Session
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.file.file import File
from pdf_core.model import ConversionError
from tools.pdf_text_pages import PdfTextPagesTool


class Reader(RequestReader):
    def _read_stream(self):
        yield from ()


class Writer(ResponseWriter):
    def __init__(self, reader, result, delay=0):
        self.reader, self.result, self.delay = (reader, result, delay)
        self.requests = []

    def write(self, data):
        if not data.strip():
            return
        request = json.loads(data)
        self.requests.append(request)
        payload = request["data"]["data"]
        request_id = payload["backwards_request_id"]

        def respond():
            for session_id, identity in (
                ("other", request_id),
                ("session", "wrong"),
                ("session", request_id),
            ):
                self.reader._process_line(
                    PluginInStream(
                        session_id=session_id,
                        event=PluginInStreamEvent.BackwardInvocationResponse,
                        data={
                            "backwards_request_id": identity,
                            "event": (
                                "error"
                                if isinstance(self.result, str)
                                else "response"
                            ),
                            "message": (
                                self.result
                                if isinstance(self.result, str)
                                else "struct"
                            ),
                            "data": (
                                (
                                    {
                                        "url": "http://attacker.test/files/upload/for-plugin"
                                    }
                                    if session_id == "other"
                                    else self.result
                                )
                                if isinstance(self.result, dict)
                                else None
                            ),
                        },
                        reader=self.reader,
                        writer=self,
                    )
                )

        if self.result is not None:
            gevent.spawn_later(self.delay, respond)

    def done(self):
        pass


def make_session(result, method=InstallMethod.Local, delay=0):
    reader = Reader()
    writer = Writer(reader, result, delay)
    session = Session(
        "session", ThreadPoolExecutor(), reader, writer, install_method=method
    )
    return (session, reader, writer)


def input_file(
    url="http://runtime.test/base/files/id/file-preview?sign=INPUT_SECRET",
):
    return File(
        url=url, type="document", filename="input.txt", extension=".txt"
    )


def invoke(session, file):
    tool = PdfTextPagesTool.from_credentials({})
    tool.session = session
    return tool._invoke({"pdf_files": [file]})


def test_no_file_settings_uses_independent_runtime_base_and_unchanged_fetch(
    monkeypatch,
):
    from pdf_core.fetch import select_source

    session, reader, writer = make_session(
        {
            "url": "http://runtime.test/base/files/upload/for-plugin?sign=CONTROL_SECRET"
        }
    )
    file = input_file()
    calls = []

    def acquire(url, sources, limits, remaining, deadline):
        selected, target = select_source(url, sources)
        calls.append((selected.host, target))
        return b"unchanged text"

    monkeypatch.setattr("tools.pdf_text_pages.fetch", acquire)
    messages = list(invoke(session, file))
    assert messages[0].message.text == ""
    assert messages[1].message.blob == b"unchanged text"
    assert messages[-1].message.json_object["documents"] == []
    assert calls == [
        ("runtime.test", "/base/files/id/file-preview?sign=INPUT_SECRET")
    ]
    assert reader.readers == []
    request = writer.requests[0]["data"]["data"]
    assert request["type"] == "upload_file"
    assert request["request"] == {
        "filename": "pdf-text-pages-source-probe.bin",
        "mimetype": "application/octet-stream",
    }
    assert "INPUT_SECRET" not in json.dumps(writer.requests)
    assert len(writer.requests) == 1


def test_bad_input_does_not_start_discovery():
    session, _, writer = make_session(None)
    tool = PdfTextPagesTool.from_credentials({})
    tool.session = session
    with pytest.raises(ConversionError, match="INPUT:"):
        next(tool._invoke({"pdf_files": ["http://attacker.test/file"]}))
    assert writer.requests == []


def test_runtime_source_rejects_foreign_input_before_dns(monkeypatch):
    session, reader, _ = make_session(
        {
            "url": "http://runtime.test/base/files/upload/for-plugin?opaque=control"
        }
    )

    def forbidden(*args):
        pytest.fail("foreign File URL must not reach DNS")

    monkeypatch.setattr("pdf_core.fetch.resolve_addresses", forbidden)
    with pytest.raises(ConversionError, match="FETCH_DENIED"):
        next(
            invoke(
                session,
                input_file("http://foreign.invalid/files/id/file-preview"),
            )
        )
    assert reader.readers == []


def test_runtime_authorized_real_clipboard_png_preserves_bytes_and_query():
    import io
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from PIL import Image

    output = io.BytesIO()
    image = Image.new("RGB", (4, 4), "blue")
    image.save(output, format="PNG")
    image.close()
    png = output.getvalue()
    paths = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            self.wfile.write(png)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    task = gevent.spawn(server.serve_forever)
    origin = f"http://127.0.0.1:{server.server_port}"
    session, reader, writer = make_session(
        {"url": origin + "/files/upload/for-plugin?opaque=control"}
    )
    item = File(
        url=origin + "/files/clipboard/file-preview?opaque=input%2Funchanged",
        type="image",
        filename="clipboard.png",
        extension=".png",
        mime_type="image/png",
        size=len(png),
    )
    try:
        messages = list(invoke(session, item))
    finally:
        server.shutdown()
        task.join()
        server.server_close()
    assert messages[0].message.text == ""
    assert messages[1].message.blob == png
    assert messages[1].meta == {
        "filename": "clipboard.png",
        "mime_type": "image/png",
    }
    assert messages[-1].message.json_object["documents"] == []
    assert paths == ["/files/clipboard/file-preview?opaque=input%2Funchanged"]
    assert len(writer.requests) == 1 and reader.readers == []
