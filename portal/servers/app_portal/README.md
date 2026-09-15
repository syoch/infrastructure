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

## bridge (`portal-opencode-bridge`)

OpenCode が動くマシンで常駐させる。control-plane の bootstrap token で登録する。

```bash
portal-opencode-bridge \
  --server-url http://<portal-host>:8000 \
  --bootstrap-token <token> \
  --opencode-url http://127.0.0.1:12000 \
  --webui-base-url http://127.0.0.1:12000
```

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
After=network.target

[Service]
ExecStart=%h/.nix-profile/bin/portal-opencode-bridge \
  --server-url https://portal.syoch.org \
  --bootstrap-token %h/.config/portal-opencode-bridge.token \
  --opencode-url http://127.0.0.1:12000
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

bootstrap token は `python3 manage.py --config <cfg> control issue-bootstrap-token
--device-id opencode-bridge --display-name "OpenCode Bridge"` で発行する。

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
