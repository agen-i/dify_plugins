# 選定と一次資料の記録

確認日2026-10-04 UTC。顧客installed版は確認できていません。選定は要件を満たす最小試行で具体化し、原handoffの合意済み入出力/全page保持/一体record契約を変更していません。

| 選定 | 根拠・実測 | 影響と未確認 |
|---|---|---|
| 名前pdf_text_pages、app/pdf_text_pages配置 | 既存repoのapp/<plugin>配置、用途が分かるprovider名 | 既存pluginやroot依存を変更しない |
| dify-plugin 0.10.2 | PyPI公開版を固定installし、FileとToolのコード、SDK registration/実messageを観測 | 実Dify/daemon版との互換は実機未確認 |
| pypdfium2 5.14.0 | 同じPDFium処理でpage text/render、4page mixed試行成功 | OCRを追加しない。PDFium156.0.8076.0とwheel noticesを保持 |
| Pillow 12.3.0 | PNG canvas/labelを追加、元page外pixel一致、回転日本語/縮小sample確認 | 同梱Aileron subsetのCC0許諾を確認。外部font/binaryのruntime downloadなし |
| 150 DPI、PNG、上余白80px/32px label | 少量A4/横長/回転で欠落なし。768px幅縮小labelを人間可視確認 | LLMが識別できる精度はT08–T10へ留保 |
| UUID4 full32hex batch prefix | 標準random UUID、入力順D/physical P、batch内unique検査 | 122bit randomで極低衝突確率。グローバル永続登録はしない |
| limits初期値 | 150DPI少量試行と資源境界失敗/復旧から保守的に選定 | 顧客daemon/model最大量の保証値ではない。管理者が適合確認 |
| pinned-IP downloader | File.blobのunbounded取得不足を補う。Host/SNI保持、proxy/redirectなし、actual byte/time cap | provider管理allowlistが必須。正規source IP/port/path unknownは導入時解消 |
| 専用逐次child+flock | PDFium同process複数thread同時呼出し禁止とnative停止可能性を守る | Linuxのみamd64を宣言。processはnetwork/filesystem sandboxではない |
| official CLI 0.6.10 | release binary version確認、quick initとpackage実行成功 | 顧客daemon installと同一difypkgの実機検証は別checkpoint |

## 固定SDKコードの観測

固定wheelの`dify_plugin/file/file.py`は未取得`File.blob`で`httpx.get(...).content`を使うため、実装はURL取得を独自にbounded化しています。`interfaces/tool/tool.py:Tool._convert_parameters`はDify identityのdictをFileへ、listの各dictをFileへ変換します。single/list/both経路をそのSDK関数で変換してtool adapterを実行しています。

`create_text_message`はTEXT、`create_blob_message(bytes, meta)`はBLOB、`create_json_message(Mapping|list)`はJSONです。本実装は1 TEXT、全pageのBLOB、1 dict JSONを構築します。SDKでJSON message内`json_object`がdictであることを確認しています。Dify標準変数のjson集約型をSDKだけから断定しません。

固定SDKは`Tool.__init__`でresponse_typeを設定し、`from_credentials`で正常初期化できます。実fixture adapter testはこの公的helperを使います。`main`のPluginRegistrationはprovider/tool/manifestを読み、導入定義を正常初期化しました。公式CLIでpayloadを生成するだけの確認より隣接したSDK検証です。

## 一次資料

- [Dify Tool Plugin](https://docs.dify.ai/en/develop-plugin/dev-guides-and-walkthroughs/tool-plugin): Python3.12、file/files宣言型、標準開発/package手順。
- [Dify Tool Return](https://docs.dify.ai/en/develop-plugin/features-and-specs/plugin-types/tool): text/files/json標準変数、TEXT/BLOB/JSON helpers、image/png MIME metadata。
- [SDK公式repo](https://github.com/langgenius/dify-plugin-sdks)、[PyPI 0.10.2](https://pypi.org/project/dify-plugin/0.10.2/): source locatorと固定wheel。採用wheelの実コードを上記観測に用いた。
- [Dify file transformerの公式code snapshot](https://github.com/langgenius/dify/blob/70ef9cbd5d3f1c6d209de14ca23354a908b0eaae/api/core/tools/utils/message_transformer.py): BLOB処理でmetaのmime_type/filenameを使いtool fileへ保存する。これは公開sourceの根拠で、顧客installed版の観測ではない。
- [Dify debugging](https://docs.dify.ai/en/develop-plugin/features-and-specs/plugin-types/remote-debug-a-plugin): host:portとworkspace key、remote env。固定SDKconfig/plugin.pyのparserでも確認。
- [CLI 0.6.10公式release](https://github.com/langgenius/dify-plugin-daemon/releases/tag/0.6.10): linux-amd64 executableを使用、local-binに保持、配布payloadから除外。
- [pypdfium2公式repo](https://github.com/pypdfium2-team/pypdfium2)、[Python API](https://pypdfium2.readthedocs.io/en/stable/python_api.html)、[固定PyPI 5.14.0](https://pypi.org/project/pypdfium2/5.14.0/): render/text/close/thread制約、wheel noticesの必要性。
- [PDFium upstream](https://pdfium.googlesource.com/pdfium/)、[PDFium binaries](https://github.com/bblanchon/pdfium-binaries): native release/noticeと更新追跡。固定wheel version.jsonは156.0.8076.0、origin pdfium-binaries。
- [Pillow releases](https://pillow.readthedocs.io/en/stable/releasenotes/index.html)、[固定PyPI12.3.0](https://pypi.org/project/Pillow/12.3.0/): PNG/font/canvas。wheel license全文を保持。
- [Aileron designer公式](https://dotcolon.net/fonts/aileron): curl取得したpage JSON-LD licenseはCC0。Pillow固定ImageFont.pyはAileron subset使用を明記。
- [OpenAI images/vision](https://developers.openai.com/api/docs/guides/images-vision): filename/metadataに依存せず、画像内pixel IDで照合する理由と縮小に関する限界。APIをプラグインから呼ぶ設計ではない。

HTTP probeの`/console/api/version?current_version=1.10.0`でversion1.16.1を観測しましたが、API意味上latest/update情報かもしれず、顧客installed版へ昇格しません。HTTP reachabilityとremote debug socket reachabilityも分けて記録しました。
