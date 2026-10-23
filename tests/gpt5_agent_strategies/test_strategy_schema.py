from __future__ import annotations

from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
PLUGIN_DIR = BASE_DIR / "app" / "gpt5_agent_strategies"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _parameter_names(strategy_yaml: str) -> set[str]:
    data = _load_yaml(PLUGIN_DIR / "strategies" / strategy_yaml)
    return {item["name"] for item in data["parameters"]}


def _parameter(strategy_yaml: str, name: str) -> dict:
    data = _load_yaml(PLUGIN_DIR / "strategies" / strategy_yaml)
    for item in data["parameters"]:
        if item["name"] == name:
            return item
    raise AssertionError(f"parameter not found: {strategy_yaml}:{name}")


def test_function_calling_strategy_has_required_parameters() -> None:
    names = _parameter_names("gpt5_function_calling.yaml")
    assert {
        "model",
        "tools",
        "instruction",
        "prompt_policy_overrides",
        "query",
        "maximum_iterations",
        "invocation_timeout_seconds",
        "emit_intermediate_thoughts",
        "allow_schemaless_tool_args",
    }.issubset(names)


def test_react_strategy_has_required_parameters() -> None:
    names = _parameter_names("gpt5_react.yaml")
    assert {
        "model",
        "tools",
        "instruction",
        "prompt_policy_overrides",
        "query",
        "maximum_iterations",
        "invocation_timeout_seconds",
        "emit_intermediate_thoughts",
        "allow_schemaless_tool_args",
    }.issubset(names)


def test_prompt_policy_overrides_has_help_and_placeholder_in_both_strategies() -> (
    None
):
    expected_keys = (
        "persistence_policy",
        "context_gathering_policy",
        "uncertainty_policy",
        "tool_preamble_policy",
        "extra_policy",
    )
    for strategy_yaml in ("gpt5_function_calling.yaml", "gpt5_react.yaml"):
        param = _parameter(strategy_yaml, "prompt_policy_overrides")
        help_i18n = param.get("help", {})
        placeholder_i18n = param.get("placeholder", {})

        assert "en_US" in help_i18n
        assert "ja_JP" in help_i18n
        assert "en_US" in placeholder_i18n
        assert "ja_JP" in placeholder_i18n

        assert "JSON" in str(help_i18n["en_US"])
        assert "プレーンテキスト" in str(help_i18n["ja_JP"])
        for key in expected_keys:
            assert key in str(help_i18n["en_US"])
            assert key in str(help_i18n["ja_JP"])

        assert "You do NOT need to write XML-like tags" in str(
            help_i18n["en_US"]
        )
        assert "タグ" in str(help_i18n["ja_JP"])
        assert "不要" in str(help_i18n["ja_JP"])
        assert "system-prompt policy block" in str(help_i18n["en_US"])
        assert "runtime context data" in str(help_i18n["en_US"])
        assert "context" in str(help_i18n["ja_JP"])
        assert "別物" in str(help_i18n["ja_JP"])

        assert "tool_preamble_policy" in str(placeholder_i18n["en_US"])
        assert "tool_preamble_policy" in str(placeholder_i18n["ja_JP"])
        assert "extra_policy" in str(placeholder_i18n["en_US"])
        assert "extra_policy" in str(placeholder_i18n["ja_JP"])
        assert "<tool_preamble>" not in str(placeholder_i18n["en_US"])
        assert "<tool_preamble>" not in str(placeholder_i18n["ja_JP"])


def test_common_parameters_have_help_in_both_strategies() -> None:
    expected_help_params = (
        "model",
        "tools",
        "instruction",
        "prompt_policy_overrides",
        "context",
        "query",
        "maximum_iterations",
        "invocation_timeout_seconds",
        "emit_intermediate_thoughts",
        "allow_schemaless_tool_args",
    )
    for strategy_yaml in ("gpt5_function_calling.yaml", "gpt5_react.yaml"):
        for param_name in expected_help_params:
            param = _parameter(strategy_yaml, param_name)
            help_i18n = param.get("help", {})
            assert "en_US" in help_i18n
            assert "ja_JP" in help_i18n
            assert str(help_i18n["en_US"]).strip()
            assert str(help_i18n["ja_JP"]).strip()

        context_help = _parameter(strategy_yaml, "context")["help"]
        assert "Runtime context data" in str(context_help["en_US"])
        assert "context_gathering_policy" in str(context_help["en_US"])
        assert "実行時コンテキスト" in str(context_help["ja_JP"])
        assert "別物" in str(context_help["ja_JP"])

        thought_help = _parameter(strategy_yaml, "emit_intermediate_thoughts")[
            "help"
        ]
        thought_default = _parameter(
            strategy_yaml, "emit_intermediate_thoughts"
        )["default"]
        assert thought_default is False
        assert "<think>" in str(thought_help["en_US"])
        assert "true" in str(thought_help["en_US"])
        assert "<think>" in str(thought_help["ja_JP"])
        assert "true" in str(thought_help["ja_JP"])

        schemaless_default = _parameter(
            strategy_yaml, "allow_schemaless_tool_args"
        )["default"]
        assert schemaless_default is False


def test_invocation_timeout_parameter_contract_in_both_strategies() -> None:
    for strategy_yaml in ("gpt5_function_calling.yaml", "gpt5_react.yaml"):
        param = _parameter(strategy_yaml, "invocation_timeout_seconds")
        help_i18n = param.get("help", {})

        assert param["default"] == 1200
        assert param["min"] == 60
        assert param["max"] == 1800
        assert "en_US" in help_i18n
        assert "ja_JP" in help_i18n
        assert "backwards invocation" in str(help_i18n["en_US"])
        assert "別レイヤー" in str(help_i18n["ja_JP"])
