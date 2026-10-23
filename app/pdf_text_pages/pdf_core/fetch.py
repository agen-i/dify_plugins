"""Only administrator-approved Dify sources; no File.blob or ambient proxies."""

import errno
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit

from pdf_core.config import AllowedSource, Limits
from pdf_core.model import ConversionError


def select_source(
    url: str, sources: tuple[AllowedSource, ...]
) -> tuple[AllowedSource, str]:
    try:
        if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
            raise ValueError
        u = urlsplit(url)
        if u.username is not None or u.password is not None or u.fragment:
            raise ValueError
        path = u.path
        decoded = unquote(path)
        # Deny encoded separators and traversal; do not normalize them.
        if (
            "%" in decoded
            or "\\" in decoded
            or any(seg in (".", "..") for seg in decoded.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in decoded)
            or len(decoded.split("/")) != len(path.split("/"))
        ):
            raise ValueError
        port = (
            u.port
            if u.port is not None
            else (443 if u.scheme == "https" else 80)
        )
        for source in sources:
            if (
                u.scheme == source.scheme
                and u.hostname == source.host
                and port == source.port
                and decoded.startswith(source.path_prefix)
            ):
                if source.download_routes:
                    route = decoded[len(source.path_prefix) :]
                    if not re.fullmatch(
                        r"(?:[A-Za-z0-9_-]+/file-preview|tools/[A-Za-z0-9_-]+(?:\.[A-Za-z0-9]+)?)",
                        route,
                    ):
                        continue
                retrieval = source._target or source
                return retrieval, path + ("?" + u.query if u.query else "")
        raise ValueError
    except Exception:
        raise ConversionError("FETCH_DENIED: source is not approved") from None


_DNS_QUERY = """
import json, socket, sys
try:
    answers = socket.getaddrinfo(sys.argv[1], int(sys.argv[2]), type=socket.SOCK_STREAM)
except socket.gaierror as exc:
    codes = {socket.EAI_NONAME: 21, socket.EAI_AGAIN: 22, socket.EAI_FAIL: 23}
    sys.exit(codes.get(exc.errno, 24))
except OSError:
    sys.exit(24)
print(json.dumps(list(dict.fromkeys(a[4][0] for a in answers))))
"""


def safe_failure(
    code: str, source: AllowedSource, address: str | None = None
) -> ConversionError:
    """Only internal stage codes and coarse categories; no exception text."""
    kind = "unknown"
    if address is not None:
        try:
            ip = ipaddress.ip_address(address)
            kind = (
                "loopback"
                if ip.is_loopback
                else "private" if ip.is_private else "public"
            )
        except ValueError:
            pass
    scheme = source.scheme if source.scheme in ("http", "https") else "unknown"
    return ConversionError(
        f"FETCH_FAILURE: {code}; scheme={scheme}; address_kind={kind}"
    )


