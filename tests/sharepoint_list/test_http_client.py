"""Tests for http_client module."""

from __future__ import annotations

import json
import socket

import pytest
import requests

from app.sharepoint_list.internal import http_client
from app.sharepoint_list.internal.request_builders import RequestSpec
from tests.sharepoint_list._stub_http_server import StubResponse, StubServer


def _make_spec(
    base_url: str,
    path: str = "/",
    method: str = "GET",
    params: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
) -> RequestSpec:
    url = f"{base_url}{path}"
    return RequestSpec(
        method=method, url=url, params=params or {}, json=json_body
    )


@pytest.fixture
def stub_server() -> StubServer:
    server = StubServer()
    server.start()
    yield server
    server.stop()


def _find_unused_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class TestGraphAPIError:
    def test_base_exception_attributes(self) -> None:
        exc = http_client.GraphAPIError(
            "test message", status_code=400, response_text="error"
        )
        assert str(exc) == "test message"
        assert exc.status_code == 400
        assert exc.response_text == "error"


class TestRateLimitError:
    def test_retry_after_attribute(self) -> None:
        exc = http_client.RateLimitError(
            "rate limited", retry_after=60, status_code=429
        )
        assert exc.retry_after == 60
        assert exc.status_code == 429


class TestParseRetryAfter:
    def test_parse_integer_value(self) -> None:
        resp = requests.Response()
        resp.headers["Retry-After"] = "120"
        assert http_client.parse_retry_after(resp) == 120

    def test_parse_missing_header(self) -> None:
        resp = requests.Response()
        assert http_client.parse_retry_after(resp) is None

    def test_parse_invalid_value(self) -> None:
        resp = requests.Response()
        resp.headers["Retry-After"] = "invalid"
        assert http_client.parse_retry_after(resp) is None

    def test_parse_http_date_value(self) -> None:
        resp = requests.Response()
        resp.headers["Retry-After"] = "Wed, 21 Oct 2015 07:28:00 GMT"
        assert http_client.parse_retry_after(resp) is None


class TestIsRetryableException:
    def test_transient_error_is_retryable(self) -> None:
        exc = http_client.TransientError("test")
        assert http_client.is_retryable_exception(exc) is True

    def test_rate_limit_error_is_retryable(self) -> None:
        exc = http_client.RateLimitError("test")
        assert http_client.is_retryable_exception(exc) is True

    def test_authentication_error_is_not_retryable(self) -> None:
        exc = http_client.AuthenticationError("test")
        assert http_client.is_retryable_exception(exc) is False

    def test_authorization_error_is_not_retryable(self) -> None:
        exc = http_client.AuthorizationError("test")
        assert http_client.is_retryable_exception(exc) is False

    def test_timeout_is_retryable(self) -> None:
        exc = requests.exceptions.Timeout()
        assert http_client.is_retryable_exception(exc) is True

    def test_connection_error_is_retryable(self) -> None:
        exc = requests.exceptions.ConnectionError()
        assert http_client.is_retryable_exception(exc) is True


class TestCalculateBackoffWait:
    def test_exponential_backoff(self) -> None:
        config = http_client.RetryConfig(
            min_wait_seconds=1.0,
            max_wait_seconds=10.0,
            exponential_base=2.0,
            jitter=False,
        )
        assert http_client.calculate_backoff_wait(0, config) == 1.0
        assert http_client.calculate_backoff_wait(1, config) == 2.0
        assert http_client.calculate_backoff_wait(2, config) == 4.0
        assert http_client.calculate_backoff_wait(3, config) == 8.0
        assert http_client.calculate_backoff_wait(4, config) == 10.0

    def test_retry_after_overrides_backoff(self) -> None:
        config = http_client.RetryConfig(
            min_wait_seconds=1.0,
            max_wait_seconds=10.0,
            jitter=False,
        )
        assert (
            http_client.calculate_backoff_wait(0, config, retry_after=30)
            == 30.0
        )

    def test_jitter_adds_randomness(self) -> None:
        config = http_client.RetryConfig(
            min_wait_seconds=1.0,
            max_wait_seconds=10.0,
            jitter=True,
        )
        wait = http_client.calculate_backoff_wait(0, config)
        assert 1.0 <= wait <= 1.25


