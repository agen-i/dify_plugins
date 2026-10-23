# 実機検証の引継ぎ

実施ownerは顧客Dify workspace管理者と、その実行環境へのアクセスを許可された担当者です。窓口は2026-10-05の応答ヘッダー`X-Version: 1.17.1` / `X-Env: PRODUCTION`で対象Dify installed版を確認しました。対象daemon実版・pluginへの設定継承・直接接続は未確認です。コード/ローカル変換の合格を実機受入へ読み替えません。

## 今回の変更と確認

ユーザーは0.1.5の添付/空入力が正常に動作したと確認しています。0.1.6はPDF拡張子の全ページ変換を維持し、その他のファイルを元bytes/filename/MIMEのまま入力順に返します。環境設定を変更せず、0.1.6通常更新→同ChatflowでPDFと画像等の混在リストを再実行します。PDFの全ページgroupと元ファイルが入力順で並び、textはPDFだけ、JSONのPDF page.image_indexが実files位置に一致することを確認します。非画像ファイルも返却しますが、後続モデルの対応は別に確認します。PDF以外だけならtext空/files元ファイル、入力0件ならtext空/files空です。今回leafは実行していません。

ユーザーが新Chatflowでinvoke到達し、旧flow側が無応答の原因だったことを確認しました。0.1.4は0.1.2を基に、pdf_filesのみ/0件正常終了を実装しています。0.1.3-r2は不採用で含めません。以下は窓口がadmitする実機手順で、本leafは実行していません。

1. 同一最終`pdf_text_pages-0.1.6.difypkg`へ通常更新し、入力欄がpdf_filesのみであることを確認。旧pdf_file設定はpdf_filesへ同じFile変数を選び直す。
2. 入力ファイルなしで実行し、text空文字/files空配列/documents=[] JSON、通常のLLM質問が進むことを確認。設定sourceやDPIの新入力を要求しない。
3. 同じ新Chatflowで単一File変数・sys.files・任意listをpdf_filesへ割当し、1件以上の完成text/全pagefilesがLLM USER/Visionへ直接入ることを確認。単一Fileのリスト化/後処理/JSON追加はしない。

1件以上の実通信/安全性/LLM精度と原受入は別に記録します。元二入力口併用はuser指示で廃止され、一つのlistへ指定した順序/重複の検証と区別します。

## 未実施の認証・直接接続受入（窓口の別admission）

同一の最終配布物`dist/pdf_text_pages-0.1.5.difypkg`を使います。version/hash/source対応は`dist/BUILD_RECORD-0.1.5.json`で識別します。ここに書く導入/更新/実機操作はまだ実施していません。実施の採否は窓口が所有します。

1. 既存0.1.0/0.1.1/0.1.2のPlugins画面から0.1.4配布物へ通常更新し、版が0.1.4になったことを確認します。credential削除・再認証・再導入は行いません。新規導入を確認できる許可済み検証workspaceがある場合も同じ配布物を使い、認証情報がない状態を確認します。新規成功から旧認証状態の更新成功を推論しません。
2. Provider/tool画面に認証要求、`allowed_sources` JSON、固定IP等の追加入力が出ないことを確認します。既存Chatflowで合成`mixed.pdf`を単一File入力へ割り当て実行します。設定が不足すると、ノードに「FILES_URL / INTERNAL_FILES_URL（既存の別名設定を含む）が未設定です。管理者はDifyの既存配信設定とプラグインへの継承を確認してください。」と表示されます。不適合時は該当設定名と同じ確認事項を表示し、値・URL・署名を表示しません。
3. 成功時は`text`と4ページ分の画像`files`を確認し、USERへ`text`、Visionへ`files`を直接接続します。Template・コード・単一Fileのリスト化・JSON追加は行いません。LLM実入力traceに本文と画像の両方があることを確認します。これがT15の疎通証拠であり、インストール成功やLLMの自己申告だけでは合格にしません。
4. 添付`sys.files`、任意Fileリスト、tool由来の任意Fileも正規配信routeで同じ直接接続を試します。一listの順序、重複、空本文の詳細は下のT01–T07へ引き継ぎます。

設定不足・core設定との不一致で失敗した場合は、秘密のないノードエラーと対象版だけを窓口へ返します。管理者が既存設定の解決・pluginへの継承を確認し、窓口がAの成立とB等の再採否を判断します。ユーザーへホストコマンド、認証JSON、新しい必須envやcredential削除を要求する手順にはしません。

## T13の扱いと先に確認する条件

T13は認証要求なし/T15と別に合格を判定します。許可済み検証環境で不許可URL/route、取得失敗、署名queryを含む例外を試し、不許可先への通信がなく、URL/query/資格情報がノードエラー・通常ログへ出ないことを確認します。画面がURL/path文字列をFileへ変換できない場合は、その拒否を記録し、実行環境の担当が既存のFile境界試験を引き継ぎます。文字列拒否だけをredirect/proxy/TLS/実byte/累積期限の対象試験完了とは扱いません。実到達先・DNS/peer/TLSと実受信量・期限を対象環境で確認する部分は担当ownerへ残します。実URL・署名queryをチャットや共有ログへ貼りません。

