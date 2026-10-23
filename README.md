# Dify plugins

`tkosht/dify_plugins` の公開コードから作成した独立したコピーです。各プラグインはPython 3.12とuvで実行します。SDKの版が異なるため、プラグインごとに独立した環境と `uv.lock` を持ちます。

| Plugin | 機能 | 手順 |
| --- | --- | --- |
| `gpt5_agent_strategies` | GPT-5 agent strategies | [README](app/gpt5_agent_strategies/README.md) |
| `nanobana` | Gemini画像生成 | [README](app/nanobana/README.md) |
| `openai_gpt5_responses` | OpenAI Responsesモデルprovider | [README](app/openai_gpt5_responses/README.md) |
| `pdf_text_pages` | PDF本文・ページ画像 | [README](app/pdf_text_pages/README.md) |
| `sharepoint_list` | SharePointリスト操作 | [README](app/sharepoint_list/README.md) |

## 開発と実行

ルートから、対象のプラグインを指定します。

```sh
uv sync --locked
uv sync --locked --project app/openai_gpt5_responses
uv run --project app/openai_gpt5_responses python -m pytest tests/openai_gpt5_responses -q
cd app/openai_gpt5_responses
uv run python main.py
```

`main.py` はDify plugin runtimeの入口です。実サービスへの接続には各pluginのREADMEに記載された認証・接続設定が必要です。環境ファイルや認証値はこのコピーに含めていません。通常のprovider認証はDify上で設定し、開発runtimeの接続設定は利用者のローカル環境で管理してください。

SDK 0.9.1を固定したプラグインと、SDK 0.10.2を使うPDFプラグインを一つの環境へ混ぜないでください。`requirements.txt` はDifyパッケージ向けの既存依存宣言として保持し、ローカル開発には各 `pyproject.toml` と `uv.lock` を使います。

## テスト

リポジトリのルートで実行します。

```sh
uv run --project app/gpt5_agent_strategies python -m pytest tests/gpt5_agent_strategies -q
uv run --project app/nanobana python -m pytest tests/nanobana -q
uv run --project app/openai_gpt5_responses python -m pytest tests/openai_gpt5_responses -q
uv run --project app/sharepoint_list python -m pytest tests/sharepoint_list -q
(cd app/pdf_text_pages && uv run python -m pytest tests -q)
uv run ruff check .
uv run black --check .
```

元のMIT LICENSE、各プラグインの表示・security/privacy文書、PDFの配布物と第三者ライセンスnoticeを保持しています。出典と変更範囲は [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md) を参照してください。
