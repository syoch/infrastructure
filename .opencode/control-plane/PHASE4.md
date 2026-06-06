# Phase 4: Nginx WS / SSE reverse proxy

## 概要

`portal.syoch.org` の nginx 設定 (dotfiles リポジトリ `components/host/sv01/default.nix` 配下) に、WebSocket と SSE のためのヘッダ・タイムアウト設定を追加する。
本リポジトリでは nginx 設定を持たないが、必要な設定値をリファレンスとして本ファイルにまとめる。

## 必要な nginx 設定

`/api/control/` 配下の location ブロックに対し、以下のヘッダとタイムアウトを付与する:

```nginx
location /api/control/ {
    proxy_pass http://127.0.0.1:8000;  # portal uvicorn ワーカー

    # ---- Standard reverse proxy headers ----
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # ---- WebSocket upgrade (Phase 3) ----
    # 接続直後の Upgrade ヘッダで 101 Switching Protocols に切り替える
    proxy_http_version 1.1;
    proxy_set_header Upgrade    $http_upgrade;
    proxy_set_header Connection "upgrade";

    # ---- Timeouts ----
    # WS は長時間 idle する (ping 間隔 30s) ため read timeout を長めに
    proxy_connect_timeout 5s;
    proxy_send_timeout    60s;
    proxy_read_timeout    600s;   # 10 分
    send_timeout          600s;

    # ---- Buffering 無効化 (SSE で必要) ----
    proxy_buffering off;
    proxy_request_buffering off;
    add_header X-Accel-Buffering no;

    # ---- TLS (Cloudflare 背後) ----
    proxy_ssl_server_name on;
}
```

## 理由

### `proxy_http_version 1.1` + `Upgrade` / `Connection`
- WebSocket は HTTP/1.1 Upgrade ベース。1.0 では接続が切り替わらない
- `$http_upgrade` が空 (通常の HTTP リクエスト) の場合、`Connection: close` 相当として扱われる
- WS 接続が `Connection: upgrade` で来ると、nginx は 101 を返して tunnel モードに遷移

### `proxy_read_timeout 600s`
- デフォルト 60s では、idle な WS 接続が 60s で切断される
- サーバ側の `_handle_ping` を使う (Phase 3) ことで実質無制限だが、安全弁として 10 分

### `proxy_buffering off`
- SSE は連続的なストリーム。nginx の buffering を有効にするとイベントが遅延・バッチングされる
- Cloudflare 背後では `X-Accel-Buffering: no` ヘッダも必須 (CF は response buffering を独自に行う)

### `X-Forwarded-Proto`
- portal 内部で `request.url.scheme` を見る場合に `https` を正しく伝えるため

## dotfiles 側の実装 (要対応)

dotfiles `components/host/sv01/default.nix` の `portal.syoch.org` vhost 内の `location /api/` ブロックに上記を追加する。
nginx 設定の location は `/api/` でまとめられている (Phase 3 WS/SSE 以外も含む) ため、path マッチは `/api/control/` に限定して書くと安全。

## 進捗

- [x] PHASE4.md
- [ ] dotfiles リポジトリへ PR (本リポジトリ外)

## 検証

- 端末で `wscat -c wss://portal.syoch.org/api/control/devices/<id>/ws?token=<tk>` を実行し、welcome メッセージが返ること
- ブラウザ DevTools の Network タブで `/api/control/events` (SSE) の response headers に `Content-Type: text/event-stream` が見えること
