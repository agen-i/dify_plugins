# 安全性・導入運用

基準記録: 2026-10-04 UTC。認証修復の対象source確認日: 2026-10-05。実装とローカル試験の事実を記録し、顧客環境での安全認定を意味しません。

## 通信と権限

入力ファイル0件のempty pathは通信/変換を行わず、配信設定・DPI・limits検査を開始しません。1件以上はPDF以外も同じ安全取得経路を使います。

プラグインはOpenAI/LLM/外部変換サービスを呼ばず、APIキーを要求しません。入力取得はDify SDK `File`だけを受け付け、URL/path文字列を拒否します。SDK `File.blob`は`httpx.get(...).content`で未bounded取得するので使いません。

1件以上ではProvider credentials schemaを空にし、入力URL・旧資格情報JSONを許可先のsourceにしません。既存環境設定のpresence-aware別名を解決し、`INTERNAL_FILES_URL or FILES_URL`の一つのbaseでアップロード・tool/datasource由来の両download routeを許可します。詳細は[README](README.md)参照。必要なscheme/host/port/base path/routeだけを受け付け、不足・不適合は通信前の日本語CONFIGエラーです。値やURLは出しません。入力URLからのallowlist生成、推測default、追加認証/必須設定fallbackはありません。0.1.5は既存の管理設定で対応する二つのbaseに限り、承認file origin/routeから独立既存内部APIbaseへ同path/query取得を対応付けます。他のURL書換えは行いません。旧JSON例・load_sources関数は過去の書式/固定IPテストのため保持しますが、invokeの許可設定には使用しません。

承認設定のhostだけをisolated Python子プロセスでDNS解決します。取得の累積期限をsubprocess timeoutへ渡し、期限超過では子をkill/waitで回収します。一回の解決結果をsnapshotとして当該取得へ固定し、接続失敗時だけそのsnapshot内の次IPを同じ累積期限で試します。各失敗socketをcloseし、別host/別DNS/URLrewriteへ進みません。peer/TLS検証失敗やHTTP送信後の再試行はしません。成功IPについて、hostnameを再解決せずliteral IP socketへ接続し、TLS前後でpeer IP/portを照合します。私設IPは管理下Dify配信に必要な場合を許容します。resolver/networkの信頼・coreの解決済み配信設定との対応は導入時の成立条件であり、環境値だけで確認済みとはしません。設定不一致は任意URL許可で回避しません。

HTTP HostとHTTPS SNIは承認hostを保持し、標準CA/hostname検証を必須とします。TLS不一致を安全な`FETCH_FAILURE`へ置換します。redirectは一切追従せず環境proxyを使いません。DNS/接続/TLS/header/bodyは同じ取得期限内で処理し、slow-drip headerで期限を伸ばしません。既存のsocket idle wait最大2秒は変更していません。遅い正規配信への適合は未検証です。

ポート/host/path境界、userinfo、fragment、encoded/double-encoded traversalやseparator、制御文字を検査します。申告size/Content-Lengthを信用せず、実受信byteを数え、上限+1byteで拒否します。URL/query/レスポンス詳細/元例外はユーザーエラーへ伝播しません。入力取得に未知の資格情報ヘッダーを追加する機能はありません。正規配信が別の認証方式を必要とする場合は導入前に方式を確認する必要があります。

対応付けは既存AllowedSourceの内部target情報だけを使用し、旧JSON設定面へ新inputfieldを追加しません。内部API設定が不足/不適合なら値を出さず通信前CONFIG、外部connect fallbackなし。origin変更時のnonroot/外部末尾slashは対応未確認として拒否、directの既存prefixは保持します。

manifestのDify invocation permissionsは`{}`です。tool/LLM/app/storage/endpointを呼ぶ権限は不要です。`{}`はOSネットワークの禁止やsandboxを意味しません。管理者はplugin-daemonのegressも正規配信IP/portへ制限できます。debug時にはremote install socketへの追加通信が必要です。

## ログ・保存

実装は通常ログを出しません。公開エラーには分類、入力口/index、必要時physical pageを入れ、設定不足・不適合のCONFIGでは設定名と管理者の確認事項も示します。FETCH_FAILUREでは固定の段階コード、限定errno/DNS種別、http/https、loopback/private/public/unknownの分類だけを示します。child起動前/解決失敗時のaddress_kindはunknownです。元例外str/repr/host/IP/query/設定値を伝えません。値は出さず、本文/PNG/元filename/File URL/credentialsを入れません。native childのstdout/stderrはDEVNULLです。エラーチェーンは秘密を含む外部例外を露出しないよう抑制します。

入力/生成PNG/本文recordは実行固有の`/tmp/pdf-text-pages-<uid>/run-*`（0700）へ保存し、入力名をpathへ使いません。正常終了、例外、owned child timeout/terminate/killではparentがchildをreap後に自身のTemporaryDirectoryをcleanupします。lock fileは小さな固定数の同期用fileで、資料データを含まず再利用します。temp rootはsymlink/owner/permissionを検査し、lockはNOFOLLOWで開きます。

Linux parent-death signalはparentの突然の終了時にchildを停止しますが、parentそのものがSIGKILL/ホスト停止した場合のtemp削除を保証しません。運用では専用container tmpfs/ephemeral volumeを使い、停止を確認後にこのプラグイン専用volumeを管理者の保存/削除方針に従って処置してください。agentは他実行や所有不明のtempを自動削除しません。process分離はネットワーク/ファイルシステムsandboxではありません。

