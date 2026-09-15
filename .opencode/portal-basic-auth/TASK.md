# Task: Obtainium 向け Bypass パスへの Basic Auth 適用

**Status**: TODO
**担当**: portal 作成エージェント (この文書の指示に従って実装)
**関連**: `cloudflare-access` skill, `portal-architecture` skill, `nixos/portal-service.nix`

---

## 背景

### 発見された問題 (ペネトレーションテスト 2026-08-09/10)

`portal.syoch.org` は Cloudflare Access で全体が保護されているが、Obtainium
(Android のヘッドレス APK 取得) のために以下のパスが CF Access の Bypass 対象
になっている:

| パス | 用途 | 状態 |
|------|------|------|
| `/scrape-index.html` | Obtainium HTML ソースのスクレイピングインデックス | **認証なしで公開** (APK インベントリ漏洩) |
| `/api/apps/download/{apk_id}/{filename}` | APK ファイル配信 | **認証なしでダウンロード可能** (実測 47MB 取得成功) |
| `/obtainium-export.json` | Obtainium エクスポート JSON | 現状は CF Access 保護中 (302) |

この Bypass により:

1. **APK バイナリが誰でもダウンロード可能** — 配信しているアプリ (GameGuardian 等) の
   バイナリを認証なしで取得できる
2. **`/scrape-index.html` で全アプリのインベントリ (アプリ名・パッケージ ID・バージョン) が漏洩**

### 方針決定

- **CF Access (ログイン型) の適用はしない** — Obtainium はヘッドレスでログイン/MFA を
  踏めず、機能停止するため
- **nginx レベルで Basic Auth を適用する** — Obtainium は URL に `user:pass@` を
  埋め込む形で Basic Auth に対応しているため、そのまま動作する
- **NixOS module の設定で Basic Auth を構成する** — 手動で nginx をいじるのではなく、
  module のオプションとして定義する

---

## 実装内容

### 1. NixOS module (`nixos/portal-service.nix`)

`services.syoch-portal` に Basic Auth 用のオプションを追加する。

```nix
basicAuth = {
  enable = mkEnableOption "HTTP Basic Auth for Obtainium bypass paths";
  htpasswdFile = mkOption {
    type = types.nullOr types.path;
    default = null;
    description = "Path to an htpasswd file (e.g. from a sops secret) with the Obtainium credentials.";
  };
  protectedPaths = mkOption {
    type = types.listOf types.str;
    default = [
      "/scrape-index.html"
      "/api/apps/download"
    ];
    description = "Nginx location prefixes to protect with Basic Auth. Paths must match how the portal serves them.";
  };
};
```

- `enable = true` かつ `htpasswdFile` が設定されている場合のみ、nginx 設定を
  生成する
- 実際の nginx vhost は `dotfiles` 側 (`components/host/sv01/services/portal.nix`)
  で宣言されるため、module 側は「Basic Auth を有効化するためのフラグと
  設定値を提供する」設計とする

### 2. nginx vhost (`dotfiles/components/host/sv01/services/portal.nix`)

`portal.syoch.org` の vhost で、`cfg.services.syoch-portal.basicAuth.protectedPaths`
に該当する location に `auth_basic` を設定する。

```nix
locations."= /scrape-index.html" = {
  proxyPass = "http://127.0.0.1:8000";
  extraConfig = ''
    auth_basic "Obtainium";
    auth_basic_user_file /etc/nginx/obtainium.htpasswd;
  '';
};
locations."/api/apps/download/" = {
  proxyPass = "http://127.0.0.1:8000";
  extraConfig = ''
    auth_basic "Obtainium";
    auth_basic_user_file /etc/nginx/obtainium.htpasswd;
  '';
};
```

- `htpasswdFile` は sops secret (`sops.secrets."obtainium-htpasswd"`) から
  `/etc/nginx/obtainium.htpasswd` に配置し、nginx が読めるパーミッションにする
- `obtainium-export.json` は現状 CF Access 保護中 (302)。もし Obtainium が
  export JSON も取得するなら、同じ Basic Auth を適用するか、方針を確認する

### 3. sops secret の追加 (`components/host/sv01/secrets.yaml` 等)

```yaml
obtainium-htpasswd: !ENC ... # htpasswd 形式 (user:hash) の内容
```

生成例 (エージェントが秘密鍵を持つ側で実行):

```bash
htpasswd -nb obtainium '<generated-password>'
```

### 4. Obtainium 側の URL 設定 (利用者側)

Obtainium のアプリ URL / HTML ソース URL を:

```
https://portal.syoch.org/scrape-index.html
```
から
```
https://obtainium:<password>@portal.syoch.org/scrape-index.html
```

に変更する。同様に APK ダウンロード URL (`/api/apps/download/...`) にも
`user:pass@` を含める。詳しくは `obtainium-import` skill を参照。

---

## 検証項目 (テスト要件)

Basic Auth 適用後に以下の確認を行う:

| # | 検証 | 期待結果 |
|---|------|----------|
| 1 | `curl https://portal.syoch.org/scrape-index.html` (認証なし) | **401** |
| 2 | `curl -u obtainium:<pass> https://portal.syoch.org/scrape-index.html` | **200** (HTML) |
| 3 | `curl https://portal.syoch.org/api/apps/download/1/<filename>` (認証なし) | **401** |
| 4 | `curl -u obtainium:<pass> https://portal.syoch.org/api/apps/download/1/<filename>` | **200** (APK) |
| 5 | CF Access 保護パス (`/api/apps`, `/api/backup`, `/openapi.json`) | 変わらず **302** |
| 6 | `/api/control/*` | 変わらず **401** (Bearer 認証) |
| 7 | Obtainium 実機で実際にアプリ取得が通る (URL に user:pass を埋め込んだ状態) | 成功 |

### テストコマンド例

```bash
# 認証なし → 401 を期待
curl -i https://portal.syoch.org/scrape-index.html | head -20

# 認証あり → 200 を期待
curl -i -u 'obtainium:password' https://portal.syoch.org/scrape-index.html | head -20
```

---

## 注意事項

1. **Basic Auth は平文のパスワードを送る** — 必ず HTTPS (CF Access / nginx TLS) 経由
   であること。既に HTTPS なので問題ないが、Basic Auth 単体は暗号化しない点に注意。
2. **認証情報の強度** — `obtainium:<password>` はパスワード生成して使い回さないこと。
   認証情報を知る端末だけが APK を取得できる状態にするのが目的。
3. **nginx の location 順序** — `/api/apps/download/` の prefix が `/api/` など他の
   location より先にマッチするよう定義する。nginx は最長 prefix マッチなので、
   原則 `download/` が優先されるが、`= /scrape-index.html` (完全一致) と
   `/api/apps/download/` (prefix) の使い分けに注意。
4. **module と dotfiles の責務分担** — module (`portal-service.nix`) はオプションと
   nginx 生成ロジックを提供し、dotfiles 側は secret の配布と vhost での利用を
   宣言する。どちらか一方に閉じ込めない。
5. **`obtainium-export.json` の方針** — 現在 302 (CF Access 保護) のため、このまま
   Basic Auth と併用する場合は、Export は CF Access のログインが要る状態になる。
   運用上、Export の取得も Basic Auth に統一すべきかは別途判断する。

---

## 成果物

- [ ] `nixos/portal-service.nix` に `basicAuth` オプション追加
- [ ] `dotfiles` 側 vhost に `auth_basic` location 追加
- [ ] sops secret `obtainium-htpasswd` 追加
- [ ] 上記 検証項目 1-7 がすべて通ること