def error_suffix(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    known = {
        "ENOENT",
        "EACCES",
        "ECONNREFUSED",
        "ENETUNREACH",
        "EHOSTUNREACH",
        "EADDRNOTAVAIL",
        "ECONNRESET",
        "EPIPE",
        "ETIMEDOUT",
        "EAFNOSUPPORT",
    }
    name = errno.errorcode.get(exc.errno) if isinstance(exc, OSError) else None
    return (
        name
        if name in known
        else "OSERROR" if isinstance(exc, OSError) else "UNKNOWN"
    )


def resolve_addresses(
    source: AllowedSource, deadline: float
) -> tuple[str, ...]:
    """Resolve one trusted-host snapshot in a killable/reaped child.

    The deployment's resolver/network are trust dependencies, not inputs from
    the File. Python's isolated child avoids SDK/gevent DNS monkey-patching.
    """
    stage = "DNS_SOURCE"
    try:
        if source.address is not None:
            return (str(ipaddress.ip_address(source.address)),)
        try:
            return (str(ipaddress.ip_address(source.host)),)
        except ValueError:
            pass
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("resolver", 0)
        stage = "DNS_LAUNCH"
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                _DNS_QUERY,
                source.host,
                str(source.port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=remaining,
            check=True,
        )
        stage = "DNS_RESPONSE"
        addresses = json.loads(result.stdout)
        if not isinstance(addresses, list) or not addresses:
            raise ValueError
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired("resolver", remaining)
        # Validate the complete snapshot before attempting any connection.
        return tuple(
            dict.fromkeys(str(ipaddress.ip_address(a)) for a in addresses)
        )
    except subprocess.TimeoutExpired:
        raise ConversionError("FETCH_TIMEOUT: acquisition deadline") from None
    except subprocess.CalledProcessError as exc:
        codes = {
            21: "DNS_LOOKUP_EAI_NONAME",
            22: "DNS_LOOKUP_EAI_AGAIN",
            23: "DNS_LOOKUP_EAI_FAIL",
            24: "DNS_LOOKUP_OTHER",
        }
        code = codes.get(exc.returncode)
        if code is None:
            value = exc.returncode
            if type(value) is int and 1 <= value <= 255:
                code = f"DNS_CHILD_EXIT_{value}"
            elif type(value) is int and -64 <= value <= -1:
                code = f"DNS_CHILD_SIGNAL_{-value}"
            else:
                code = "DNS_CHILD_OTHER"
        raise safe_failure(code, source) from None
    except Exception as exc:
        code = (
            stage + "_" + error_suffix(exc) if stage == "DNS_LAUNCH" else stage
        )
        raise safe_failure(code, source) from None


def resolve_address(source: AllowedSource, deadline: float) -> str:
    """Compatibility helper; fetch retains every IP in the single snapshot."""
    return resolve_addresses(source, deadline)[0]


def connect_snapshot(
    source: AllowedSource, addresses: tuple[str, ...], deadline: float
) -> tuple[socket.socket, str]:
    """Retry only failed connects in this snapshot, never another origin/DNS."""
    code, last_address = "CONNECT_UNKNOWN", None
    for address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
        sock = None
        try:
            family = (
                socket.AF_INET6
                if ipaddress.ip_address(address).version == 6
                else socket.AF_INET
            )
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(max(0.001, min(2.0, remaining)))
            sock.connect((address, source.port))
            return sock, address
        except Exception as exc:
            code, last_address = "CONNECT_" + error_suffix(exc), address
            if sock is not None:
                sock.close()
    if time.monotonic() >= deadline:
        raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
    raise safe_failure(code, source, last_address)


def verify_peer(sock: socket.socket, address: str, port: int) -> None:
    peer = sock.getpeername()
    if (
        ipaddress.ip_address(peer[0]) != ipaddress.ip_address(address)
        or peer[1] != port
    ):
        raise ConversionError("FETCH_DENIED: connected peer is not approved")


class DeadlineReader(io.RawIOBase):
    def __init__(self, sock: socket.socket, deadline: float, release) -> None:
        self.sock, self.deadline, self.release = sock, deadline, release

    def close(self) -> None:
        if not self.closed:
            self.release()
        super().close()

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
        self.sock.settimeout(max(0.001, min(2.0, remaining)))
        return self.sock.recv_into(buffer)


class DeadlineSocket:
    """HTTP headers and body both use a cumulative deadline, including slow drip."""

    def __init__(self, sock: socket.socket, deadline: float) -> None:
        self.sock, self.deadline = sock, deadline
        self.readers, self.closing = 0, False

    def release(self) -> None:
        self.readers -= 1
        if self.closing and self.readers == 0:
            self.sock.close()

    def makefile(self, mode: str) -> io.BufferedReader:
        self.readers += 1
        return io.BufferedReader(
            DeadlineReader(self.sock, self.deadline, self.release)
        )

    def sendall(self, data: bytes) -> None:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
        self.sock.settimeout(max(0.001, min(2.0, remaining)))
        self.sock.sendall(data)

    def close(self) -> None:
        self.closing = True
        if self.readers == 0:
            self.sock.close()


def fetch(
    url: str,
    sources: tuple[AllowedSource, ...],
    limits: Limits,
    remaining_bytes: int,
    deadline: float,
) -> bytes:
    source, target = select_source(url, sources)
    end = min(deadline, time.monotonic() + limits.fetch_seconds)
    conn: http.client.HTTPConnection | None = None
    sock: socket.socket | None = None
    response: http.client.HTTPResponse | None = None
    stage, address = "DNS", None
    try:
        addresses = resolve_addresses(source, end)
        if time.monotonic() >= end:
            raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
        timeout = max(0.001, min(2.0, end - time.monotonic()))
        stage = "CONNECT"
        sock, address = connect_snapshot(source, addresses, end)
        stage = "PEER_CHECK"
        verify_peer(sock, address, source.port)
        if source.scheme == "https":
            stage = "TLS_INIT"
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
            sock.settimeout(max(0.001, min(2.0, remaining)))
            context = ssl.create_default_context()
            stage = "TLS_HANDSHAKE"
            sock = context.wrap_socket(sock, server_hostname=source.host)
            stage = "PEER_CHECK"
            verify_peer(sock, address, source.port)
        stage = "HTTP_SEND"
        conn = http.client.HTTPConnection(
            source.host, source.port, timeout=timeout
        )
        conn.sock = DeadlineSocket(sock, end)
        conn.request(
            "GET",
            target,
            headers={"Accept": "application/pdf", "Connection": "close"},
        )
        stage = "HTTP_RESPONSE"
        response = conn.getresponse()
        if response.status != 200:  # Redirects never followed.
            raise ConversionError("FETCH_HTTP: expected status 200")
        stage = "HTTP_BODY"
        cap = min(limits.input_file_bytes, remaining_bytes)
        chunks = bytearray()
        while True:
            if time.monotonic() >= end:
                raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
            sock.settimeout(max(0.001, min(2.0, end - time.monotonic())))
            chunk = response.read1(min(65536, cap + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
            if len(chunks) > cap:
                raise ConversionError("LIMIT: input bytes")
        if time.monotonic() >= end:
            raise ConversionError("FETCH_TIMEOUT: acquisition deadline")
        return bytes(chunks)
    except ConversionError:
        raise
    except Exception as exc:
        code = (
            "TLS_VERIFY"
            if isinstance(exc, ssl.SSLCertVerificationError)
            else stage
        )
        raise safe_failure(code, source, address) from None
    finally:
        if response is not None:
            response.close()
        if conn is not None:
            conn.close()
        elif sock is not None:
            sock.close()
