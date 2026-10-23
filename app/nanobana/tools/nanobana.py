import base64
import mimetypes
import uuid
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from internal.auth import (
    make_genai_client,
    resolve_auth_config,
    sanitize_error_message,
)

DEFAULT_MODEL = "gemini-3-pro-image"
SUPPORTED_MODELS = ("gemini-3-pro-image", "gemini-3.1-flash-image")
SUPPORTED_ASPECT_RATIOS = (
    "1:1",
    "3:2",
    "2:3",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
)
SUPPORTED_IMAGE_SIZES = ("1K", "2K", "4K")
MAX_INPUT_IMAGES = 14
MAX_OUTPUT_IMAGES = 1


@dataclass(frozen=True)
class GeneratedImage:
    blob: bytes
    mime_type: str


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_model(value: Any) -> str:
    model = _clean_string(value) or DEFAULT_MODEL
    if model not in SUPPORTED_MODELS:
        return DEFAULT_MODEL
    return model


def normalize_aspect_ratio(value: Any) -> str:
    aspect_ratio = _clean_string(value) or "1:1"
    if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
        return "1:1"
    return aspect_ratio


def normalize_resolution(value: Any) -> str:
    image_size = _clean_string(value) or "1K"
    if image_size not in SUPPORTED_IMAGE_SIZES:
        return "1K"
    return image_size


def normalize_images(value: Any) -> list[Any]:
    if _is_empty_image_placeholder(value):
        return []
    if isinstance(value, list):
        return [
            item for item in value if not _is_empty_image_placeholder(item)
        ]
    return [value]


def _is_empty_image_placeholder(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _value(source: Any, *names: str) -> Any:
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        if hasattr(source, name):
            return getattr(source, name)
    return None


def _iter_candidates(response: Any) -> Iterable[Any]:
    candidates = _value(response, "candidates") or []
    if isinstance(candidates, Iterable) and not isinstance(
        candidates, str | bytes
    ):
        return candidates
    return []


def _iter_parts(candidate: Any) -> Iterable[Any]:
    content = _value(candidate, "content") or {}
    parts = _value(content, "parts") or []
    if isinstance(parts, Iterable) and not isinstance(parts, str | bytes):
        return parts
    return []


def _decode_inline_data(data: Any) -> bytes | None:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str) and data:
        return base64.b64decode(data)
    return None


def extract_generated_content(
    response: Any,
) -> tuple[list[str], list[GeneratedImage]]:
    texts: list[str] = []
    images: list[GeneratedImage] = []

    for candidate in _iter_candidates(response):
        for part in _iter_parts(candidate):
            if _value(part, "thought") is True:
                continue

            text = _value(part, "text")
            if text:
                texts.append(str(text))

            inline_data = _value(part, "inline_data", "inlineData")
            if not inline_data:
                continue

            data = _value(inline_data, "data")
            blob = _decode_inline_data(data)
            if not blob:
                continue

            mime_type = (
                _value(inline_data, "mime_type", "mimeType") or "image/png"
            )
            images.append(GeneratedImage(blob=blob, mime_type=str(mime_type)))

    return texts, images[-MAX_OUTPUT_IMAGES:]


def _build_generate_config(aspect_ratio: str, image_size: str) -> Any:
    from google.genai import types

    return types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(
            image_size=image_size,
            aspect_ratio=aspect_ratio,
        ),
    )


def build_contents(prompt: str, images: list[Any]) -> list[Any]:
    if len(images) > MAX_INPUT_IMAGES:
        raise ValueError(
            f"At most {MAX_INPUT_IMAGES} input images are supported."
        )

    contents: list[Any] = [prompt]
    if not images:
        return contents

    from google.genai import types

    for image in images:
        blob = _value(image, "blob")
        mime_type = _value(image, "mime_type", "mimeType")
        if not isinstance(blob, bytes) or not mime_type:
            raise ValueError(
                "Each image file must include blob bytes and mime_type."
            )
        contents.append(
            types.Part.from_bytes(data=blob, mime_type=str(mime_type))
        )
    return contents


def _image_filename(mime_type: str) -> str:
    extension_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    extension = (
        extension_map.get(mime_type)
        or mimetypes.guess_extension(mime_type)
        or ".bin"
    )
    # Use timezone.utc so repo-level Python 3.10 import checks keep working.
    timestamp = datetime.now(timezone.utc).strftime(  # noqa: UP017
        "%Y%m%d_%H%M%S"
    )
    unique_suffix = uuid.uuid4().hex[:8]
    return f"gemini_image_{timestamp}_{unique_suffix}{extension}"


class NanobanaTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        credentials = self.runtime.credentials or {}
        prompt = _clean_string(tool_parameters.get("prompt"))
        if not prompt:
            yield self.create_text_message("Please input prompt.")
            return

        model = normalize_model(tool_parameters.get("model"))
        aspect_ratio = normalize_aspect_ratio(
            tool_parameters.get("aspect_ratio")
        )
        image_size = normalize_resolution(tool_parameters.get("resolution"))
        images = normalize_images(tool_parameters.get("images"))
        try:
            contents = build_contents(prompt, images)
        except Exception as exc:
            message = sanitize_error_message(exc, credentials)
            yield self.create_text_message(
                f"Invalid nanobana image input: {message}"
            )
            return

        try:
            auth_config = resolve_auth_config(credentials)
            client = make_genai_client(auth_config)
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=_build_generate_config(aspect_ratio, image_size),
                )
            finally:
                try:
                    client.close()
                except Exception:
                    pass
            texts, images = extract_generated_content(response)
        except Exception as exc:
            message = sanitize_error_message(exc, credentials)
            yield self.create_text_message(
                f"Gemini image generation failed: {message}"
            )
            return

        for text in texts:
            yield self.create_text_message(text)

        for image in images:
            yield self.create_blob_message(
                blob=image.blob,
                meta={
                    "mime_type": image.mime_type,
                    "filename": _image_filename(image.mime_type),
                },
            )

        if not texts and not images:
            yield self.create_text_message(
                "Gemini returned no text or image candidates."
            )
