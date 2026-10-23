from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.openai_gpt5_responses.internal.credentials import (
    normalize_api_base,
)

BASE_DIR = Path(__file__).resolve().parents[2]
PLUGIN_DIR = BASE_DIR / "app" / "openai_gpt5_responses"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_provider_schema_exposes_required_credentials() -> None:
    provider = _load_yaml(PLUGIN_DIR / "provider" / "openai_gpt5.yaml")
    schemas = provider["provider_credential_schema"]["credential_form_schemas"]
    variables = [schema["variable"] for schema in schemas]

    assert "openai_api_key" in variables
    assert "openai_organization" in variables
    assert "openai_api_base" in variables
    assert "request_timeout_seconds" in variables
    assert "max_retries" in variables


def test_provider_supports_predefined_and_customizable_models() -> None:
    provider = _load_yaml(PLUGIN_DIR / "provider" / "openai_gpt5.yaml")
    methods = provider["configurate_methods"]

    assert "predefined-model" in methods
    assert "customizable-model" in methods


def test_required_models_exist() -> None:
    llm_dir = PLUGIN_DIR / "models" / "llm"
    required = {
        "gpt-5.4.yaml",
        "gpt-5.4-pro.yaml",
        "gpt-5.2.yaml",
        "gpt-5.2-pro.yaml",
        "gpt-5.3-codex.yaml",
    }
    actual = {p.name for p in llm_dir.glob("*.yaml")}

    assert required.issubset(actual)


def test_predefined_model_position_prioritizes_latest_gpt54_variants() -> None:
    position = _load_yaml(PLUGIN_DIR / "models" / "llm" / "_position.yaml")

    assert position[:4] == [
        "gpt-5.4",
        "gpt-5.4-pro",
        "gpt-5.2",
        "gpt-5.2-pro",
    ]


def test_llm_models_expose_api_exact_parameter_names() -> None:
    llm_dir = PLUGIN_DIR / "models" / "llm"
    target_names = {
        "max_output_tokens",
        "reasoning_effort",
        "reasoning_summary",
        "verbosity",
        "response_format",
        "json_schema",
        "tool_choice",
        "parallel_tool_calls",
        "enable_stream",
    }

    for yaml_path in llm_dir.glob("*.yaml"):
        if yaml_path.name.startswith("_"):
            continue
        if yaml_path.name == "llm.py":
            continue

        data = _load_yaml(yaml_path)
        parameter_rules = data.get("parameter_rules", [])
        names = {rule.get("name") for rule in parameter_rules}
        assert target_names.issubset(names), yaml_path.name


def test_llm_parameter_rules_have_help_i18n_fields() -> None:
    llm_dir = PLUGIN_DIR / "models" / "llm"
    for yaml_path in llm_dir.glob("*.yaml"):
        if yaml_path.name.startswith("_"):
            continue

        data = _load_yaml(yaml_path)
        parameter_rules = data.get("parameter_rules", [])
        assert parameter_rules, yaml_path.name

        for rule in parameter_rules:
            help_obj = rule.get("help")
            assert isinstance(
                help_obj, dict
            ), f"{yaml_path.name}:{rule.get('name')} missing help"
            assert help_obj.get(
                "en_US"
            ), f"{yaml_path.name}:{rule.get('name')} missing help.en_US"
            assert help_obj.get(
                "ja_JP"
            ), f"{yaml_path.name}:{rule.get('name')} missing help.ja_JP"


def test_llm_reasoning_summary_rule_has_expected_default_and_options() -> None:
    llm_dir = PLUGIN_DIR / "models" / "llm"
    expected_options = {"auto", "concise", "detailed"}

    for yaml_path in llm_dir.glob("*.yaml"):
        if yaml_path.name.startswith("_"):
            continue

        data = _load_yaml(yaml_path)
        parameter_rules = data.get("parameter_rules", [])
        by_name = {rule.get("name"): rule for rule in parameter_rules}
        summary_rule = by_name["reasoning_summary"]

        assert summary_rule.get("default") == "auto", yaml_path.name
        options = set(summary_rule.get("options", []))
        assert options == expected_options, yaml_path.name


def test_provider_schema_has_documented_defaults() -> None:
    provider = _load_yaml(PLUGIN_DIR / "provider" / "openai_gpt5.yaml")
    schemas = provider["provider_credential_schema"]["credential_form_schemas"]
    by_name = {schema["variable"]: schema for schema in schemas}

    assert by_name["openai_api_base"]["default"] == ""
    assert by_name["request_timeout_seconds"]["default"] == "600"
    assert by_name["max_retries"]["default"] == "1"


def test_model_yaml_does_not_claim_vision_feature() -> None:
    llm_dir = PLUGIN_DIR / "models" / "llm"
    for yaml_path in llm_dir.glob("*.yaml"):
        if yaml_path.name.startswith("_"):
            continue
        data = _load_yaml(yaml_path)
        features = set(data.get("features", []))
        assert "vision" not in features, yaml_path.name


def test_model_yaml_claims_agent_thought_feature() -> None:
    llm_dir = PLUGIN_DIR / "models" / "llm"
    for yaml_path in llm_dir.glob("*.yaml"):
        if yaml_path.name.startswith("_"):
            continue
        data = _load_yaml(yaml_path)
        features = set(data.get("features", []))
        assert "agent-thought" in features, yaml_path.name


def test_api_base_normalization_is_v1_idempotent() -> None:
    expected = "https://api.openai.com/v1"
    assert normalize_api_base("https://api.openai.com") == expected
    assert normalize_api_base("https://api.openai.com/v1") == expected


def test_api_base_normalization_rejects_non_https() -> None:
    with pytest.raises(ValueError, match="https"):
        normalize_api_base("http://api.openai.com")


def test_api_base_normalization_rejects_private_or_local_hosts() -> None:
    candidates = [
        "https://127.0.0.1",
        "https://10.0.0.10",
        "https://169.254.169.254",
        "https://localhost",
    ]
    for candidate in candidates:
        with pytest.raises(ValueError, match="not allowed"):
            normalize_api_base(candidate)


def test_api_base_normalization_rejects_missing_host_or_userinfo() -> None:
    with pytest.raises(ValueError, match="host is required"):
        normalize_api_base("https://")
    with pytest.raises(ValueError, match="must not include credentials"):
        normalize_api_base("https://user:pass@api.openai.com")


def test_api_base_normalization_rejects_non_allowlisted_host_by_default() -> (
    None
):
    with pytest.raises(ValueError, match="not allowed"):
        normalize_api_base("https://example.test")


def test_api_base_normalization_rejects_invalid_path() -> None:
    with pytest.raises(ValueError, match="path must be /v1"):
        normalize_api_base("https://api.openai.com/v2")


def test_api_base_normalization_rejects_localhost_subdomain() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        normalize_api_base("https://service.localhost")


def test_api_base_normalization_allows_configured_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_GPT5_ALLOWED_BASE_URL_HOSTS", "example.test")
    assert (
        normalize_api_base("https://example.test") == "https://example.test/v1"
    )
