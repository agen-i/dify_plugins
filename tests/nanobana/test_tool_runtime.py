from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest


def _install_google_type_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    types_mod = types.ModuleType("google.genai.types")

    class ImageConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class GenerateContentConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class Part:
        @staticmethod
        def from_bytes(data: bytes, mime_type: str) -> SimpleNamespace:
            return SimpleNamespace(data=data, mime_type=mime_type)

    types_mod.ImageConfig = ImageConfig
    types_mod.GenerateContentConfig = GenerateContentConfig
    types_mod.Part = Part
    genai_mod.types = types_mod
    google_mod.genai = genai_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)


class FakeModels:
    def __init__(
        self, response: Any, generate_error: Exception | None = None
    ) -> None:
        self.response = response
        self.generate_error = generate_error
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.generate_error is not None:
            raise self.generate_error
        return self.response


class FakeClient:
    def __init__(
        self, response: Any, generate_error: Exception | None = None
    ) -> None:
        self.models = FakeModels(response, generate_error)
        self.closed = False
        self.close_calls = 0

    def close(self) -> None:
        self.closed = True
        self.close_calls += 1


def _tool(module: Any, credentials: dict[str, Any]) -> Any:
    tool = module.NanobanaTool()
    tool.runtime = SimpleNamespace(credentials=credentials)
    return tool


def test_invoke_returns_text_and_blob(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(text="generated caption"),
                        SimpleNamespace(
                            inline_data=SimpleNamespace(
                                data=b"image-bytes", mime_type="image/png"
                            )
                        ),
                    ]
                )
            )
        ]
    )
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    messages = list(
        _tool(module, {"vertex_project_id": "project-a"})._invoke(
            {
                "prompt": "draw a small banana",
                "model": "gemini-3-pro-image",
                "aspect_ratio": "16:9",
                "resolution": "2K",
            }
        )
    )

    assert messages[0] == {"type": "text", "text": "generated caption"}
    assert messages[1]["type"] == "blob"
    assert messages[1]["blob"] == b"image-bytes"
    assert messages[1]["meta"]["mime_type"] == "image/png"
    call = fake_client.models.calls[0]
    assert call["model"] == "gemini-3-pro-image"
    assert call["contents"] == ["draw a small banana"]
    assert call["config"].response_modalities == ["TEXT", "IMAGE"]
    assert call["config"].image_config.aspect_ratio == "16:9"
    assert call["config"].image_config.image_size == "2K"


def test_invoke_returns_only_last_generated_image(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "data": b"first-image",
                                "mimeType": "image/png",
                            }
                        },
                        {
                            "inlineData": {
                                "data": b"second-image",
                                "mimeType": "image/png",
                            }
                        },
                    ]
                }
            }
        ]
    }
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    messages = list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {"prompt": "draw a small banana"}
        )
    )

    blob_messages = [
        message for message in messages if message["type"] == "blob"
    ]
    assert len(blob_messages) == 1
    assert blob_messages[0]["blob"] == b"second-image"


def test_invoke_skips_thought_parts_before_emitting_outputs(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "internal reasoning", "thought": True},
                        {
                            "inlineData": {
                                "data": b"thought-image",
                                "mimeType": "image/png",
                            },
                            "thought": True,
                        },
                        {"text": "final caption"},
                    ]
                }
            }
        ]
    }
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    messages = list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {"prompt": "draw a small banana"}
        )
    )

    assert messages == [{"type": "text", "text": "final caption"}]


def test_invoke_closes_client_after_successful_generate_content(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {"prompt": "draw a small banana"}
        )
    )

    assert fake_client.closed is True
    assert fake_client.close_calls == 1


def test_invoke_closes_client_after_generate_content_raises(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    fake_client = FakeClient(
        SimpleNamespace(candidates=[]),
        generate_error=RuntimeError("generation failed"),
    )
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    messages = list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {"prompt": "draw a small banana"}
        )
    )

    assert fake_client.closed is True
    assert fake_client.close_calls == 1
    assert messages[0]["type"] == "text"
    assert "Gemini image generation failed" in messages[0]["text"]