- Dify/plugin-daemon/OpenAI provider pluginの実installed版、Linux CPU/Python、daemonメモリ/timeout/parallelism、モデル名/画像detail設定を記録します。公式composeのdaemon0.6.10-localを実daemon版の証拠にはしません。
- 管理者は独立した既存配信設定とcoreの解決済みbase、pluginへの継承、必要route、resolver/network/CAを確認します。API専用`api.env`やremote/TOML補完がpluginへ一致して渡る保証はありません。追加設定を通常利用の前提として持ち込まず、成立しなければ窓口へ返します。
- ソースdebugが必要な場合だけ、Plugins > debugの到達可能host:portとworkspace keyを使います。keyをチャットへ貼らずローカルで設定し、agentは`.env`本文を読み/表示しません。最終配布物の画面確認にdebug key/socketは不要です。
- インストール/ワークフロー実行の権限と承認を確認します。本番設定やDify版の更新は本開発taskの許可範囲に含めません。

## T01–T07 / T15

開始→本プラグイン→標準LLM→回答の4nodeを作り、開始でPDFを許可します。`pdf_files`へ単一File変数（core自動list化）またはsys.files等/任意listを指定します。二入力口の併用は廃止しました。Template/code/list変換nodeとJSON入力を追加しません。LLM USERは質問とtool.text、Visionはtool.filesを直接指定します。

`docs/samples/mixed.pdf`（4物理page）と`beta.pdf`（1page）を使い、単一File選択・添付list・任意list・同名別PDF・同じPDF重複を実行します。実行traceで以下を確認し、必要な証拠だけ機密を除いて保存します。

1. 1件の完成text、全pageのimage files、文書順/ページ順/一意ID。混在mixedは本文→画像だけ→白紙→回転日本語で4page、空本文も保持。
2. tool.filesのDify型がArray[File]であり、標準LLM Vision選択に表示されること。PNG MIME、filename metadataの採用、実ファイル数/順序を確認。
3. tool.jsonの実集約型（objectそのものか1objectのarray等）を記録。LLMには接続しない。
4. LLM実input traceでtextとimagesの両方が送られたことを確認。『画像を見た』というLLM自己申告だけを疎通証拠にしない。
5. 返却途中の通信障害を検証workspaceで再現できる場合は、部分結果がLLMへ正常入力されずtool/node failureになることを確認。

## T08–T10

fixtureの期待値: ALPHA/mixed物理page1は本文`ALPHA ... amount 42 kg`、青い矢印は右向き。BETA/beta物理page1は本文`BETA ... amount 42 kg`、青い矢印は左向き。mixed物理page2は緑の矩形を含むimage-only、page3は生成したblank、page4は90度回転した日本語『日本語の凡例：42キログラム』です。プラグインは空本文からpage種別を断定しません。

質問例: 『固有語ALPHA/BETAのある資料について、本文の数量と矢印の向きを対応づけ、資料名とPDF物理ページを根拠として答えてください。』両文書の固有語/数量/矢印/根拠pageを別々に採点し、モデル名・detail・DPI・画像数・入力prompt・正誤を記録します。

T09はテスト用Chatflowだけでimage順を入れ替え、textは同じにします。productionの利用者に並べ替えnodeを要求する仕様ではありません。画像内pixel IDで対応できたか、順序依存の誤対応、縮小後ID誤読を記録します。T10は本文の数量と図の方向を同じpageへ正しく結びつける回答を評価します。全回答の常時正確性を保証したものとして扱いません。

## T11–T14

非機密の破損/暗号化PDF、許可先からのHTTP失敗、上限前後、同時invoke、owned child timeout/memory failureを検証workspaceで実行します。対象位置を示す失敗、部分成功なし、本文/filename/URL/query非露出、temp cleanup、直後の正常request成功を確認してください。容量/モデル上限は顧客環境で具体値を確認し、SECURITYの初期値を保証値と扱わないでください。

既存配信設定の不足・不適合は意図した通信前fail-closedであり、疎通不良のために任意URLを許可する回避策へ変更しません。daemon/network運用は顧客管理者が扱います。

## 原要件全体の残件

認証要求なし、新規/通常更新、T13、T15の成立だけで全体完了にはしません。T01–T06の実UI、T07の対象表示/縮小、T08–T10のLLM分析精度、T11の返却途中障害、T12の対象上限適合/daemon enforcement、T14の対象daemon運用/回復は実機未実施です。窓口がこの同一packageの検証checkpointと担当を採否し、VERIFICATIONの受入表へ証拠を返します。I3の再fetch、I4の2秒idle、I5–I9の表示/設定/権限/返却に関する未検証候補も保持し、この認証修復から追加仕様変更へ自動変換しません。
