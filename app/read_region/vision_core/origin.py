"""Recover only an origin from the platform's authenticated upload-grant RPC.

The upload metadata request does not upload/create a file. The grant URL and its
credentials are discarded; only the platform-provided scheme/host/port survive.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from vision_core.fetch import Origin, native_origin
from vision_core.images import ImageFailure


def native_origin_from_session(session: Any) -> Origin:
    iterator = None
    try:
        from gevent import Timeout
        from dify_plugin.core.entities.invocation import InvokeType

        with Timeout(8, ImageFailure("NATIVE_ORIGIN_TIMEOUT")):
            iterator = session.file._backwards_invoke(
                InvokeType.UploadFile,
                dict,
                {
                    "filename": "read_region_native_origin.png",
                    "mimetype": "image/png",
                },
            )
            response = next(iterator)
            if (
                type(response) is not dict
                or len(json.dumps(response, ensure_ascii=False).encode())
                > 4096
            ):
                raise ImageFailure("NATIVE_ORIGIN_UNAVAILABLE")
            url = response.get("url")
            if not isinstance(url, str) or not 1 <= len(url) <= 2048:
                raise ImageFailure("NATIVE_ORIGIN_UNAVAILABLE")
            parsed = urlsplit(url)
            if parsed.fragment or parsed.username or parsed.password:
                raise ImageFailure("NATIVE_ORIGIN_UNAVAILABLE")
            return native_origin(
                urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
            )
    except ImageFailure:
        raise
    except Exception:
        raise ImageFailure("NATIVE_ORIGIN_UNAVAILABLE") from None
    finally:
        if iterator is not None:
            try:
                with Timeout(1, False):
                    iterator.close()
            except Exception:
                pass
