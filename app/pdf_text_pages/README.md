# PDF本文・ページ画像プラグイン 0.1.6

PDFの全ページを、同じページレコードの本文とPNG画像から出力します。Dify Chatflowの標準LLMノードへ完成済み`text`と`files`を直接接続する設計です。Template・コードノード・リスト変換・`json`の追加入力を利用者へ要求しません。ローカルSDK・変換・安全性テストと公式CLIパッケージ化を実施しています。**顧客Dify上での直接接続とLLMの回答精度は未検証です。** 実施範囲は[VERIFICATION.md](VERIFICATION.md)を参照してください。

## 0.1.6のファイル入力

`pdf_files`へ`sys.files`などのファイルリストを直接指定できます。拡張子が`pdf`または`.pdf`（大文字小文字を区別しない）のファイルだけを全ページ変換します。拡張子が未指定ならファイル名の末尾を使い、MIMEだけでPDFへ分類しません。PDF以外は画像・非画像を問わず、同じ安全な取得経路で取得したbytes、ファイル名、MIMEをそのまま返します。名前/MIMEが未指定の場合だけ`file`/`application/octet-stream`を使います。

`files`は入力順を保ち、PDFの位置には全ページPNGをまとめて、そのほかの位置には元ファイルを一つ出力します。`text`はPDF本文と読み方だけで、PDFがなければ完全に空です。`json`のschema1.0とPDF文書だけの`documents`を維持し、各ページの`image_index`は混在後の`files`位置を示します。元ファイルについての説明文や追加JSON構造は生成しません。後続モデルが対応しない形式も除外しません。

全入力へ既存の件数・入力byte・累積期限を適用し、元ファイルにも出力単体8MiB、PNGとの合計40MiBの既定上限を適用します。ページ上限はPDFだけを数えます。上限超過や後のファイルの取得・変換失敗では部分成功を返しません。0.1.6の混在入力とLLMの実機確認は未実施です。

## 取得先対応

顧客Difyの環境設定は変更しません。独立した既存FILES_URL等のoriginと限定file routeへ一致する入力だけを、既存の解決済DIFY_INNER_API_URLへ同じpath/queryで取得します。公開側へ接続を試してからfallbackする方式ではありません。INTERNAL_FILES_URL等が既に有効なら従来の直接取得を維持し、不要な内部API設定の検査を加えません。

入力origin/pathの検査後、内部targetだけをDNS/IP固定/peer/Host/SNI/TLSで取得し、proxy/redirect・実byte/期限・機密非露出を維持します。入力URLから設定を生成せず、API defaultやPLUGIN_DIFY_INNER_API_URL aliasを推測しません。同originは元の直接path/queryを保持。origin変更が必要な場合は外部base pathが空、内部APIbaseがrootに限り、外部末尾/（//filesになる形）やnonroot prefixは対応未確認のため通信前CONFIGにします。strip/addprefixや環境変更を要求する回避策はありません。

ユーザー操作は0.1.6へ通常更新して同じChatflow/同じPDFを再実行するだけです。実機の修復成立は未確認です。PDF入力一つ/0件正常終了、DPI、元の本文/全pagePNG対応は不変です。

## 入力と空リスト

ファイル入力は`pdf_files`一つです。`sys.files`や任意のFileリスト、単一File変数を指定できます。Dify1.17.1のselectorはFile/Array[File]を許可し、単一Fileはcoreが一要素listへ変換してSDKへ渡します。ユーザー側でリスト化するノードは不要です。この経路は[固定sourceと検証記録](VERIFICATION.md)に基づき、実UIは未測です。

入力ファイルが0件（空list・未指定・None）なら正常終了し、`text`は空文字、`files`は標準の空list、`json`は既存schemaでdocuments=[]を返します。通信・変換・slot/一時childを開始せず、不要な配信source/DPI/管理limits検査も行いません。list以外の不正値を空として扱わず、1件以上では配信設定・DPI・上限を検査します。PDFの順序・重複・全page/空本文対応を維持します。

最新ユーザー指示で`pdf_file`パラメータと二入力口の併用を廃止しました。旧`pdf_file`を設定していたノードは、`pdf_files`へ同じFile変数を選び直してください。本文/imagesの後処理やJSON追加は不要です。原HANDOFFは変更せず、入力口の採用変更として本記録に分けて残します。

旧0.1.2の無応答は既存Chatflow側の問題とユーザーが確認し、新しいChatflowでplugin invokeに到達しました。0.1.3-r2 SDK adapterは不採用で本版へ含めません。ユーザーは0.1.5の添付入力と空入力が正常に動作したと確認しています。混在入力・LLM接続の全受入とは区別します。

## 導入

対象はLinux amd64、Python 3.12です。固定依存は`requirements.txt`（全runtime依存の版とwheel hash）と`uv.lock`（開発依存も含む）に記録しています。SDK 0.10.2、pypdfium2 5.14.0（PDFium 156.0.8076.0）、Pillow 12.3.0を採用しました。最低Dify宣言は1.17.1です。認証修復は1.17.1のプラグインFile URL生成・設定の意味に合わせています。対象Dify 1.17.1は窓口の応答ヘッダー観測で確認済みですが、対象daemonの版・設定継承・実機直接接続・通常更新は未確認です。その他のDify版の互換性は未検証です。

