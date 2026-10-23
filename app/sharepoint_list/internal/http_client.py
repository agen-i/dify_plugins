"""HTTP client with retry logic for Microsoft Graph API.

標準ライブラリのみでリトライロジックを実装。
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import requests

from . import request_builders

logger = logging.getLogger(__name__)


# ============================================================
# カスタム例外クラス
# ============================================================


class GraphAPIError(Exception):
    """Base exception for Graph API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class AuthenticationError(GraphAPIError):
    """401 Unauthorized - token expired or invalid."""

    pass


class AuthorizationError(GraphAPIError):
    """403 Forbidden - insufficient permissions."""

    pass


class RateLimitError(GraphAPIError):
    """429 Too Many Requests - rate limit exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        status_code: int | None = None,
        response_text: str | None = None,
    ):
        super().__init__(message, status_code, response_text)
        self.retry_after = retry_after


class TransientError(GraphAPIError):
    """5xx errors or temporary network issues - safe to retry."""

    pass


# ============================================================
# リトライ設定
# ============================================================


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 10.0
    exponential_base: float = 2.0
    jitter: bool = True  # ランダムなジッターを追加して thundering herd を防ぐ


DEFAULT_RETRY_CONFIG = RetryConfig()


# ============================================================
# リトライ可能かどうかの判定
# ============================================================


def is_retryable_exception(exc: BaseException) -> bool:
    """Determine if an exception is retryable."""
    if isinstance(exc, (TransientError, RateLimitError)):
        return True
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    return False


# ============================================================
# 待機時間計算
# ============================================================


def calculate_backoff_wait(
    attempt: int,
    config: RetryConfig,
    retry_after: int | None = None,
) -> float:
    """
    Calculate wait time with exponential backoff.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
        retry_after: Optional Retry-After header value (seconds)

    Returns:
        Wait time in seconds
    """
    if retry_after is not None and retry_after > 0:
        # Retry-After ヘッダーがあればそれを優先
        wait = float(retry_after)
    else:
        # 指数バックオフ: min_wait * (base ^ attempt)
        wait = config.min_wait_seconds * (config.exponential_base**attempt)
        wait = min(wait, config.max_wait_seconds)

    # ジッターを追加（0-25%のランダムな増加）
    if config.jitter:
        jitter_factor = 1.0 + random.random() * 0.25
        wait = wait * jitter_factor

    return wait


# ============================================================
# Retry-After ヘッダー解析
# ============================================================


def parse_retry_after(response: requests.Response) -> int | None:
    """Parse Retry-After header value."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        # Retry-After can be seconds or HTTP-date
        return int(retry_after)
    except ValueError:
        # HTTP-date format - use default
        return None


# ============================================================
# HTTP リクエスト実行（リトライ付き）
# ============================================================


def send_request_with_retry(
    spec: request_builders.RequestSpec,
    access_token: str,
    extra_headers: dict[str, str] | None = None,
    config: RetryConfig | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Send HTTP request with retry logic.

    Retries on:
    - 429 (Rate Limit) with Retry-After handling
    - 5xx (Server Errors)
    - Connection/Timeout errors

    Does NOT retry on:
    - 401 (Authentication) - raises AuthenticationError
    - 403 (Authorization) - raises AuthorizationError
    - 4xx (Client Errors) - raises GraphAPIError

    Args:
        spec: Request specification
        access_token: OAuth access token
        extra_headers: Additional headers to include
        config: Retry configuration
        timeout: Request timeout in seconds

    Returns:
        Response JSON as dictionary

    Raises:
        AuthenticationError: On 401 response
        AuthorizationError: On 403 response
        RateLimitError: On 429 response after max retries
        TransientError: On 5xx response after max retries
        GraphAPIError: On other 4xx responses
    """
    config = config or DEFAULT_RETRY_CONFIG
    last_exception: Exception | None = None

    for attempt in range(config.max_attempts):
        try:
            return _send_single_request(
                spec, access_token, extra_headers, timeout
            )

        except (TransientError, RateLimitError) as e:
            last_exception = e
            retry_after = getattr(e, "retry_after", None)

            if attempt < config.max_attempts - 1:
                wait_time = calculate_backoff_wait(
                    attempt, config, retry_after
                )
                logger.warning(
                    "Retryable error occurred (attempt %d/%d). "
                    "Waiting %.2f seconds before retry. Error: %s",
                    attempt + 1,
                    config.max_attempts,
                    wait_time,
                    str(e),
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    "Max retry attempts (%d) exceeded. Last error: %s",
                    config.max_attempts,
                    str(e),
                )
                raise

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ) as e:
            last_exception = e

            if attempt < config.max_attempts - 1:
                wait_time = calculate_backoff_wait(attempt, config)
                logger.warning(
                    "Network error occurred (attempt %d/%d). "
                    "Waiting %.2f seconds before retry. Error: %s",
                    attempt + 1,
                    config.max_attempts,
                    wait_time,
                    str(e),
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    "Max retry attempts (%d) exceeded. Last error: %s",
                    config.max_attempts,
                    str(e),
                )
                # ネットワークエラーを TransientError にラップして raise
                raise TransientError(
                    f"Network error after {config.max_attempts} attempts: {e}",
                    status_code=None,
                    response_text=None,
                ) from e

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise GraphAPIError("Unexpected error in retry loop")


def _send_single_request(
    spec: request_builders.RequestSpec,
    access_token: str,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute a single HTTP request without retry."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if spec.json is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    # Let Timeout and ConnectionError propagate for retry handling
    resp = requests.request(
        method=spec.method,
        url=spec.url,
        params=spec.params or None,
        json=spec.json,
        headers=headers,
        timeout=timeout,
    )

    # Handle error responses
    if resp.status_code >= 400:
        _handle_error_response(resp, access_token)

    # Parse successful response
    if resp.text:
        try:
            return resp.json()
        except ValueError:
            return {}
    return {}


def _handle_error_response(resp: requests.Response, access_token: str) -> None:
    """Raise appropriate exception based on status code."""
    status = resp.status_code
    text = resp.text[:500] if resp.text else ""
    token_len = (
        len(access_token) if isinstance(access_token, str) else "non-str"
    )

    base_msg = f"Graph API error {status}: {text[:200]} (access_token_len={token_len})"

    if status == 401:
        raise AuthenticationError(
            "Access token expired or invalid. Please re-authorize.",
            status_code=status,
            response_text=text,
        )

    if status == 403:
        raise AuthorizationError(
            f"Insufficient permissions: {text[:200]}",
            status_code=status,
            response_text=text,
        )

    if status == 429:
        retry_after = parse_retry_after(resp)
        raise RateLimitError(
            f"Rate limit exceeded. Retry after {retry_after or 'unknown'} seconds.",
            retry_after=retry_after,
            status_code=status,
            response_text=text,
        )

    if 500 <= status < 600:
        raise TransientError(
            f"Server error (temporary): {base_msg}",
            status_code=status,
            response_text=text,
        )

    # Other 4xx errors - not retryable
    raise GraphAPIError(base_msg, status_code=status, response_text=text)