def test_invoke_adds_single_image_part(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )
    input_image = SimpleNamespace(blob=b"input-png", mime_type="image/png")

    list(
        _tool(module, {"vertex_project_id": "project-a"})._invoke(
            {
                "prompt": "edit this image",
                "images": input_image,
            }
        )
    )

    contents = fake_client.models.calls[0]["contents"]
    assert contents[0] == "edit this image"
    assert contents[1].data == b"input-png"
    assert contents[1].mime_type == "image/png"


def test_invoke_adds_multiple_image_parts(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )
    images = [
        SimpleNamespace(blob=b"input-png", mime_type="image/png"),
        SimpleNamespace(blob=b"input-webp", mime_type="image/webp"),
    ]

    list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {
                "prompt": "combine references",
                "images": images,
            }
        )
    )

    contents = fake_client.models.calls[0]["contents"]
    assert [item.mime_type for item in contents[1:]] == [
        "image/png",
        "image/webp",
    ]
    assert [item.data for item in contents[1:]] == [
        b"input-png",
        b"input-webp",
    ]


@pytest.mark.parametrize("images", ["", None, [None, ""], []])
def test_invoke_ignores_empty_image_placeholders(
    nanobana_imports: None,
    monkeypatch: pytest.MonkeyPatch,
    images: Any,
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {
                "prompt": "draw without references",
                "images": images,
            }
        )
    )

    assert fake_client.models.calls[0]["contents"] == [
        "draw without references"
    ]


def test_invoke_filters_empty_image_entries_from_list(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )
    input_image = SimpleNamespace(blob=b"input-png", mime_type="image/png")

    list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {
                "prompt": "edit this image",
                "images": [None, "", input_image],
            }
        )
    )

    contents = fake_client.models.calls[0]["contents"]
    assert contents[0] == "edit this image"
    assert len(contents) == 2
    assert contents[1].data == b"input-png"
    assert contents[1].mime_type == "image/png"


def test_broken_image_blob_returns_text_without_api_call(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    class BrokenImage:
        mime_type = "image/png"

        @property
        def blob(self) -> bytes:
            raise RuntimeError("file fetch failed for SECRET-KEY")

    messages = list(
        _tool(module, {"api_key": "SECRET-KEY"})._invoke(
            {
                "prompt": "edit broken image",
                "images": BrokenImage(),
            }
        )
    )

    assert fake_client.models.calls == []
    assert messages[0]["type"] == "text"
    assert "Invalid nanobana image input" in messages[0]["text"]
    assert "SECRET-KEY" not in messages[0]["text"]
    assert "[REDACTED]" in messages[0]["text"]


def test_invoke_returns_text_when_no_image(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Unable to show the generated image."}]
                }
            }
        ]
    }
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    messages = list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {"prompt": "blocked image"}
        )
    )

    assert messages == [
        {"type": "text", "text": "Unable to show the generated image."}
    ]


def test_invoke_masks_secret_in_error(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")

    def fail(_config: Any) -> None:
        raise RuntimeError("bad credential SECRET-KEY")

    monkeypatch.setattr(module, "make_genai_client", fail)

    messages = list(
        _tool(module, {"api_key": "SECRET-KEY"})._invoke(
            {"prompt": "draw a small banana"}
        )
    )

    assert messages[0]["type"] == "text"
    assert "SECRET-KEY" not in messages[0]["text"]
    assert "[REDACTED]" in messages[0]["text"]


def test_invalid_select_options_fall_back_to_defaults(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {
                "prompt": "draw a small banana",
                "model": "unknown-image-model",
                "aspect_ratio": "4:1",
                "resolution": "8K",
            }
        )
    )

    call = fake_client.models.calls[0]
    assert call["model"] == "gemini-3-pro-image"
    assert call["config"].image_config.aspect_ratio == "1:1"
    assert call["config"].image_config.image_size == "1K"


def test_image_size_parameter_does_not_override_resolution_default(
    nanobana_imports: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_google_type_stubs(monkeypatch)
    module = importlib.import_module("tools.nanobana")
    response = SimpleNamespace(candidates=[])
    fake_client = FakeClient(response)
    monkeypatch.setattr(
        module, "make_genai_client", lambda _config: fake_client
    )

    list(
        _tool(module, {"api_key": "developer-key"})._invoke(
            {
                "prompt": "draw a small banana",
                "image_size": "4K",
            }
        )
    )

    assert (
        fake_client.models.calls[0]["config"].image_config.image_size == "1K"
    )
