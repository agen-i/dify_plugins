# OpenAI GPT-5 Responses プラグイン

このプラグインは OpenAI Responses API を使い、Dify に GPT-5 系モデルを提供します。

## 主な特徴

- API パラメータ名を Dify UI へほぼそのまま公開
- `gpt-5.4` / `gpt-5.4-pro` / `gpt-5.2` / `gpt-5.2-pro` を含む predefined model を同梱
- `gpt-5-codex` / `gpt-5.1-codex` / `gpt-5.3-codex` を選択可能
- モデル可用性は実行時 API エラーで検知（事前遮断しない）

## プロバイダー認証情報

- `openai_api_key`（必須）
- `openai_organization`（任意）
- `openai_api_base`（任意、`https` + allowlist 検証後に `/v1` 正規化）
- `request_timeout_seconds`（任意、30〜1200 に clamp。既定 `600`）
- `max_retries`（任意、0〜5 に clamp）

## Plugin Runtime Timeout

- plugin 起動時の既定値:
  - `MAX_REQUEST_TIMEOUT=1200`
  - `MAX_INVOCATION_TIMEOUT=1200`
- どちらも OS 環境変数で上書き可能です。
- `request_timeout_seconds` は OpenAI API リクエストの待機時間であり、plugin runtime の timeout とは別です。

`openai_api_base` の安全制約:
- `https` のみ許可
- `localhost` / private IP / link-local / metadata endpoint は拒否
- 既定許可ホストは `api.openai.com`
- 追加許可は `OPENAI_GPT5_ALLOWED_BASE_URL_HOSTS`（カンマ区切り）で設定

## LLM パラメータ

- `max_output_tokens`
- `reasoning_effort` (`none/minimal/low/medium/high/xhigh`)
- `reasoning_summary` (`auto/concise/detailed`)
- `verbosity` (`low/medium/high`)
- `response_format` (`text/json_schema`)
- `json_schema`（`response_format=json_schema` 時に必須）
- `tool_choice`
- `parallel_tool_calls`
- `enable_stream`

bool-like パラメータ（`enable_stream`, `parallel_tool_calls`, `json_schema.strict`）は次を受け付けます。

- `true/false`
- `"true"/"false"`
- `1/0`
- `"1"/"0"`

## 安全な監査ログ

`OPENAI_GPT5_AUDIT_LOG=true` を設定すると監査ログを標準出力に出力します。

### 出力される項目

- `event`: `responses_api_request` / `responses_api_success` / `responses_api_error`
- `model` / `response_model`
- `request_id`（利用可能時）
- `status_code` / `code` / `param`（エラー時）
- `response_format` / `stream` / `tool_count` / `input_message_count`
- `base_url_host`

### 出力しない項目

- API key（`openai_api_key`）
- Authorization header
- Prompt content/body
- JSON schema body と tool argument payload
