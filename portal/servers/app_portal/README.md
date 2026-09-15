# App Portal (`servers/app_portal`)

OpenCode が作成した Web アプリ（および手動登録した任意のアプリ）のレジストリと、
各アプリにピン留めされた OpenCode セッションへフィードバックを配送する仕組み。

## 全体像

```
[SPA #/apps] ─admin Bearer─> [servers/app_portal] ─> PostgreSQL
                                    │                 (app_portal_web_apps,
                                    │                  app_portal_feedback,
                                    │                  app_portal_bridges)
                                    │ feedback 保存後 enqueue_command
                                    ▼
                      [control-plane コマンド基盤 (既存)]
                                    ▲  WS(outbound) claim / result
                                    │
                     [portal-opencode-bridge]  (OpenCode ホストで常駐)
                                    │  opencode serve API
                                    ▼
                              [OpenCode セッション]
```

- 配送は **control-plane のデバイス／コマンドチャネルを流用**する。bridge は
  通常の control-plane デバイスとして登録し、`opencode.*` オペレーションを提供する。
- フィードバック送信は `require_admin_device`（admin デバイス）のみ。
- セッションは**ピン留め必須**（`opencode_session_id`）。

## データモデル

- `app_portal_web_apps`: slug / name / description / url / project_directory /
  opencode_session_id / bridge_device_id / source / tags / status
- `app_portal_feedback`: app_id / body / kind / status(pending|delivered|failed) /
  command_id / target_session_id / webui_url / delivered_at / error
- `app_portal_bridges`: device_id / hostname / webui_base_url / server_key / last_seen

## API (`/api/app-portal`)

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| GET | `/apps` | デバイス | 一覧 |
| POST | `/apps` | デバイス | 登録 |
| GET | `/apps/{slug}` | デバイス | 詳細（feedback 込み） |
| PATCH | `/apps/{slug}` | admin | 更新 |
| DELETE | `/apps/{slug}` | admin | 削除 |
| POST | `/apps/{slug}/feedback` | admin | 送信（コマンド enqueue） |
| GET | `/feedback` | admin | 横断一覧 |
| POST | `/feedback/{id}/refresh` | admin | 配送状態を再取得 |
| POST | `/bridges/announce` | デバイス | WebUI base URL 登録 |
| GET | `/bridges` | admin | bridge 一覧 |

`webui_url` は `{webui_base_url}/server/{server_key}/session/{session_id}`。
`server_key = base64url(webui_base_url)`（OpenCode WebUI の実装に一致）。

## アプリ設定の変更

登録済みアプリの設定（名前・説明・URL・directory・session・bridge・タグ・status）は
次の 2 通りで変更できる。

- WebUI: `#/apps/{slug}` の「設定」フォーム → 保存（`PATCH /api/app-portal/apps/{slug}`）
- CLI:
  ```bash
  portal-manage --config <cfg> app-portal update-app --slug <slug> \
    [--name ...] [--description ...] [--url ...] [--directory ...] \
    [--session-id ...] [--bridge-device-id ...] [--status active|archived] \
    [--tag a --tag b]
  ```
  指定したフィールドのみ更新される（slug は不変）。

## CLI

- `app-portal list-apps` — 一覧
- `app-portal register-app --name ... --directory ... --session-id ...` — 手動登録
- `app-portal update-app --slug ... [--name ...] ...` — 設定変更
- `app-portal delete-app --slug ...` — 削除
- `app-portal list-feedback [--app-slug ...]` — フィードバック一覧
- `app-portal list-bridges` — bridge 一覧

## bridge (`portal-opencode-bridge`)

OpenCode が動くマシンで常駐させる。control-plane の bootstrap token で登録する。

```bash
portal-opencode-bridge \
  --server-url http://<portal-host>:8000 \
  --bootstrap-token <token> \
  --credentials-file /var/lib/portal-opencode-bridge/credentials.json \
  --opencode-url http://127.0.0.1:12000 \
  --webui-base-url http://127.0.0.1:12000
```

- bootstrap token は**初回登録のみ**必要。登録後は `--credentials-file` に bearer token が
  保存され、以降の再起動はキャッシュを再利用する（token の再発行は不要）。
- `--bootstrap-token-file <path>` でトークンをファイルから読むこともできる（argv 露出を避ける）。

提供オペレーション:

- `opencode.feedback` — セッションへ prompt を非同期注入（`POST /session/{id}/prompt_async`）し deep link を返す
- `opencode.list_sessions` — ディレクトリでフィルタしたセッション一覧
- `opencode.webui_url` — WebUI base URL / server_key を返す

`--webui-base-url` はブラウザから到達可能な URL を指定する（リモート閲覧なら
tailscale 名など）。

### systemd unit 例

```ini
[Unit]
Description=Portal OpenCode bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=syoch
StateDirectory=portal-opencode-bridge
ExecStart=%h/.nix-profile/bin/portal-opencode-bridge \
  --server-url https://portal.syoch.org \
  --bootstrap-token-file /etc/nixos/portal-opencode-bridge.token \
  --credentials-file /var/lib/portal-opencode-bridge/credentials.json \
  --opencode-url http://127.0.0.1:12000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

bootstrap token は `python3 manage.py --config <cfg> control issue-bootstrap-token
--device-id opencode-bridge --display-name "OpenCode Bridge"` で発行する。

syoch-nix (NixOS) には `services.portal-opencode-bridge` モジュール（dotfiles
`components/host/syoch-nix/portal-bridge.nix`）があり、bootstrap token は sops
secret `portal-opencode-bridge-token` から供給される。

## OpenCode 自動登録ツール

`portal/integrations/opencode/app_portal.ts` を `~/.config/opencode/tools/app_portal.ts`
に配置する（dotfiles/home-manager 経由）。環境変数:

- `PORTAL_APP_URL` — ポータルの base URL
- `PORTAL_APP_TOKEN` — control-plane デバイスの Bearer トークン（`tk_...`）

エージェントは `app_portal_register` ツールで、`ctx.worktree` と `ctx.sessionID` を
添えてアプリを登録できる。

## 有効化

ポータル設定 `config.json` の `extensions` に追加:

```json
{
  "module": "servers.app_portal",
  "class": "AppPortalExtension",
  "config": { "bridge_device_id": "opencode-bridge" }
}
```

`app_portal` は control-plane を配送に使うため、`ControlPlaneExtension` を
併せてロードする必要がある。

## テスト

- `portal/tests/backend/test_app_portal.py` — REST + 配送フロー（bridge 結果は
  DB でシミュレート）
- `portal/tests/backend/test_app_portal_bridge.py` — fake OpenCode サーバに対する
  bridge のユニットテスト