class TestSendSingleRequest:
    def test_successful_request(self, stub_server: StubServer) -> None:
        stub_server.enqueue(
            StubResponse(
                status=200,
                body={"value": []},
                headers={"Content-Type": "application/json"},
            )
        )
        spec = _make_spec(stub_server.base_url, "/ok")
        result = http_client._send_single_request(spec, "test_token")
        assert result == {"value": []}

    def test_non_json_response_returns_empty_dict(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=200, body="plain text"))
        spec = _make_spec(stub_server.base_url, "/text")
        result = http_client._send_single_request(spec, "test_token")
        assert result == {}

    def test_empty_response_returns_empty_dict(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=204, body=None))
        spec = _make_spec(stub_server.base_url, "/no-content", method="DELETE")
        result = http_client._send_single_request(spec, "test_token")
        assert result == {}

    def test_400_raises_graph_api_error(self, stub_server: StubServer) -> None:
        stub_server.enqueue(StubResponse(status=400, body="Bad Request"))
        spec = _make_spec(stub_server.base_url, "/bad")
        with pytest.raises(http_client.GraphAPIError) as exc_info:
            http_client._send_single_request(spec, "test_token")
        assert exc_info.value.status_code == 400
        assert exc_info.value.response_text == "Bad Request"

    def test_404_raises_graph_api_error(self, stub_server: StubServer) -> None:
        stub_server.enqueue(StubResponse(status=404, body="Not Found"))
        spec = _make_spec(stub_server.base_url, "/missing")
        with pytest.raises(http_client.GraphAPIError) as exc_info:
            http_client._send_single_request(spec, "test_token")
        assert exc_info.value.status_code == 404
        assert exc_info.value.response_text == "Not Found"

    def test_401_raises_authentication_error(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=401, body="Unauthorized"))
        spec = _make_spec(stub_server.base_url, "/unauthorized")
        with pytest.raises(http_client.AuthenticationError) as exc_info:
            http_client._send_single_request(spec, "test_token")
        assert exc_info.value.status_code == 401

    def test_403_raises_authorization_error(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=403, body="Forbidden"))
        spec = _make_spec(stub_server.base_url, "/forbidden")
        with pytest.raises(http_client.AuthorizationError) as exc_info:
            http_client._send_single_request(spec, "test_token")
        assert exc_info.value.status_code == 403

    def test_429_raises_rate_limit_error(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(
            StubResponse(
                status=429,
                body="Too Many Requests",
                headers={"Retry-After": "60"},
            )
        )
        spec = _make_spec(stub_server.base_url, "/rate-limit")
        with pytest.raises(http_client.RateLimitError) as exc_info:
            http_client._send_single_request(spec, "test_token")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 60

    def test_500_raises_transient_error(self, stub_server: StubServer) -> None:
        stub_server.enqueue(StubResponse(status=500, body="Server Error"))
        spec = _make_spec(stub_server.base_url, "/server-error")
        with pytest.raises(http_client.TransientError) as exc_info:
            http_client._send_single_request(spec, "test_token")
        assert exc_info.value.status_code == 500

    def test_authorization_header_is_sent(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=200, body="{}"))
        spec = _make_spec(stub_server.base_url, "/headers")
        http_client._send_single_request(spec, "test_token")
        headers = stub_server.requests[-1]["headers"]
        assert headers.get("Authorization") == "Bearer test_token"

    def test_content_type_added_when_json_present(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=200, body="{}"))
        spec = _make_spec(
            stub_server.base_url, "/json", method="POST", json_body={"x": 1}
        )
        http_client._send_single_request(spec, "test_token")
        headers = stub_server.requests[-1]["headers"]
        assert headers.get("Content-Type") == "application/json"

    def test_extra_headers_are_forwarded(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=200, body="{}"))
        spec = _make_spec(stub_server.base_url, "/extra")
        http_client._send_single_request(
            spec, "test_token", extra_headers={"Prefer": "test"}
        )
        headers = stub_server.requests[-1]["headers"]
        assert headers.get("Prefer") == "test"

    def test_params_and_json_body_are_sent(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=200, body="{}"))
        spec = _make_spec(
            stub_server.base_url,
            "/payload",
            method="POST",
            params={"foo": "bar"},
            json_body={"a": 1, "b": "two"},
        )
        http_client._send_single_request(spec, "test_token")
        request = stub_server.requests[-1]
        assert request["query"].get("foo") == ["bar"]
        body = json.loads(request["body"].decode("utf-8"))
        assert body == {"a": 1, "b": "two"}