1. [SECURITY.md](SECURITY.md)の上限・保存方針と、顧客Dify/plugin-daemonの版、メモリ、Python、対象モデルの画像数/サイズ/入力長を確認します。
2. DifyのPlugins画面から`dist/pdf_text_pages-0.1.6.difypkg`をローカルファイルとして導入します。署名必須環境では組織の署名/導入手続きを使ってください。本プラグインは署名検証設定を変更しません。
3. Providerの認証設定はありません。配信JSON、固定IP、追加の環境設定、旧credentialの削除は通常利用の手順に含めません。0.1.0/0.1.1/0.1.2/0.1.4からは同じauthor/nameの0.1.6配布物を通常更新します。旧版の配布物と記録は保持しています。新規導入・通常更新で認証要求が消えることと、正規PDFを実行できることは実機確認が必要です。

取得先は入力Fileと独立したプラグインプロセスの既存管理設定から制限します。Dify 1.17.1に合わせ、`INTERNAL_FILES_URL`が存在しなければ既存の別名`SERVER_CONSOLE_API_URL`を読み、`FILES_URL`が存在しなければ`CONSOLE_API_URL`を読みます。primaryが存在して空文字の場合はその別名へ戻りません。その後、内部値が空でなければ内部値、空なら外部値を選びます。同じbaseの`/files/{id}/file-preview`と`/files/tools/{id}{extension}`だけを許可します。base pathも照合し、Difyのbaseとrouteの連結を保持します。既存管理設定による限定origin→内部API対応以外のURL書換えは行いません。

設定不足・不適合は通信前に短い日本語のノードエラーになります。例：「FILES_URL / INTERNAL_FILES_URL（既存の別名設定を含む）が未設定です。管理者はDifyの既存配信設定とプラグインへの継承を確認してください。」値・URL・署名は表示しません。管理者は既存設定の解決値と継承を確認し、窓口が次案を判断します。認証JSONや新しい必須設定を追加して解決済みとは扱いません。coreのremote/TOML設定とpluginの環境設定が一致する保証はなく、公式composeのAPI専用`api.env`の値がdaemonへ渡る保証もありません。

承認hostのDNSは取得期限内に停止・回収可能な子プロセスで解決し、一回のDNS解決結果内のIPへ固定して実socket peerのIP/portを確認します。接続失敗時だけ同じsnapshot内の次IPを、累積期限内で試します。peer/TLS検証失敗やHTTP送信後は再試行しません。HTTP Host/TLS SNIと標準CA/hostname検証を維持し、redirect・環境proxy・userinfo・fragment・encoding/traversalを拒否します。resolver/networkとcore設定の対応は対象環境で確認する条件です。[旧JSON例](config/allowed_sources.example.json)は0.1.0の書式証拠として保持しており、0.1.1の認証入力や設定sourceには使いません。署名付きURLをチャットや通常ログへ貼らないでください。

4. 非機密合成PDFで[実機検証手順](docs/LIVE_TESTS.md)を実施します。`text`と`files`が標準LLMへ入った実行traceを確認してから顧客資料へ進んでください。

## Chatflow接続

```text
開始 → PDF本文・ページ画像 → LLM（Vision対応OpenAIモデル）→ 回答
                     text → USERプロンプトへ変数挿入
                    files → LLMのVision入力へ直接指定
```

| 入力方法 | プラグイン設定 |
|---|---|
| 任意の単一File変数 | `pdf_files`へ直接指定。Dify coreが一要素listへ変換 |
| 添付リスト`sys.files`等 | `pdf_files`へその変数を指定 |
| 任意のファイルリスト変数 | `pdf_files`へ指定。元の順序と重複を保持 |
| 入力なし | 未指定/空list/Noneでtext空・files空・文書0件JSON |
| PDF以外のみ | text空・filesは元ファイル・文書0件JSON。取得設定を検査 |

`pdf_files`は0..管理上限件です。PDF以外も取得して元ファイルとして返します。同名/同内容/同一Fileの重複も保持し、PDFの重複は独立文書にします。割当元変数名や業務上の役割は推定しません。`dpi`は既定150、36〜管理者上限（既定200）です。0件では変換しないためpluginのDPI検査も不要です。

| 標準出力 | 内容 |
|---|---|
| `text` | 読み方、文書名/ID、PDF物理ページ番号/ID、そのページの抽出本文。1 text message |
| `files` | 入力順の元ファイルとPDF全ページのPNG blob messages。PNGはimage/png、filenameはページID.png |
| `json` | 1 JSON object message。batch→PDF documents→pages、入力口/位置、ID、本文状態/文字数、混在files内の画像位置/filename。本文全文/画像Base64を複製しない |

