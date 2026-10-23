## nanobana

Dify workflow から Gemini Nano Banana 系モデルで画像を生成・編集する Tool plugin です。

### 認証方式

- Vertex AI: `vertex_project_id` を設定します。`vertex_location` は未指定時 `global` です。`vertex_service_account_key` は base64 エンコードしたサービスアカウントキー JSON を指定できます。空欄の場合は Application Default Credentials に委ねます。
- Gemini Developer API: `vertex_project_id` を空欄にし、`api_key` を設定します。

両方設定されている場合は Vertex AI を優先します。

### モデル

- `gemini-3-pro-image` は、このプラグインの主対象かつ既定モデルです。
- `gemini-3.1-flash-image`

現行 GA のモデル ID のみを公開します。

### ツールパラメータ

- `prompt`: 画像生成・編集プロンプトです。
- `images`: 編集または参照に使う任意の入力画像です。
- `model`: Gemini 画像モデルです。
- `aspect_ratio`: 生成画像の縦横比です。
- `resolution`: 生成画像の解像度です。Pro 前提の workflow では、Pro 互換の `1K`、`2K`、`4K` を使用してください。

### 認証テスト

自動 unit/package test では、Gemini Developer API または Vertex AI への live call は実行しません。実認証と runtime 挙動は、Dify 側で provider を設定したあと、以下の最小条件で tool を実行して確認してください。

- model: `gemini-3-pro-image`
- location: `global`
- resolution: `1K`
- aspect ratio: `1:1`

Google から画像なしのテキスト応答が返った場合は、認証失敗ではなく通常のテキスト結果として返します。

### 未調査事項

- Gemini Developer API / Vertex AI への live request はユーザー側で確認してください。
- 実ユーザー認証情報は自動テストでは確認しません。
- Dify UI にインストールした workflow smoke test はユーザー側で確認してください。
- `4K` は Pro 互換の解像度として文書化しており、Dify workflow 検証に含めてください。