class TestSendRequestWithRetry:
    def test_retries_on_transient_error(self, stub_server: StubServer) -> None:
        stub_server.enqueue(StubResponse(status=500, body="Server Error"))
        stub_server.enqueue(StubResponse(status=200, body={"value": []}))
        spec = _make_spec(stub_server.base_url, "/flaky")
        config = http_client.RetryConfig(
            max_attempts=3,
            min_wait_seconds=0,
            max_wait_seconds=0,
            jitter=False,
        )
        result = http_client.send_request_with_retry(
            spec, "test_token", config=config
        )
        assert result == {"value": []}
        assert len(stub_server.requests) == 2

    def test_retries_on_rate_limit_error(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(
            StubResponse(
                status=429,
                body="Too Many Requests",
                headers={"Retry-After": "0"},
            )
        )
        stub_server.enqueue(StubResponse(status=200, body={"value": []}))
        spec = _make_spec(stub_server.base_url, "/rate-limit")
        config = http_client.RetryConfig(
            max_attempts=3,
            min_wait_seconds=0,
            max_wait_seconds=0,
            jitter=False,
        )
        result = http_client.send_request_with_retry(
            spec, "test_token", config=config
        )
        assert result == {"value": []}
        assert len(stub_server.requests) == 2

    def test_does_not_retry_on_authentication_error(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=401, body="Unauthorized"))
        spec = _make_spec(stub_server.base_url, "/unauthorized")
        config = http_client.RetryConfig(max_attempts=3)
        with pytest.raises(http_client.AuthenticationError):
            http_client.send_request_with_retry(
                spec, "test_token", config=config
            )
        assert len(stub_server.requests) == 1

    def test_does_not_retry_on_authorization_error(
        self, stub_server: StubServer
    ) -> None:
        stub_server.enqueue(StubResponse(status=403, body="Forbidden"))
        spec = _make_spec(stub_server.base_url, "/forbidden")
        config = http_client.RetryConfig(max_attempts=3)
        with pytest.raises(http_client.AuthorizationError):
            http_client.send_request_with_retry(
                spec, "test_token", config=config
            )
        assert len(stub_server.requests) == 1

    def test_max_retries_exceeded(self, stub_server: StubServer) -> None:
        stub_server.enqueue(StubResponse(status=500, body="Server Error"))
        stub_server.enqueue(StubResponse(status=500, body="Server Error"))
        stub_server.enqueue(StubResponse(status=500, body="Server Error"))
        spec = _make_spec(stub_server.base_url, "/always-500")
        config = http_client.RetryConfig(
            max_attempts=3,
            min_wait_seconds=0,
            max_wait_seconds=0,
            jitter=False,
        )
        with pytest.raises(http_client.TransientError):
            http_client.send_request_with_retry(
                spec, "test_token", config=config
            )
        assert len(stub_server.requests) == 3

    def test_max_attempts_one_no_retry(self, stub_server: StubServer) -> None:
        stub_server.enqueue(StubResponse(status=500, body="Server Error"))
        spec = _make_spec(stub_server.base_url, "/one-shot")
        config = http_client.RetryConfig(
            max_attempts=1,
            min_wait_seconds=0,
            max_wait_seconds=0,
            jitter=False,
        )
        with pytest.raises(http_client.TransientError):
            http_client.send_request_with_retry(
                spec, "test_token", config=config
            )
        assert len(stub_server.requests) == 1

    def test_retries_on_timeout(self, stub_server: StubServer) -> None:
        stub_server.enqueue(
            StubResponse(status=200, body={"value": []}, delay=0.2)
        )
        stub_server.enqueue(StubResponse(status=200, body={"value": []}))
        spec = _make_spec(stub_server.base_url, "/slow")
        config = http_client.RetryConfig(
            max_attempts=2,
            min_wait_seconds=0,
            max_wait_seconds=0,
            jitter=False,
        )
        result = http_client.send_request_with_retry(
            spec, "test_token", config=config, timeout=0.02
        )
        assert result == {"value": []}
        assert len(stub_server.requests) == 2

    def test_connection_error_wrapped_after_max_retries(self) -> None:
        unused_port = _find_unused_port()
        spec = RequestSpec(
            method="GET", url=f"http://127.0.0.1:{unused_port}/test"
        )
        config = http_client.RetryConfig(
            max_attempts=2,
            min_wait_seconds=0,
            max_wait_seconds=0,
            jitter=False,
        )
        with pytest.raises(http_client.TransientError) as exc_info:
            http_client.send_request_with_retry(
                spec, "test_token", config=config, timeout=0.01
            )
        assert "Network error after 2 attempts" in str(exc_info.value)

    def test_zero_attempts_raises_unexpected_error(self) -> None:
        config = http_client.RetryConfig(
            max_attempts=0,
            min_wait_seconds=0,
            max_wait_seconds=0,
            jitter=False,
        )
        spec = RequestSpec(method="GET", url="http://127.0.0.1:1/test")
        with pytest.raises(http_client.GraphAPIError) as exc_info:
            http_client.send_request_with_retry(
                spec, "test_token", config=config
            )
        assert "Unexpected error in retry loop" in str(exc_info.value)
