# SharePoint List Tool Plugin (Dify)

Manage SharePoint list items (create/update/read) via Microsoft Graph using Delegated OAuth.

## Setup
1. Azure AD App 登録
   - Redirect URI: `https://<your-dify-host>/console/api/oauth/plugin/langgenius/sharepoint_list/sharepoint_list/datasource/callback` (self-host は `http://<host>/console/api/...`)
   - 権限: `openid`, `offline_access`, `User.Read`, `Sites.ReadWrite.All`
   - クライアントシークレットを発行
2. Dify のプラグイン設定で `client_id` / `client_secret` を入力し **Save & Authorize**

## Tools
- `sharepoint_list_create_item`: `list_url` + `fields_json` で新規作成
- `sharepoint_list_update_item`: 上記 + `item_id` + `fields_json` で更新
- `sharepoint_list_get_item`: 上記 + `item_id` (+ `select_fields` 任意) で参照
- `sharepoint_list_list_items`: 一覧取得（`list_url` 必須、`select_fields`/`filters`（JSON配列）/`page_size`/`page_token`、`createdDateTime desc` 固定）
- `sharepoint_list_get_choices`: choice 列の選択肢を取得（`list_url`/`field_identifier`）

## 入力のコツ

### list_url
- SharePoint のリストURL を指定します（例: `https://contoso.sharepoint.com/sites/demo/Lists/MyList/AllItems.aspx`）
- GUID 形式のリスト ID も対応しています
- **リスト解決の補足**: リスト名に日本語などの非ASCII文字が含まれる場合、`displayName` フィルタで解決できないことがあります。その場合、`webUrl` パスマッチングで自動的に補完します。

### fields_json
- SharePoint **内部フィールド名**→値 の JSON オブジェクト
- 表示名で指定しても内部名に解決されるので、表示名でも可
- 例: `{"Title": "Sample", "ステータス": "処理中"}`

### select_fields
- 取得するフィールドをカンマ区切りで指定: `Title,Status,Priority`
- 外側クォート（シングル/ダブル）は自動除去: `"Title,Status"` → `Title,Status`
- 各フィールドのクォートも除去: `"Title","Status"` → `Title,Status`
- **厳格な検証**: 存在しないフィールドを指定すると `GraphError` が発生します
- **欠落フィールドの補完**: Graph API が空値フィールドを省略する場合、プラグイン側で `None` を補完します（OData__ プレフィックス付きフィールドも対応）

## list_items: filters（JSON配列）
### 仕様
- `filters` は **JSON配列**（またはJSONオブジェクト1件）を文字列として渡します。
- 各要素は次の形です:
  - `field`（必須）: フィールド指定（内部名 or 表示名）
  - `op`（必須）: 演算子
  - `value`（必須）: 値（string/number/bool など）
  - `type`（任意）: 値の型ヒント（`string|number|bool|datetime`）

### 演算子
- 比較: `eq`, `ne`, `gt`, `ge`, `lt`, `le`
- 文字列関数: `contains`, `startswith`, `endswith`

### 例
ステータスが「処理中」のアイテムを一覧取得:

```json
[
  {"field": "ステータス", "op": "eq", "value": "処理中"}
]
```

作成日時が指定以降、かつ優先度が3以上:

```json
[
  {"field": "createdDateTime", "op": "ge", "value": "2025-12-15T00:00:00Z", "type": "datetime"},
  {"field": "優先度", "op": "ge", "value": 3, "type": "number"}
]
```

登録日時（リスト列）での日時フィルタ例:

```json
[
  {"field": "登録日時", "op": "gt", "value": "2025-12-16T15:00:00Z", "type": "datetime"}
]
```

### フィールド参照ルール（重要）
- `createdDateTime` は **トップレベル**のフィールドとして扱います（`createdDateTime ge ...`）。
- それ以外の列は SharePoint List の `fields/<internalName>` として `$filter` を組み立てます。
- `field` に **表示名（日本語）**を渡した場合も、内部的に列定義を取得して **内部名へ解決**します。
- 作成日時の条件も `filters` の `createdDateTime` で指定します（`type: "datetime"` を推奨）。
- リスト列の日時（例: 登録日時）に `type: "datetime"` を指定した場合、`fields/<name>` の比較は文字列としてクォートされます。
- 作成(create)/更新(update) でも `fields` のキーは表示名を内部名へ解決してから送信します。
- **未知フィールドの検証**: `filters` に存在しないフィールドを指定すると `GraphError` が発生します。

## 互換性
- `filter_field` / `filter_operator` / `filter_value` は廃止しました。フィルタは `filters`（JSON配列）で指定してください。
- `created_after` / `created_before` は廃止しました。作成日時の絞り込みは `filters` の `createdDateTime` を使用してください。

## 注意
- `client_secret` はユーザー資格情報に保存しません（Dify system credential のみ）。
  - **system credentials（システム資格情報）**: プラグイン設定で管理者が入力する `client_id` / `client_secret`（アプリ共通）。Provider が OAuth のトークン取得/更新にのみ使用します。
  - **ユーザー資格情報（OAuth credentials）**: 認可後にユーザーごとに保存される `access_token` / `refresh_token` / `expires_at`。Tool 実行時は `runtime.credentials` として参照されます。
  - `client_secret` はユーザー credentials に含めず、Tool 実行時にも渡しません（漏洩防止）。
- トークン・シークレットはログ/出力に含めません。
- フィルタで利用する列は SharePoint 側で **インデックス化** しておくと 400 エラーを防止できます。

## 制約・運用メモ
- SharePoint 側で「未インデックス列へのサーバーフィルタ」は 400 で拒否される場合があります。
  - 対象列にインデックスを付けるのが最短です。
- Choice列の選択肢（入力可能値）は `sharepoint_list_get_choices` で取得できます。

## エラー
プラグインは以下のエラーを送出します:
- `GraphError`: API 呼び出し失敗（存在しないフィールド指定、未知の filter フィールドなど）
- `AuthenticationError`: 認証失敗（トークン期限切れ、無効なトークンなど）
- `AuthorizationError`: 権限不足（必要なスコープが付与されていない）
- `RateLimitError`: レート制限超過（429 エラー）

## デバッグ
- Remote Debug で接続し、Create→Read→Update→Read の最小動線で確認してください。
- デバッグログを有効化する場合は環境変数 `SHAREPOINT_LIST_DEBUG_LOG=1` を設定してください（既定OFF）。ログは Dify の plugin logging 経路に出力されるため、self-host 環境では `plugin_daemon` のコンテナログから参照できます。`SHAREPOINT_LIST_DEBUG_LOG_PATH` は deprecated で、設定されていても無視されます。
