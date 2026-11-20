import base64
from dataclasses import replace
from urllib.parse import urlencode

import pytest

from vision_core.fetch import Origin, download, native_origin, preview_path
from vision_core.images import ImageFailure, Limits

ORIGIN = Origin("http", "native.example.invalid", 5001)
PATH = "/files/01234567-89ab-cdef-0123-456789abcdef/file-preview"
QUERY = {
    "timestamp": "1795158618",
    "nonce": "a" * 32,
    "sign": base64.urlsafe_b64encode(b"x" * 32).decode(),
}
URL = "http://native.example.invalid:5001" + PATH + "?" + urlencode(QUERY)


def test_only_native_process_origin_and_exact_signed_route():
    assert native_origin("http://native.example.invalid:5001") == ORIGIN
    assert preview_path(URL, ORIGIN) == PATH + "?" + urlencode(QUERY)
    with pytest.raises(ImageFailure, match="UNSUPPORTED_NATIVE_FILE_CONTEXT"):
        native_origin(None)


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example.invalid:5001" + PATH + "?" + urlencode(QUERY),
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "http://user:pass@native.example.invalid:5001"
        + PATH
        + "?"
        + urlencode(QUERY),
        URL + "#fragment",
        URL + "&extra=1",
        URL + "&nonce=" + "a" * 32,
        URL.replace("file-preview", "image-preview"),
        URL.replace("/files/", "/files/%2e%2e/"),
        URL.replace("timestamp=1795158618", "timestamp=invalid"),
        URL.replace("nonce=" + "a" * 32, "nonce=bad"),
        URL.replace("sign=", "sign=bad"),
    ],
)
def test_arbitrary_or_forged_route_rejected(url):
    with pytest.raises(ImageFailure, match="INVALID_NATIVE_FILE"):
        preview_path(url, ORIGIN)


def install_response(monkeypatch, status, data, length=None):
    import vision_core.fetch as fetch

    seen = []

    class Response:
        def __init__(self):
            self.status = status
            self.offset = 0

        def getheader(self, name):
            return length

        def read1(self, n):
            out = data[self.offset : self.offset + n]
            self.offset += len(out)
            return out

    class Connection:
        sock = None

        def __init__(self, *args, **kwargs):
            seen.append((args, kwargs))

        def request(self, *args, **kwargs):
            seen.append((args, kwargs))

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(fetch.http.client, "HTTPConnection", Connection)
    return seen


def test_redirect_and_expired_signed_capability_never_followed(monkeypatch):
    seen = install_response(monkeypatch, 302, b"private body")
    with pytest.raises(ImageFailure, match="FILE_NOT_AVAILABLE"):
        download(URL, ORIGIN)
    assert len(seen) == 2
    install_response(monkeypatch, 404, b"private body")
    with pytest.raises(ImageFailure, match="FILE_NOT_AVAILABLE"):
        download(URL, ORIGIN)


def test_streaming_download_caps_input_and_returns_no_secret(monkeypatch):
    seen = install_response(monkeypatch, 200, b"x" * 33)
    with pytest.raises(ImageFailure) as exc:
        download(URL, ORIGIN, replace(Limits(), input_bytes=32))
    assert str(exc.value) == "INPUT_LIMIT_EXCEEDED" and URL not in str(
        exc.value
    )
    install_response(monkeypatch, 200, b"PNG")
    assert download(URL, ORIGIN) == b"PNG"
    assert seen[1][1]["headers"] == {"Accept-Encoding": "identity"}


def test_length_limit_checked_before_body(monkeypatch):
    install_response(monkeypatch, 200, b"", str(16 * 1024 * 1024))
    with pytest.raises(ImageFailure, match="INPUT_LIMIT_EXCEEDED"):
        download(URL, ORIGIN)
