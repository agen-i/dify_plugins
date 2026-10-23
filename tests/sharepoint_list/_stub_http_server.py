from __future__ import annotations

import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class StubResponse:
    def __init__(
        self,
        status: int = 200,
        body: str | bytes | dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        delay: float = 0.0,
    ) -> None:
        self.status = status
        self.body = body
        self.headers = headers or {}
        self.delay = delay


class StubServer:
    def __init__(self) -> None:
        self._responses: queue.Queue[StubResponse] = queue.Queue()
        self.requests: list[dict[str, Any]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url: str | None = None

    def enqueue(self, response: StubResponse) -> None:
        self._responses.put(response)

    def start(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self._handle()

            def do_POST(self) -> None:  # noqa: N802
                self._handle()

            def do_PATCH(self) -> None:  # noqa: N802
                self._handle()

            def do_DELETE(self) -> None:  # noqa: N802
                self._handle()

            def _handle(self) -> None:
                parsed = urlparse(self.path)
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length else b""
                self.server.stub.requests.append(
                    {
                        "method": self.command,
                        "path": parsed.path,
                        "query": parse_qs(parsed.query),
                        "headers": dict(self.headers),
                        "body": body,
                    }
                )

                try:
                    resp = self.server.stub._responses.get_nowait()
                except queue.Empty:
                    resp = StubResponse(status=500, body="No stub response")

                if resp.delay:
                    time.sleep(resp.delay)

                self.send_response(resp.status)
                for key, value in resp.headers.items():
                    self.send_header(key, value)
                self.end_headers()

                if resp.body is None:
                    return
                if isinstance(resp.body, dict):
                    payload = json.dumps(resp.body).encode("utf-8")
                elif isinstance(resp.body, str):
                    payload = resp.body.encode("utf-8")
                else:
                    payload = resp.body
                self.wfile.write(payload)

            def log_message(self, format: str, *args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.stub = self
        host, port = self._server.server_address
        self.base_url = f"http://{host}:{port}"
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=1)