採用SDKで単一File/list[File]、TEXT/BLOB/JSON messagesを観測しました。Dify側での`files`のArray[File]認識、画像順、metadata filenameの採用、`json`のobject配列への集約は実機確認対象です。Difyの標準出力仕様から直接接続を設計し、SDK観測をDify実機完了へ読み替えていません。

識別子は`B`+UUID4の32桁hex、入力順`D001`、物理ページ`P0001`です。UUID4の122 random bitsを使い、batch内重複も検査します。異なる実行のID衝突確率は極小ですが数学的ゼロではありません。ファイル名に依存するIDや永続保存は使いません。ページIDを32px ASCIIで元ページ外の80px上余白へ描画し、元ページを重ねません。低DPIなどでラベルがページ幅を超える場合は白いcanvas幅だけを広げます。

本文は要約/補完/OCRを行わず、CRLF→LFだけを整えます。空本文ページも残し、空であることから白紙/スキャンと断定しません。複数段組の読み順/表構造の完全な文字抽出は保証しません。ファイル名は見出し用にJSON quotingと制御文字処理を行います。資料本文に似た見出しや指示があっても構造として再解析せず、引用データとして示します。区切りでLLMへの悪意ある指示を完全防止できるとは扱いません。

## ローカル実行・debug

```bash
cd app/pdf_text_pages
uv sync --frozen
uv run pytest
uv run ruff check pdf_core provider tools tests main.py
```

Dify Pluginsのdebugアイコンで表示された**到達可能なdaemon host:port**を使います。[config/debug-env.example](config/debug-env.example)をローカルで`.env`へコピーし、`REMOTE_INSTALL_URL`と`REMOTE_INSTALL_KEY`を設定してください。キーはチャット/ログへ出さず、`.env*`はパッケージから除外します。source repoには同じ内容の`.env.example`もあり、Gitはそのtemplateだけを含めます。エージェントも`.env`本文を読みません。

```bash
uv run python -m main
```

2026-10-04 UTCの到達probeでは`dify`→172.18.0.2、HTTP80は到達、HTTPS443/daemon候補5003は拒否、`plugin_daemon`/`plugin-daemon`はDNS解決不可でした。HTTP UIへ到達できてもdebug socketへ到達できるとは限りません。管理者がUI表示のhost:portを確認し、必要ならdaemonネットワーク公開を管理してください。版APIの返却値1.16.1はinstalled版の証拠としては採用していません。

ソースdebugは任意の開発経路です。配布物の導入・実機確認にはdebug key/socketを要求しません。debugでもProvider資格情報は使わず、実行プロセスに既に存在する独立した配信設定を検査します。設定不足はローカル合成テストを阻害しませんが正規ファイル取得の成立確認が残ります。OpenAI APIキーは本プラグインでは不要で、後続LLMのprovider設定に属します。

## エラーと制限

拡張子のないファイル名（例 `README`）は、Dify 1.17.1がファイル保存時にMIMEから拡張子を補完します（例 `README.txt`）。bytes・MIME・出力順序は保持されますが、保存後のDify File名の完全一致は保証しません。根拠はDify 1.17.1の [`api/core/tools/tool_file_manager.py:74`](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/tools/tool_file_manager.py#L74)（commit `8387590a`）です。

`INPUT`/`FETCH_DENIED`/`FETCH_HTTP`/`FETCH_FAILURE`/`FETCH_TIMEOUT`/`PDF_OPEN`/`PDF_TEXT`/`PDF_RENDER`/`LIMIT`/`PROCESS_TIMEOUT`/`PROCESS_EXIT`/`BUSY`で分類し、文書入力位置と可能なページ番号を示します。本文/filename/URL/署名query/元例外は通常ログやエラーへ含めません。処理途中の失敗で部分結果をyieldせず、全変換・整合検査・全message構築後に返します。返却開始後のDify通信障害はローカルでは再現しておらず、実機でノード失敗扱いを確認してください。

上限を超える資料は黙って切り詰めず全体失敗します。管理者が十分な資源とDify/LLM側上限を確認した場合に、`PDF_TEXT_PAGES_LIMITS`（`config/debug-env.example`参照）で変更します。Difyツール画面のDPI maxは200なので、この値を超える運用はmanifest変更と再検証が必要です。会話をまたぐ保存/再取得は実装していません。追加質問へ資料を再利用する場合はChatflow側で同じ出力を再投入してください。

配布物作成は公式CLI 0.6.10です。

```bash
.local-bin/dify plugin package . -o dist/pdf_text_pages-0.1.6.difypkg
sha256sum dist/pdf_text_pages-0.1.6.difypkg
```

[SECURITY.md](SECURITY.md)、[third_party/INDEX.md](third_party/INDEX.md)、[docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)に依存/通信/制限/更新方針を記録しています。原要件は[docs/DIFY_PDF_PLUGIN_HANDOFF.md](docs/DIFY_PDF_PLUGIN_HANDOFF.md)へ原文のままコピーし、workspace元ファイルも保持しています。
