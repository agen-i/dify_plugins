"""Discover Dify's file base over the existing, trusted full-duplex session.

Pinned SDK 0.10.2 has no public signature-request-only method. This small
adapter uses the same backwards invocation as session.file.upload, but never
uploads a body. File input is deliberately absent from this interface.
"""

import time
from contextlib import closing
from copy import copy
from urllib.parse import urlsplit

from dify_plugin.config.config import InstallMethod
from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation, Session
from gevent import Timeout
from pydantic import BaseModel, Field

from pdf_core.config import AllowedSource, Limits, parse_runtime_base
from pdf_core.model import ConversionError


class _SignedUpload(BaseModel):
    url: str = Field(strict=True, min_length=1, max_length=8192)


class _SessionReader:
    """Keep SDK request-id filtering within the invoking session."""

    def __init__(self, session: Session) -> None:
        self.reader, self.session_id = session.reader, session.session_id

    def read(self, predicate):
        return self.reader.read(
            lambda message: message.session_id == self.session_id
            and predicate(message)
        )


def discover_runtime_sources(
    session: Session | None, limits: Limits, deadline: float
) -> tuple[AllowedSource, ...]:
    if (
        session is None
        or not session.session_id
        or session.install_method
        not in (InstallMethod.Local, InstallMethod.Remote)
    ):
        raise ConversionError(
            "CONFIG: SOURCE_UNAVAILABLE: Dify配信元を確認できる実行セッションがありません。"
            "入力URLは自動承認しません。"
        ) from None
    end = min(deadline, time.monotonic() + limits.fetch_seconds)
    remaining = end - time.monotonic()
    if remaining <= 0:
        raise ConversionError(
            "FETCH_TIMEOUT: source discovery deadline"
        ) from None
    invocation_session = copy(session)
    invocation_session.reader = _SessionReader(session)
    try:
        # Only the existing session transport is allowed: never the SDK's HTTP
        # backwards path and never a URL, tenant or user supplied by a File.
        with (
            Timeout(remaining),
            closing(
                BackwardsInvocation(invocation_session)._backwards_invoke(
                    InvokeType.UploadFile,
                    _SignedUpload,
                    {
                        "filename": "pdf-text-pages-source-probe.bin",
                        "mimetype": "application/octet-stream",
                    },
                )
            ) as response,
        ):
            signed = next(response)
    except Timeout:
        raise ConversionError(
            "FETCH_TIMEOUT: source discovery deadline"
        ) from None
    except Exception:
        raise ConversionError(
            "CONFIG: SOURCE_LOOKUP_FAILED: Dify実行基盤から配信元を確認できません。"
            "入力URLは自動承認しません。"
        ) from None
    if time.monotonic() >= end:
        raise ConversionError(
            "FETCH_TIMEOUT: source discovery deadline"
        ) from None
    try:
        # Dify 1.18.0 binds this fixed upload URI to the very same internal file
        # base used by File.to_plugin_parameter. Discard the signing query; the
        # incoming download path/query are left entirely to the existing fetch.
        parsed = urlsplit(signed.url)
        suffix = "/files/upload/for-plugin"
        if parsed.fragment or not parsed.path.endswith(suffix):
            raise ValueError
        absolute = signed.url.split("?", 1)[0]
        base = absolute[: -len(suffix)]
        return (parse_runtime_base(base, "Dify runtime file source"),)
    except Exception:
        raise ConversionError(
            "CONFIG: SOURCE_INVALID: Dify実行基盤の配信元応答が不適合です。"
            "入力URLは自動承認しません。"
        ) from None
