"""Stage-only diagnostics and one trusted DNS snapshot, including SDK gevent."""

# ruff: noqa: I001 - SDK side effects must precede stdlib network imports here.

import dify_plugin  # noqa: F401 - exercise the SDK's first-import monkey patch

import errno
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import gevent
from gevent import monkey
import pytest
import pdf_core.fetch as module
from pdf_core.config import AllowedSource, Limits
from pdf_core.model import ConversionError

SOURCE = AllowedSource("http", "approved.test", 80, "/files/")


@pytest.fixture
def listener():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(self.headers["Host"])
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


def test_unreachable_first_ip_uses_only_same_snapshot_next_ip(
    listener, monkeypatch
):
    port, calls = listener
    lookups = []

    def resolve(*args, **kwargs):
        lookups.append(1)
        return SimpleNamespace(stdout=b'["::1", "127.0.0.1"]')

    monkeypatch.setattr(module.subprocess, "run", resolve)
    source = AllowedSource("http", "approved.test", port, "/files/")
    result = module.fetch(
        f"http://approved.test:{port}/files/x?sign=HIDDEN",
        (source,),
        Limits(),
        1000,
        time.monotonic() + 2,
    )
    assert result == b"%PDF-synthetic"
    assert len(lookups) == 1 and calls == [f"approved.test:{port}"]


@pytest.mark.parametrize(
    "failure,expected",
    [
        (FileNotFoundError(errno.ENOENT, "HIDDEN"), "DNS_LAUNCH_ENOENT"),
        (PermissionError(errno.EACCES, "HIDDEN"), "DNS_LAUNCH_EACCES"),
        (
            subprocess.CalledProcessError(21, ["HIDDEN"]),
            "DNS_LOOKUP_EAI_NONAME",
        ),
        (
            subprocess.CalledProcessError(22, ["HIDDEN"]),
            "DNS_LOOKUP_EAI_AGAIN",
        ),
        (subprocess.CalledProcessError(23, ["HIDDEN"]), "DNS_LOOKUP_EAI_FAIL"),
        (subprocess.CalledProcessError(24, ["HIDDEN"]), "DNS_LOOKUP_OTHER"),
        (subprocess.CalledProcessError(1, ["HIDDEN"]), "DNS_CHILD_EXIT_1"),
        (subprocess.CalledProcessError(-9, ["HIDDEN"]), "DNS_CHILD_SIGNAL_9"),
        (SimpleNamespace(stdout=b"HIDDEN"), "DNS_RESPONSE"),
        (SimpleNamespace(stdout=b"[]"), "DNS_RESPONSE"),
    ],
)
def test_dns_failures_are_distinct_and_sanitized(
    monkeypatch, failure, expected
):
    def run(*args, **kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(ConversionError) as caught:
        module.resolve_address(SOURCE, time.monotonic() + 1)
    assert expected in str(caught.value)
    assert "HIDDEN" not in str(caught.value) and "approved.test" not in str(
        caught.value
    )


def test_sdk_gevent_greenlet_launches_real_isolated_dns_child():
    assert monkey.is_module_patched("subprocess")
    assert monkey.is_module_patched("socket")
    source = AllowedSource("http", "localhost", 80, "/files/")
    addresses = gevent.spawn(
        module.resolve_addresses, source, time.monotonic() + 2
    ).get(timeout=3)
    assert addresses and all(
        address in ("::1", "127.0.0.1") for address in addresses
    )


def test_real_missing_executable_in_sdk_greenlet_is_launch_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        module.sys, "executable", "/nonexistent-pdf-resolver-python"
    )

    def lookup():
        try:
            module.resolve_address(SOURCE, time.monotonic() + 1)
        except ConversionError as exc:
            return str(exc)

    message = gevent.spawn(lookup).get(timeout=2)
    assert "DNS_LAUNCH_ENOENT" in message


@pytest.mark.parametrize(
    "stage,failure,expected",
    [
        (
            "connect",
            ConnectionRefusedError(errno.ECONNREFUSED, "HIDDEN"),
            "CONNECT_ECONNREFUSED",
        ),
        ("peer", OSError("HIDDEN"), "PEER_CHECK"),
        ("tls", ssl.SSLCertVerificationError("HIDDEN"), "TLS_VERIFY"),
        ("response", ValueError("HIDDEN"), "HTTP_RESPONSE"),
        ("send", OSError(errno.EPIPE, "HIDDEN"), "HTTP_SEND"),
        ("body", OSError(errno.ECONNRESET, "HIDDEN"), "HTTP_BODY"),
    ],
)
def test_fetch_stage_errors_never_expose_original(
    monkeypatch, stage, failure, expected
):
    class FakeSocket:
        def settimeout(self, *args):
            pass

        def connect(self, *args):
            if stage == "connect":
                raise failure

        def getpeername(self):
            if stage == "peer":
                raise failure
            return "127.0.0.1", 80

        def close(self):
            pass

    class FakeConnection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            if stage == "send":
                raise failure

        def getresponse(self):
            if stage == "body":
                return FakeResponse()
            raise failure

        def close(self):
            pass

    class FakeTLS:
        def wrap_socket(self, *args, **kwargs):
            raise failure

    class FakeResponse:
        status = 200

        def read1(self, *args):
            raise failure

        def close(self):
            pass

    sockets = []

    def create(*args):
        sock = FakeSocket()
        sockets.append(sock)
        return sock

    monkeypatch.setattr(module.socket, "socket", create)
    monkeypatch.setattr(
        module, "resolve_addresses", lambda *args: ("127.0.0.1", "127.0.0.2")
    )
    monkeypatch.setattr(module.http.client, "HTTPConnection", FakeConnection)
    monkeypatch.setattr(
        module.ssl, "create_default_context", lambda: FakeTLS()
    )
    scheme = "https" if stage == "tls" else "http"
    source = AllowedSource(scheme, "approved.test", 80, "/files/", "127.0.0.1")
    with pytest.raises(ConversionError) as caught:
        module.fetch(
            scheme + "://approved.test:80/files/x?sign=HIDDEN",
            (source,),
            Limits(),
            1000,
            time.monotonic() + 1,
        )
    assert expected in str(caught.value)
    assert "HIDDEN" not in str(caught.value) and "approved.test" not in str(
        caught.value
    )
    assert "127.0.0.1" not in str(caught.value)

    assert len(sockets) == (2 if stage == "connect" else 1)


def test_snapshot_retries_do_not_extend_deadline(monkeypatch):
    sockets, closed = [], []

    class SlowRefused:
        def settimeout(self, *args):
            pass

        def connect(self, *args):
            time.sleep(0.04)
            raise ConnectionRefusedError(errno.ECONNREFUSED, "HIDDEN")

        def close(self):
            closed.append(1)

    def create(*args):
        sockets.append(1)
        return SlowRefused()

    monkeypatch.setattr(module.socket, "socket", create)
    with pytest.raises(ConversionError, match="FETCH_TIMEOUT"):
        module.connect_snapshot(
            SOURCE, ("::1", "127.0.0.1"), time.monotonic() + 0.02
        )
    assert len(sockets) == len(closed) == 1


def test_invalid_snapshot_is_rejected_before_connection(monkeypatch):
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=b'["127.0.0.1", "HIDDEN"]'
        ),
    )
    with pytest.raises(ConversionError, match="DNS_RESPONSE") as caught:
        module.resolve_addresses(SOURCE, time.monotonic() + 1)
    assert "HIDDEN" not in str(caught.value)
