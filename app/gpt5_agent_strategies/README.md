# GPT-5 Agent Strategies プラグイン

このプラグインは Dify 向けに GPT-5 系モデル前提の Agent Strategy を提供します。

## 戦略

- `gpt5_function_calling`
- `gpt5_react`

`gpt5_react` は `gpt5_function_calling` 実装を継承しており、実行基盤と安全ガードは共通です。

## 主要パラメータ

- `model`: strategy で利用する LLM
- `tools`: 実行中に呼び出し可能なツール
- `instruction`: 実行時ベース指示（Dify の `prompt_instruction`）
- `prompt_policy_overrides`: system prompt ポリシー上書き
- `context`: 実行時コンテキストデータ（構造化オブジェクト）
- `query`: ユーザー入力
- `maximum_iterations`: ツール呼び出しループ上限（既定 6）
- `invocation_timeout_seconds`: strategy 内部呼び出しの待機時間（既定 1200）
- `emit_intermediate_thoughts`: 中間 `<think>` 表示制御（既定 `true`）

## タイムアウト層

- `invocation_timeout_seconds`
  - strategy 内で行う model/tool の backwards invocation 待機時間です。
- plugin 起動時の既定値
  - `MAX_REQUEST_TIMEOUT=1800`
  - `MAX_INVOCATION_TIMEOUT=1200`
- `MAX_REQUEST_TIMEOUT` は plugin process 全体の outer timeout、`invocation_timeout_seconds` は strategy 内部待機です。
- 起動時 timeout は OS 環境変数で上書き可能です。

## プロンプトのカスタマイズ（`prompt_policy_overrides`）

- プレーンテキスト:
  - 追加ポリシーとして末尾に追記
- JSON オブジェクト:
  - 次のキーのみ上書き可能
    - `persistence_policy`
    - `context_gathering_policy`
    - `uncertainty_policy`
    - `tool_preamble_policy`
    - `extra_policy`
  - 未知キーは無視
  - `persistence/context_gathering/uncertainty/tool_preamble` はタグ省略時に内部で自動タグ付与

`context_gathering_policy` は system prompt の方針ブロックです。`context`（実行時データ）とは別概念です。

## 出力表示ポリシー

- `emit_intermediate_thoughts=true`:
  - 実行中の `<think>` を表示
- `emit_intermediate_thoughts=false`:
  - `<think>` はユーザー表示に出さず、ユーザー向け可視テキストのみ返す

## 安全方針

- tool arguments は JSON object 文字列のみ許容
- 不正 JSON / 非文字列 / 非 object は fail-closed（tool 実行しない）
- tool 実行例外時は固定化エラーメッセージを返す
- 同一失敗 signature の重複 tool 呼び出しは抑止する
- local file 読み込みは `/files` 配下かつ 5MB 以下に制限する

## Dify UI 入力例（`prompt_policy_overrides`）

### 例1: プレーンテキスト

```text
<runtime_policy>
- 回答は箇条書きを優先してください。
</runtime_policy>
```

### 例2: JSON

```json
{
  "persistence_policy": "- タスク完了まで継続します。",
  "context_gathering_policy": "- まず広く確認し、その後に絞り込みます。",
  "uncertainty_policy": "- 前提は明示して進めます。",
  "tool_preamble_policy": "- ツール呼び出し前に <think> を日本語で出力してください。",
  "extra_policy": "- 最終回答は日本語で簡潔に。"
}
```
