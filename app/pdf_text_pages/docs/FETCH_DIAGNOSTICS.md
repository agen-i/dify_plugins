# 取得失敗の安全な診断（0.1.2）

表示例は`FETCH_FAILURE: CONNECT_ECONNREFUSED; scheme=http; address_kind=private`です。URL・host/IPそのもの・署名query・設定値・元例外str/reprは出しません。stageと限定errno/DNS種別だけを使い、一般的な例外型名や任意の例外文をコピーしません。通常ログは追加していません。

| コード | 判別できる事実と内部の次判断 |
|---|---|
| DNS_SOURCE | 内部設定の固定IP検証で失敗。値は非表示 |
| DNS_LAUNCH_ENOENT/EACCES等 | DNS子の起動失敗。存在/実行権限等の固定errno。hostname lookup失敗とは分ける |
| DNS_LOOKUP_EAI_NONAME | resolverが名前/サービスを解決できなかった。対象名や設定が何かは非表示・未確定 |
| DNS_LOOKUP_EAI_AGAIN | 一時的な名前解決失敗。恒久的な設定誤りと断定しない |
| DNS_LOOKUP_EAI_FAIL/OTHER | 名前解決失敗/その他のOSError。個別resolver原因は未確定 |
| DNS_CHILD_EXIT_n/SIGNAL_n/OTHER | 子の標準出力処理前の非0終了/シグナル。nはexit1–255またはsignal1–64だけ。stderrは非表示 |
| DNS_RESPONSE | 子のJSONが不適合・空・有効IPでない。取得先へ接続していない |
| CONNECT_ECONNREFUSED/ENETUNREACH/EHOSTUNREACH/TIMEOUT等 | 同一snapshot内で接続できなかった。限定errno以外はOSERROR/UNKNOWN。HTTP応答や出力返却の失敗とは分ける |
| PEER_CHECK | 実peer情報の取得/検査の例外。peer不一致そのものは従来のFETCH_DENIEDで拒否 |
| TLS_INIT/TLS_HANDSHAKE/TLS_VERIFY | TLS準備/handshake/証明書検証の失敗。証明書本文やverify_messageは非表示。個別のCA/期限/hostname要因は未確定 |
| HTTP_SEND/HTTP_RESPONSE/HTTP_BODY | request構築/送信、応答解析、body読取の失敗段階。応答本文/詳細は非表示 |

schemeは承認設定のhttp/httpsのみです。address_kindは接続対象として選んだIPをloopback/private/publicに分類したもので、host/IPの値を公開せず、配信元の正当性や実daemonの構成を証明しません。DNSが未解決ならunknownで、hostnameからloopback等を推測しません。非0childのcodeは許容整数だけに限定します。

既存のFETCH_DENIED、FETCH_HTTP、FETCH_TIMEOUT、LIMIT等は維持します。HTTP非200はFETCH_HTTP（redirect追従なし）、取得の累積期限超過はFETCH_TIMEOUT、実byte超過はLIMITです。idle2秒・取得/要求期限とbyte上限は変更していません。

一回の承認host DNSsnapshotの複数IPを取得中に固定し、接続失敗時だけ次IPを試します。別host/別origin/再DNS/default/URL書換えを使わず、同じscheme/host/port/path、期限、Host/SNI/TLS/peer条件を維持します。peer/TLS失敗やHTTP送信後は再試行しません。これでローカル再現した先頭IPのみの失敗経路を閉じますが、0.1.1実機エラーの原因と一致する証拠はありません。

ユーザーの操作は0.1.2へ更新して同じChatflowを再実行するだけです。ホストコマンド・ログ提出・新しい配信設定・credential削除を要求しません。窓口が段階コードを内部採否の証拠として扱い、単一のstageから対象構成や根本原因が全て確定したと扱わず、他の利用可能な内部経路を比較して継続します。