Dify実行履歴/出力ファイルは別の保存面です。Dify管理者がworkspace閲覧権限、保持期間、バックアップ、削除を定め、出力本文/画像の保存を説明してください。後続OpenAI LLMからの本文/画像外部送信は別途顧客承認事項です。

元ファイル返却はbytesを加工せず、元Fileのfilename/MIMEを保持します。PDF内部ページの連番は変更せず、JSONのimage_indexだけ混在files位置へ補正します。入力件数上限は全形式、ページ上限はPDFのみです。出力件数は既存のPDF総ページ上限と入力件数上限の和以内で、後続モデルの対応形式/最大量は別途の実機受入条件です。

## 初期処理上限

すべて`Limits`を唯一の正本とし、実行開始時に管理環境`PDF_TEXT_PAGES_LIMITS`を検証してimmutable値へ固定します。PDFやDify tool入力で上限を変えません。DPIだけは利用者指定できますが管理上限以内に検証します。

| 上限 | 初期値 | 保護する時点 |
|---|---:|---|
| file数 | 5 | 正規化前/後 |
| input単体/総byte | 10/25 MiB | 申告値、実取得中、child前 |
| PDF単体/総page数 | 20/30 | PDF open直後 |
| DPI | 既定150、最大200、最低36 | render前 |
| PNG幅/高さ（余白込み） | 各5000px | render確保前と実raster確認 |
| PNG総画素（余白込み、1画像） | 16,000,000 | render確保前 |
| 出力単体/総byte（PNGと元ファイル） | 8/40 MiB | PNG encode中/生成中、元ファイル取得後と全出力準備前 |
| 完成text/抽出本文総文字数 | 1,000,000 | 抽出前/中、整形後 |
| 1 file取得 | 20s | header/bodyを含む累積deadline |
| native処理 | 60s | child wall timeout、CPU limit |
| request全体 | 100s | 全入力取得→child残時間→出力直前/各yield |
| child address space | 1 GiB | native import前RLIMIT_AS |
| 同時変換/返却 | 1 | cross-process flock slot、返却終了まで保持 |
| daemon宣言メモリ | 2 GiB | manifest、実際のenforcementは顧客daemon確認 |

5files/30pages等は少量150DPI試行から選んだ保守的な**初期仮説**であり、顧客Dify/LLMの対応可能最大量を実測した値ではありません。ローカル合成4page×2doc、約100KiB/4画像の通常例と各境界を検証しました。管理者は顧客daemonの実メモリ、実File storage、標準tool出力上限、モデルの画像数/サイズ/入力長を確認して上限を下げるか、資源増加と再検証を行ってください。manifest memory宣言だけで親processメモリが必ず制限されるとは説明しません。

OSのfile-size上限はPNG単体値と、本文文字数×最大JSON escape量・実request metadata・page overheadから導く内部JSON最大量の大きい側へ設定します。PNG単体の実上限は別途encode中のBoundedPNGで厳守し、本文が多い合法PDFを内部JSONサイズの別条件で拒否しません。

native PDFiumは専用childだけで逐次呼び出し、同process複数threadから同時に実行しません。parentはflockで同じruntime volume/uid上の複数processも制限します。別container/host間の総数はdaemonのreplica/resource制約で管理します。slotが満杯なら`BUSY`で即時失敗し、無限待ちを作りません。childが応答しなければowned process groupへTERM、0.25s後も生存すればKILL、waitでreapします。memory limitでnative import/処理が失敗した後も正常requestが成功することを確認しました。

入力と出力のbufferはbyte上限内で保持し、全変換・整合性・message構築の成功前にyieldしません。返却中の通信停止はSDK/daemonのtimeoutにも依存します。100s deadlineは各yield前に検査しますが、callerがgeneratorを再開しない時間はPython側から実行できず、daemon request timeout120sとgenerator終了を顧客環境で確認する必要があります。SDKが入力JSONをプラグインへ渡す以前の巨大payload制限はDify/plugin-daemonの責任面です。

## 依存・license・脆弱性

主依存: dify-plugin 0.10.2（Apache-2.0）、pypdfium2 5.14.0（複合許諾: wheelのApache/BSD/CC-BY notices参照）、同梱PDFium 156.0.8076.0（BSDとthird-party notices）、Pillow 12.3.0（MIT-CMUと同梱third-party notices）、default label font Aileron subset（designer公式CC0）。本プラグイン本体はrepo既存MIT licenseを保持します。判断は各固定wheelのlicense本文に戻れるよう[third_party](third_party/INDEX.md)へcopyしました。PDFium wheelのBUILD_LICENSES一式、Pillow含有library notices、Aileron CC0本文を同梱します。依存binaryはdifypkgへ直接コピーせず、hash付きrequirementsで導入します。

2026-10-04 UTCに`uv run pip-audit -r requirements.txt --format json -o docs/pip-audit.json`を実行し、runtime dependency37件で既知Python advisoryは0件でした。この結果は照会時点/対象databaseの範囲であり、native PDFiumの全CVE/未知脆弱性が存在しない保証ではありません。PDFium upstream releaseとsecurity updatesは[一次資料](docs/DEPENDENCIES.md)から追跡し、顧客は定期的に固定版を再検査してください。

更新時はrequirements/uv.lockを一緒に更新し、wheel内notice/同梱PDFium版、pip-audit、合成PDFのfull suite、Dify直接接続試験を再実施し、版を増やしてofficial CLIで再package/SHA256を記録します。依存やSDKを自動でfloating upgradeしません。パッケージのhashとsource整合確認はdistのmanifestを参照してください。
