from __future__ import annotations

from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "app" / "nanobana"


def test_tool_schema_uses_ga_image_models() -> None:
    schema = (PLUGIN_DIR / "tools" / "nanobana.yaml").read_text()

    assert "gemini-3-pro-image" in schema
    assert "gemini-3.1-flash-image" in schema
    assert 'ja_JP: "gemini-3-pro-image"' in schema
    assert 'en_US: "gemini-3-pro-image"' in schema
    assert 'ja_JP: "gemini-3.1-flash-image"' in schema
    assert 'en_US: "gemini-3.1-flash-image"' in schema
    assert "Nano Banana Pro" not in schema
    assert "Nano Banana 2" not in schema
    assert "gemini-3-pro-image-preview" not in schema
    assert "gemini-3.1-flash-image-preview" not in schema


def test_tool_schema_exposes_images_and_resolution() -> None:
    schema = (PLUGIN_DIR / "tools" / "nanobana.yaml").read_text()

    assert "name: images" in schema
    assert "type: files" in schema
    assert "name: resolution" in schema
    assert "ja_JP: 解像度" in schema
    assert "en_US: Resolution" in schema
    assert 'value: "1K"' in schema
    assert 'value: "2K"' in schema
    assert 'value: "4K"' in schema
    assert 'value: "512"' not in schema
    assert "Pro-first workflows" in schema
    assert "4K (Preview)" not in schema
    assert "name: image_size" not in schema


def test_provider_schema_supports_developer_and_vertex_modes() -> None:
    schema = (PLUGIN_DIR / "provider" / "nanobana.yaml").read_text()

    assert "api_key:" in schema
    assert "vertex_project_id:" in schema
    assert "vertex_location:" in schema
    assert "vertex_service_account_key:" in schema
    assert (
        "Service Account Key (Leave blank if you use Application Default Credentials)"
        in schema
    )
    assert "Service Account Key (base64 JSON)" not in schema
    assert (
        "Enter your Google Cloud Service Account Key in base64 format"
        in schema
    )


def test_readme_documents_pro_first_scope_and_user_side_live_checks() -> None:
    readme = (PLUGIN_DIR / "README.md").read_text()
    ja_readme = (PLUGIN_DIR / "readme" / "README_ja_JP.md").read_text()

    assert "`gemini-3-pro-image` is the primary/default model" in readme
    assert "gemini-3-pro-image-preview" not in readme
    assert "Pro-compatible resolutions `1K`, `2K`, and `4K`" in readme
    assert "1K" in readme
    assert "2K" in readme
    assert "4K" in readme
    assert "512" not in readme
    assert "image_size" not in readme
    assert "`512` is only supported" not in readme
    assert "`4K` is a Google Preview feature" not in readme
    assert (
        "Automated unit and package tests do not perform live Gemini" in readme
    )
    assert "Vertex AI calls" in readme
    assert (
        "verify real authentication and runtime behavior from Dify" in readme
    )
    assert "### Unverified items" in readme
    assert (
        "Live Gemini Developer API and Vertex AI requests are user-side checks"
        in readme
    )
    assert "Real credentials are user-side checks" in readme
    assert (
        "Installed Dify UI workflow smoke tests are user-side checks" in readme
    )
    assert "`4K` remains documented as a Pro-compatible resolution" in readme
    assert (
        "`gemini-3-pro-image` は、このプラグインの主対象かつ既定モデルです"
        in ja_readme
    )
    assert "512" not in ja_readme
    assert "image_size" not in ja_readme
    assert "Pro 互換の `1K`、`2K`、`4K`" in ja_readme
    assert "### 未調査事項" in ja_readme
    assert (
        "Gemini Developer API / Vertex AI への live request はユーザー側"
        in ja_readme
    )
    assert "実ユーザー認証情報は自動テストでは確認しません" in ja_readme
    assert "workflow smoke test はユーザー側" in ja_readme
