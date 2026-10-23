# 検証記録

## 0.1.6：PDF変換とその他ファイルの元bytes返却

committed0.1.5 e8fc0d3/package SHA71c497f58f4d1bdb16973d0c4db6dc90c1bcb11dc0d258907c41c09d19978340が採用元です。ユーザーは同版の添付と空入力の正常動作を確認しています。0.1.6は拡張子優先/欠損時filename末尾/PDFだけsignature・parser検査、MIMEだけのPDF昇格無し。その他は既存fetchをそのまま使いbytes/filename/MIMEを返却し、混在filesの位置だけPDF metadataへ反映します。schema1.0/PDF-only documentsと内部PDF連番検査は不変。PDF無しtextは完全空、入力無しは従来の設定検査/通信/変換無しです。

固定一次sourceを親が2026-10-05に有界確認：[graphon File](https://github.com/langgenius/graphon/blob/11e2dee8cbd6dc2e6bf1c2059d9bbf4d0437ebe5/src/graphon/file/models.py#L189)は画像もfor_external=False、[file_runtime](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/app/workflow/file_runtime.py#L58)はtransfer_method別の既存file-preview/tool/datasource routeを生成し、画像専用routeへ分岐しません。[upload service](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/services/upload_file_delivery_service.py#L67)は署名検証後storage stream、[upload controller](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/controllers/files/upload_file_delivery.py#L107)と[tool controller](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/controllers/files/tool_files.py#L43)はAcceptによるbody変換をしません。SVG/html等のresponse header安全化とbody不変を区別し、元File.MIMEを出力metaへ保持します。fetchのAccept/許可routeは変更不要です。REMOTE_URLも旧policy外なら拒否します。実環境の配信成功を保証するsourceではありません。

既存max_filesとinputbyte/期限は全入力、output_file/totalは元ファイルとPNG合算、page上限はPDFだけ。全取得・変換・上限検査・message準備後にyieldします。新抽象・設定・診断・依存はありません。main/worker/runner/config/fetchとDPI/limits既定は0.1.5のままです。

TDD新8caseは8failed/2warnings/1.02s→8passed/2warnings/1.14s。必要境界追加後11caseを含むfocusedは55passed/10warnings/16.30s。exact plugin full suiteは**required_now、148 passed / 16 warnings / 26.61s、exit0**、[結果](docs/phase8-test-results-0.1.6.txt)。ruff check成功、format19files成功。旧138成功は旧候補だけの証拠です。SDK由来warningsは実daemon互換性の保証ではありません。

```bash
.venv/bin/python -m pytest tests/test_passthrough.py tests/test_empty_input.py tests/test_fetch_adapter.py --tb=short
.venv/bin/python -m pytest --tb=short > docs/phase8-test-results-0.1.6.txt 2>&1
.venv/bin/ruff check pdf_core provider tools tests main.py
.venv/bin/ruff format --check pdf_core provider tools tests main.py
.local-bin/dify plugin package . -o dist/pdf_text_pages-0.1.6.difypkg
```

[CODE0.1.6](docs/CANDIDATE_CODE_SHA256-0.1.6.txt)、[BUILD_RECORD0.1.6](dist/BUILD_RECORD-0.1.6.json)、[SOURCE0.1.6](dist/SOURCE_SHA256-0.1.6.txt)で同一candidateを識別。全旧packages/records/r2保全と既存未trackedを保持。versionのみ0.1.6、meta0.1.0/minDify1.17.1/SDK0.10.2は不変。0.1.6の実Dify混在順/元bytes/metadata/LLM直結・精度、新規導入/更新/T13/T15は未実施です。同じ最終packageの通常更新→同Chatflowで混在入力を再実行するcheckpointへ延期し、環境変更/ログ提出を要求しません。原T07/T08–10/T11返却途中/T12/T14等、独立reviewとroot全体受入は残ります。

## 0.1.5の履歴：既存file base→内部APIの同path/query取得

ユーザーがexact0.1.4 SHA433c7fe42f624871eb38301fe69940d521e02644004e21dadfd1711a238a87e0導入/PDF1件でCONNECT_ECONNREFUSED scheme=https/address_kind=publicを観測。これは接続拒否factで、公開配信先へDockerから届かない推定は支持されますがactualenv対応/根本原因は未確定です。顧客Dify環境設定を変更しない条件で、独立既存file origin/routeから独立既存DIFY_INNER_API_URLへ同じrawpath/queryで取得する0.1.5候補です。実機修復成立/独立reviewは未実施。

必要最小の既存AllowedSource内private targetだけ、元URL validator共用。新subclass/role/診断機能は採りません。公開側DNS/connect fallbackなし。INTERNAL_FILES等のdirectとsameorigin prefixは旧意味を維持し、API不要なdirectでは余分な検査をしません。origin変更時の外basepath空/inner rootに限定、外末尾/→//filesやnonrootは通信前CONFIGで適合未確認を示し、strip/addprefix/guess/default/PLUGIN alias/設定変更へ逃がしません。targetに旧DNSsnapshot/peer/Host/SNI/TLS/byte/期限/proxyredirect保護を適用、signaturequery非改変/非露出。empty0/listonly/core singlewrap/依存/DPI/limitsは不変。

mapping16cases red11failed+5passed/1.06s→16passed/1.04s（診断を含む中間）。trailing外slashは1failed/0.05sのred後CONFIGへ修正。中間focused88passed/12warnings/16.84s。その後最新簡素化でRuntimeSource/role/base診断と診断testを取り下げ、final exact suiteは**138 passed / 12 warnings / 25.08s、exit0、required_now**。[新test log](docs/phase7-test-results-0.1.5.txt)。ruff check成功、format18files成功。古いfull/中間診断成功をfinal証拠へ転用しません。元safe_failure形式で、新しい診断設定はありません。

固定source（研究担当2026-10-05）：[compose解決済DIFY_INNER_API_URL](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/docker/docker-compose.yaml#L600)→[daemon環境継承](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/internal/core/local_runtime/subprocess.go#L35-L45)。PLUGIN_DIFY_INNER_API_URLはcompose補間入力で、plugin aliasの根拠ではありません。[upload署名](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/app/workflow/file_runtime.py#L142-L155)、[tool署名](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/tools/signature.py#L76-L89)はoriginをpayloadに含まず、同path/queryと[upload検証route](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/controllers/files/upload_file_delivery.py#L99-L129)/[tool route](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/controllers/files/tool_files.py#L29-L55)に対応。sourceからactual設定/到達/CA/署名成功を推論しません。

[CODE0.1.5](docs/CANDIDATE_CODE_SHA256-0.1.5.txt)、[BUILD_RECORD0.1.5](dist/BUILD_RECORD-0.1.5.json)、[SOURCE0.1.5](dist/SOURCE_SHA256-0.1.5.txt)でversion/source/payload/hashを識別。全oldpkg/records/r2patch/archiveを保持、r2SDKadapter不採用。new/update/T13/T15は同じ最終0.1.5package、最小実機操作は通常更新→同flow/PDF再実行のみで設定操作/log提出を要求しません。原F2 T07/T08–10/T11返却途中/T12/T14等と未review/実機empty/単一UI/通信/LLM直結は保持し、full成功をtask全体完了にしません。

## 0.1.4の履歴（新candidate成功へ流用しない）

ユーザーが旧Chatflow側の問題で無応答だったと判明し、新しいChatflowでplugin invokeへ到達しました。このfactに基づき0.1.3-r2 SDK adapterは不採用とし、0.1.2package SHA d7b48f71e1f26d28b40855fa28aa866209f121fb52adad6ebd3e635dc5e5a353の160payload bytesへ復帰してから変更しました。mainは旧Plugin、SDK adapter/exit74/新lifecycle testsを本candidateへ含めません。

復帰前に0.1.2→r2の10変更/10new files全てをtask-scoped r2-source.patchへ保存し、一時copyのbase+gitapply replayで170r2payload byte一致を確認。patch SHA b5090c896cb043e4836c43ef24b085bab45f2d8a5d8f3709e3cddc225b3e2279。20entryはr2-preservedへ実体保存しARCHIVE_MANIFESTに元path/hash/move/copyを記録。oldall packages/recordsと原HANDOFFを保持、移動はuser explicit可逆restoreのownedr2-only範囲に限定、未知/他owner/env/cache/venv/distを削除・移動していません。

最新user要求「リストが空でも正常に動作」「単一PDFパラメータいらない」に従いpdf_file宣言/runtime branchを廃止してpdf_filesのみへ。0件はmissing/None/list[]をearly判定しtext空/noBLOB/BatchRecord既存schema documents=[] JSONを返し、limits/source/DPI/slot/fetch/convertを呼びません。非list falsy値はempty扱いせず、1件以上のLimits→source→DPI→normalize順と全page/入力順/重複/空本文/取得安全は0.1.2のままです。旧pdf_file設定者はpdf_filesへ同じFile変数を選び直す必要があり、このuser採用影響をREADMEへ明記しました。

TDDfreshbase：empty/configskip/宣言は4failed+3passed/2warnings/0.66s→7passed/2warnings/0.55s。既存single/list/both testはDifycast後一要素list/複数/同一File重複のone-list契約へ必要変更のみ。focused empty/fetch/authは71passed/12warnings/15.84s。exact plugin full suiteは**required_now、122 passed / 12 warnings / 23.96s、exit0**。[新test log](docs/phase6-test-results-0.1.4.txt)を保持。ruff check成功、format17files成功。旧r2の123や0.1.2の116を新candidate成功へ流用しません。SDK warningsは実daemon互換保証ではありません。

```bash
.venv/bin/python -m pytest tests/test_empty_input.py --tb=short
.venv/bin/python -m pytest tests/test_empty_input.py tests/test_fetch_adapter.py tests/test_auth_sources.py --tb=short
.venv/bin/python -m pytest --tb=short > docs/phase6-test-results-0.1.4.txt 2>&1
.venv/bin/ruff check pdf_core provider tools tests main.py
.venv/bin/ruff format --check pdf_core provider tools tests main.py
.local-bin/dify plugin package . -o dist/pdf_text_pages-0.1.4-r2.difypkg
```

### 単一File選択と空filesの固定source（2026-10-05研究担当から受領）

- [Dify1.17.1 selector](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/web/app/components/workflow/nodes/_base/components/form-input-item.helpers.ts#L157-L165)：file/files両方でFile/Array[File]変数を許可。
- [core invoke cast](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/tools/__base/tool.py#L49-L96)、[FILES cast](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/plugin/entities/parameters.py#L193-L196)：nonlistを一要素listへ、list[]はそのまま。[converter](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/plugin/utils/converter.py#L7-L13)→[SDK0.10.2 list dict/File変換](https://github.com/langgenius/dify-plugin-sdks/blob/3345471536c6a438884ac4942a2425b6627567f9/src/dify_plugin/interfaces/tool/tool.py#L261-L276)。pluginはstrict list受入を維持し、singleを独自coerceしません。
- [Graphon0.7.0初期files](https://github.com/langgenius/graphon/blob/11e2dee8cbd6dc2e6bf1c2059d9bbf4d0437ebe5/src/graphon/nodes/tool/tool_node.py#L48-L54)、[成功outputs](https://github.com/langgenius/graphon/blob/11e2dee8cbd6dc2e6bf1c2059d9bbf4d0437ebe5/src/graphon/nodes/tool/tool_node.py#L295-L303)：state.files初期[]→ArrayFileSegment。TEXT空+JSONだけ/no file-producing messageのlocal証拠から標準files[]へのsource裏づけ。target実測とは分けます。

原T01の単一File/リスト化不要はsource上pdf_filesで保持可能、実UI未測です。旧pdf_file入口と二口併用T04は最新user指示で廃止した投影。一listの順序/重複/対応と混同せず、原HANDOFF本文は変更していません。0件の通常LLMチャット/0.1.4更新・正規PDF直結・全受入は未実機。独立reviewも窓口の別未実行gateです。

[0.1.4 code manifest](docs/CANDIDATE_CODE_SHA256-0.1.4.txt)、[BUILD_RECORD-0.1.4.json](dist/BUILD_RECORD-0.1.4-r2.json)、[SOURCE_SHA256-0.1.4.txt](dist/SOURCE_SHA256-0.1.4-r2.txt)で同source/payload/version/hashを識別し、newinstall/update/T13/T15はこの同一最終packageを使います。F2は新flow解決/invoke到達factだけ更新し、T01の実UI、T07表示、T08–T10精度、T11返却途中、T12targetlimits、T14運用/回復、T13通信/T15直結等の未実施を保持します。

## 0.1.2の履歴（新candidateの試験結果へ転用しない）

ユーザーはSHA `60e36662c10b150f50f43ceccfdc315e93418b8f47426df00a7c3e3d1c7db478`の0.1.1を導入して同じChatflowを実行し、`pdf_files[0]: FETCH_FAILURE: acquisition failed`を観測しました。これはinvoke到達と入力取得失敗のfactです。CONFIGではないため何らかの独立したbaseを得た推論は支持されますが、target設定/到達先/原因は未確認。認証UI表示有無も未確認です。「出力先の問題」という所感はhypothesisで、codeではfetchが本文/画像の変換・出力構築より前です。

今回の実装は一回のtrusted host DNSsnapshot内で、connect失敗時だけ次IPへ接続する修正と、秘密を含まない段階診断です。IPv6first→IPv4listenerの旧失敗をローカルで再現し修正しましたが、target原因の確定ではありません。scheme/host/port/path、IP固定/peer/TLS、redirect/proxy、実byte/累積期限を維持し、別DNS/origin、URLrewrite、推測defaultへfallbackしません。peer/TLS/HTTP送信後の再試行はありません。deps、DPI、limits、認証schemaとmeta.version0.1.0/minimum Dify1.17.1は不変、plugin/projectのみ0.1.2です。

SDK0.10.2を最初にimportしたgeventgreenletから、実sys.executableのisolated stdlib DNSchildを起動し、stdlib/Docker名解決ともworkspaceで成功しました。[局所再現結果](docs/phase3-local-reproduction-0.1.2.json)はhost/IP値を出さず、patch状態/起動可否/解決familyだけを記録します。targetdaemonの起動保証ではなく『SDKpatchなら必ずDNSchild失敗』という仮説の反証です。greenlet内の不存在executable起動はDNS_LAUNCH_ENOENTを実際に確認しています。環境/コンテナ/導入/実機は変更していません。

TDD: 最初の12case redは0.58s（snapshot mockのkwargs受入を直した後の有効redは13failed/3warnings/1.15s）。最小修復後13passed/4warnings/1.14s、HTTP/send/bodyと同snapshot安全境界追加後の取得近接82passed/12warnings/16.49s。DNSエラーの必要な下位分類を追加したredは6failed+4passed/11deselected/0.63s、修復後diagnostics21passed/4warnings/1.18s。

exact candidate plugin full suiteは**required_now、116 passed / 12 warnings / 24.06s、exit0**。[新test log](docs/phase3-test-results-0.1.2.txt)へ保持。ruff check成功、format checkは16files成功。旧95/67成功はそれぞれの過去候補の証拠。codefreeze後の文書のみの編集に同じ候補の成功を再利用します。SDKのlate monkey patch/Pydantic/multithread fork warningsは対象環境互換性を検証した証拠ではありません。

```bash
.venv/bin/python -m pytest tests/test_fetch_diagnostics.py --tb=short
.venv/bin/python -m pytest tests/test_auth_sources.py tests/test_fetch_diagnostics.py tests/test_fetch_adapter.py --tb=short
.venv/bin/python -m pytest tests/test_fetch_diagnostics.py -k dns_failures --tb=short
.venv/bin/python -m pytest --tb=short > docs/phase3-test-results-0.1.2.txt 2>&1
.venv/bin/ruff check pdf_core provider tools tests main.py
.venv/bin/ruff format --check pdf_core provider tools tests main.py
.local-bin/dify plugin package . -o dist/pdf_text_pages-0.1.2.difypkg
```

[0.1.2 code candidate](docs/CANDIDATE_CODE_SHA256-0.1.2.txt)、[BUILD_RECORD-0.1.2.json](dist/BUILD_RECORD-0.1.2.json)、[SOURCE_SHA256-0.1.2.txt](dist/SOURCE_SHA256-0.1.2.txt)で新版のsource/package対応を識別します。旧0.1.0/0.1.1 packages/全records/過去test証跡は保持します。旧0.1.1のreview approveを新candidate approvalへ流用しません。独立reviewは窓口が別sessionでadmitする未実行gateです。

[段階コードと限界](docs/FETCH_DIAGNOSTICS.md)はDNSlaunch/lookup/child/response、限定errno、peer/TLS、HTTPsend/response/bodyを分けます。表示はschemeと解決したIPの粗い分類のみで、DNS未解決時address_kindはunknown。元例外str/repr/host/IP/署名query/設定値を表示しません。ユーザーの手順は同一0.1.2への通常更新と同じChatflowの再実行だけ。新config、ホストコマンド、ログ提出、credential削除を依頼しません。

対象Dify1.17.1は窓口w1:pBのヘッダー観測fact、actualdaemon/env継承/core設定一致/個別DNS/CAはunknown。今回研究担当が固定1.17.1sourceを確認した範囲では、[公式env template](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/docker/.env.example#L16-L24)と[shared template](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/docker/shared.env.example#L9-L10)は内部サービス名の配信base例/空のprimary設定例で、loopback defaultを支持しません。templateの値を実環境へ移植しません。[compose API](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/docker/docker-compose.yaml#L8-L68)と[daemon](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/docker/docker-compose.yaml#L573-L600)のenv/network、[daemon launcher](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/internal/core/local_runtime/subprocess.go#L25-L45)、[SDK gevent patch](https://github.com/langgenius/dify-plugin-sdks/blob/3345471536c6a438884ac4942a2425b6627567f9/src/dify_plugin/_gevent.py#L4)はlocal再現条件を支持するだけです。API専用override不一致なら通常FETCH_DENIEDなので、それだけで今回のgenericFETCH_FAILUREを説明したとは扱いません。

F1: 新規導入/通常更新/T13/T15は同一最終0.1.2packageで確認する未実施checkpoint。F2: 原受入全体のT01–T06 UI、T07表示、T08–T10LLM精度、T11送信途中、T12対象limit/enforcement、T14daemon運用、T13到達/信頼/機密とT15直結、認証UI/newupdate、I3–I9候補は保持。旧実機導入/invoke到達を正規取得/本文画像出力/LLM理解の成功へ昇格しません。

## 0.1.1の履歴（修復時の候補・下記を0.1.2の検証へ転用しない）

対象Dify installed版1.17.1は窓口の2026-10-05応答ヘッダー観測（X-Version: 1.17.1 / X-Env: PRODUCTION）で確認済みです。実plugin環境の設定継承・core解決値との一致・実daemon版はunknownで、実機導入時に判定します。公式1.17.1 composeのdaemon0.6.10-localは実環境の版保証ではありません。

plugin versionは0.1.1、author/nameは不変です。daemon0.6.10のidentifierはauthor/name:version@checksumなので、認証修復の同一ソース候補を旧0.1.0と識別するpatch版を選びました。meta.version0.1.0はmanifest仕様版で不変です。最低Dify宣言を1.17.1へ合わせた理由は、今回依拠するプラグインFile URL生成・設定の意味が1.10.0とは異なるためです。対象1.17.1に追加のDify更新を要求せず、その他版本の互換性は未検証です。Python/SDK/PDF依存/制限/DPIは変更していません。

空credentials schema、資格情報なしinvoke、旧credentialを削除せず無視する処理、独立したpresence-aware既存設定、内部baseで両route、通信前不足/不適合拒否と日本語エラー、有界DNS子/固定IP/peer照合を実装しました。入力URLでpolicyを作らず、任意URL・推測default・URL書換えを使いません。

TDD証拠: 新規認証境界19件のbaselineは19 failed（0.66s）、alias/empty追加後22 failed（0.60s）。explicit port0の境界追加は2 failed + 5 passed（0.65s）、Noneだけ既定portにする修正後に成功。認証近接24 passed（0.82s）、取得近接37 passed（14.56s）、追加integrationを含む認証/取得近接65 passed（15.93s）。fixture移行中の2失敗はredirect handlerと旧IPv6 path期待を元の意味へ戻して解消しました。

exact候補のplugin full suiteは**required_now、95 passed / 10 warnings / 23.26s、exit0**。証拠は[auth-repair-test-results-0.1.1.txt](docs/auth-repair-test-results-0.1.1.txt)、コード候補hashは[0.1.1 code manifest](docs/CANDIDATE_CODE_SHA256-0.1.1.txt)へ保存します。ruff check成功、format checkは15files成功。SDK由来gevent/Pydantic/multithread fork warningsは旧版同様、対象daemonの互換性確認へ昇格しません。

```bash
.venv/bin/python -m pytest tests/test_auth_sources.py --tb=short
.venv/bin/python -m pytest tests/test_auth_sources.py tests/test_fetch_adapter.py --tb=short
.venv/bin/python -m pytest --tb=short > docs/auth-repair-test-results-0.1.1.txt 2>&1
.venv/bin/ruff check pdf_core provider tools tests main.py
.venv/bin/ruff format --check pdf_core provider tools tests main.py
.local-bin/dify plugin package . -o dist/pdf_text_pages-0.1.1.difypkg
```

0.1.1のpackage/source対応は[BUILD_RECORD-0.1.1.json](dist/BUILD_RECORD-0.1.1.json)、source manifestは[新source hash](dist/SOURCE_SHA256-0.1.1.txt)へ保存します。旧0.1.0 package/BUILD_RECORD/SOURCE_SHA256と67件成功の証拠は保持し、新候補の成功へ流用しません。新規導入/通常更新/T13/T15は同一0.1.1 packageで[画面確認checkpoint](docs/LIVE_TESTS.md)へ明示的に延期します。配布物作成だけを認証修復の実機成立やtask全体完了とは扱いません。

実機未実施: 認証なしUI、新規導入/0.1.0通常更新と旧認証状態、設定継承/core対応/正規配信/DNSnetwork/CA、T13、T15、下の原受入表のT01–T06 UI、T07表示、T08–T10精度、T11送信途中、T12対象limit/enforcement、T14daemon運用。I3–I9の未検証候補を保持します。独立reviewは窓口が別sessionで手配する未実行gateであり、leafが合格と宣言しません。ホストコマンド・新env・認証JSON・credential削除でunknownを解決済みにしません。

### 1.17.1固定sourceの確認

2026-10-05に窓口の有限研究担当が確認し本leafへ渡した一次情報です。対象の設定一致・実機成功を証明する資料ではありません。

- [Dify provider](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/tools/builtin_tool/provider.py#L131-L166): 非空schemaでAPI_KEY/need_credentials。[plugin provider](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/tools/plugin_tool/provider.py#L11)は継承。
- [graphon0.7.0 File](https://github.com/langgenius/graphon/blob/11e2dee8cbd6dc2e6bf1c2059d9bbf4d0437ebe5/src/graphon/file/models.py#L202-L214): to_plugin_parameterはfor_external=False。[Dify file_runtime](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/app/workflow/file_runtime.py#L64-L161): upload/tool/datasourceの全plugin入力がINTERNAL_FILES_URL or FILES_URL、REMOTE_URLは素通し。[bind_file_uri](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/core/tools/signature.py#L13-L50): raw base+route。末尾slashを除去するvalidatorは確認されず、二重slashも元baseのまま照合。
- [Dify aliases](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/configs/feature/__init__.py#L419-L435)、[pydantic-settings2.14.2 default](https://github.com/pydantic/pydantic-settings/blob/d703bd717e5e07439fa89da2245eee6139413e9e/pydantic_settings/main.py#L573)、[env lookup](https://github.com/pydantic/pydantic-settings/blob/d703bd717e5e07439fa89da2245eee6139413e9e/pydantic_settings/sources/providers/env.py#L90-L94): primary存在時は空でもaliasへ戻らず、absent時だけ既存alias。
- [compose API](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/docker/docker-compose.yaml#L8-L68)、[daemon](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/docker/docker-compose.yaml#L573-L600): shared.env+.env、API専用api.env、公式daemon0.6.10-local。[daemon subprocess](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/internal/core/local_runtime/subprocess.go#L35-L45): daemon環境継承。[core設定補完](https://github.com/langgenius/dify/blob/8387590ace4a094de812b7847fc6a4c3a27cd52b/api/configs/app_config.py#L104-L117): remote/dotenv/TOMLとplugin環境の解決一致は別途確認。
- [plugin identifier](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/pkg/entities/plugin_entities/identity.go#L13-L45)、[update](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/internal/service/install_plugin.go#L183-L228): version/checksumで更新候補を識別。[SDK meta.version](https://github.com/langgenius/dify-plugin-sdks/blob/3345471536c6a438884ac4942a2425b6627567f9/src/dify_plugin/core/entities/plugin/setup.py#L175-L185): manifest仕様版。

## 0.1.0の履歴（修復前・下記を新候補の検証と混同しない）

実行環境のUTC時計とセッション提示日は異なりました。実コマンドの確認日は**2026-10-04 UTC**、セッション提示current_dateは2026-10-05です。検査の日時根拠は[docs/test-results.txt](docs/test-results.txt)、[docs/audit-run.txt](docs/audit-run.txt)とdist package recordのUTC値です。

## 環境・候補

- repo: `/home/devuser/workspace/dify_plugins`、branch: `feat/pdf-text-pages`、clone base: `3fcfc4fa0d6cc1e9485f775a8dfff7cc12125bc3`。commit/push/PRを実行していません。既存workspace変更へ触れていません。
- plugin: `app/pdf_text_pages`、version0.1.0、Linux x86_64、Python3.12.15、SDK0.10.2、pypdfium2 5.14.0、PDFium156.0.8076.0、Pillow12.3.0。
- CLI: official dify-plugin-daemon release0.6.10 linux-amd64、`version`出力v0.6.10、binary SHA256 `0cef74bcae375a4337c2ff7d42e4787717981a795e1c23cf56bb27ec07ec8304`。
- code candidate: [docs/CANDIDATE_CODE_SHA256.txt](docs/CANDIDATE_CODE_SHA256.txt)。検証後のsource/package整合は[dist/BUILD_RECORD.json](dist/BUILD_RECORD.json)とSOURCE_SHA256.txtへ記録。
- 原handoff: workspace元と`docs/DIFY_PDF_PLUGIN_HANDOFF.md`コピーを両方保持。両者SHA256 `8eadb6987a376d5eeabb50f2e917825fb68f7cd824216c22a8d735007536ed74`、本文を変更していません。

## 実行コマンドと証拠

```bash
uv sync --frozen
uv run pytest --tb=short
uv run ruff check pdf_core provider tools tests main.py
uv run ruff format --check pdf_core provider tools tests main.py
uv run pip-audit -r requirements.txt --format json -o docs/pip-audit.json
uv run python -c 'import main'
.local-bin/dify plugin package . -o dist/pdf_text_pages-0.1.0.difypkg
sha256sum dist/pdf_text_pages-0.1.0.difypkg
```

`import main`はSDKによるmanifest/provider/tool registrationの正常初期化を確認しました。`.env`が配置された後に実行する場合はremote接続を試行するので、これは初期ローカル環境で得た証拠です。キーを読み出すcommandは実行しません。

full regression分類は**plugin full suiteをrequired_now**として実行しています。新規pluginの通信/入力/変換/資源/SDK出力境界を対象にし、shared入口を変更しない無関係の既存plugin suiteはnot_applicableです。Dify直接接続/LLM受入は`docs/LIVE_TESTS.md`の同一最終difypkg検証checkpointへ明示的にdeferredとし、ローカル完了を実機完了とは呼びません。

独立code reviewで、PNG単体file-size値が本文を含む内部JSONにも適用される不具合を修復しました。本文約100800文字/小PNG/全明示budget内のPDFを処理でき、真正PNG超過を引き続き拒否する回帰を追加しています。

最終pytestは**67 passed, 8 warnings in 22.10s**（exit_code0）、詳細は`docs/test-results.txt`を参照してください。ruff check/format checkは成功。pip-auditはruntime37 dependencies、既知Python advisory0件（2026-10-04T16:59:21Z〜16:59:29Z）。native PDFiumの全CVE不存在を示すものではありません。

SDK0.10.2由来のgevent late monkey-patch、Pydantic旧config形式、multithread fork warningsをpytestで観測しました。tests中のHTTPserver/SSL先行importとの組合せで発生しています。productionではmainでSDKを先にimportし、native処理はexec後専用childだけで逐次実行します。warningsを顧客daemonでの互換検証済みという主張へ変換せず、導入環境で確認してください。テストの終了後にowned native childは残りませんでした。

## 受入条件への対応

| ID | ローカルで得た証拠 | 実機未実施 |
|---|---|---|
| T01 | 固定SDK single dict→File、adapter TEXT/PNG BLOB/JSON | UI単一File割当、LLM直接接続 |
| T02/T03 | list dict→list[File]、順序と全page/ID/画像位置 | sys.files/任意list UI割当 |
| T04/T05 | single先頭+list元順、同名/同一PDFの重複を独立docに保持 | 実UI操作 |
| T06 | 4page mixedの本文/画像-only/blank/日本語、空本文2pageを保持 | モデル解釈 |
| T07 | 日本語文字抽出、横長/90度回転、独立renderとの元page body pixel一致、label追加余白pixel一致 | 顧客資料/モデル縮小挙動 |
| T08/T09/T10 | ALPHA右矢印/BETA左矢印fixtureと期待値、768px縮小label人間視認 | LLM入力trace/回答採点、画像順入替え精度 |
| T11 | corrupt/encrypted、native text/render injected failureが位置付きerror、部分成功なし、秘密非露出 | Dify返却途中通信障害時のnode failure |
| T12 | file/inputbyte/page/DPI/幅/高さ/画素/outputbyte/textの閾値前/同値/後、actual byte cap、deadline/memory failure | daemon enforced memoryとDify/LLM最大量適合 |
| T13 | allowlist/path/userinfo/port/scheme/encoding拒否、HTTPredirect/proxy無効、TLS SNI/Host/hostname検証、署名query非露出、slow-drip headers cumulative deadline | 正規File配信先/認証方式 |
| T14 | timeout/実memory exit/TERM無視child→KILL/reap/temp cleanup/後続正常、cross-process BUSY/recovery、output中slot保持 | replica間daemon総parallelism、突然host停止後運用 |
| T15 | 標準TEXT/BLOB/JSONを生成、利用者追加変換なしの設計 | 同一difypkg→標準LLM text/files直結 |

## 合成fixtureと可視確認

`tests/fixtures.py`がReportLab4.4.10/Pillowで合成PDFを作成します。ReportLabは開発依存でproduction requirementsへ含めません。`docs/samples/mixed.pdf`は4page、`beta.pdf`は1pageです。期待値は`docs/LIVE_TESTS.md`にあります。初期fixtureでは両矢印が右でしたが、T08の異なる図という要件へ合わせてBETAだけ左へ変更しました。この変更はテスト/サンプルの意味に限定しproduction code candidateを変更していません。

`docs/samples/page-*.png`は150DPI、`page-*-768.png`は幅768pxへ縮小した可視sampleです。`label-768.png`を実際に開き、`BC6EDBE57C9374F2B9BFA3207365DCD3D-D001-P0001`を全文読み取れました。回転日本語page4も可視確認しました。これは人間によるローカル縮小視認の証拠で、LLM認識結果ではありません。sample metadataは非機密生成結果だけを含みます。

## 現環境の到達確認と残り

DNS `dify`→172.18.0.2、HTTP80 GET `/`は307（同host `/auth/refresh`）、`/console/api/setup`と`/console/api/system-features`は200。HTTPS443、dify5002/5003はConnectionRefused、`plugin_daemon`/`plugin-daemon`はDNS解決不可。資格情報/cookie/機密response本文は表示しません。`/console/api/version?current_version=1.10.0`はversion1.16.1を返しましたが、installed版でなく更新情報の可能性があるため顧客installed版はunknownです。

ユーザーが管理画面debug host:portを確認し、ローカル`.env`へkeyを設定する協力を申し出ています。debug daemon socketと正規file-source allowlistが解消されれば、許可された検証workspaceでLIVE_TESTSへ進められます。本開発ではDify本番設定/版の更新、OpenAI呼出し、顧客資料入力は実施していません。

パッケージはCLIのignore挙動に合わせて`.env*`をすべて除外し、秘密値空欄templateを`config/debug-env.example`にも保存して同梱します。source repoの`.env.example`は保持しています。
