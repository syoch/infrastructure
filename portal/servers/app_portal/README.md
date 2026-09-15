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
                     [portal-device-agent]  (OpenCode ホストで常駐・汎用)
                                    │  設定で定義した shell コマンドを実行
                                    │  opencode.* は portal-opencode-tool を呼ぶ
                                    ▼
                        [OpenCode ホストのローカル処理]
```

- **デバイスごとに汎用 `portal-device-agent` を 1 プロセス**常駐させる。opencode 専用の
  実行ファイルは持たず、OpenCode 操作は agent の設定に定義した custom operation として
  薄いヘルパー CLI (`portal-opencode-tool`) を呼ぶ。
- agent は `traits.opencode-bridge` operation を広告し、opencode 操作のキーと WebUI 情報を
  返す。ポータルはこれを**発見（discovery）**して使うため、operation キーをハードコードしない。
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

## Device agent + OpenCode helper

OpenCode が動くマシンでは汎用 `portal-device-agent` を常駐させ、opencode 操作を
custom operation として定義する。opencode 固有の処理は `portal-opencode-tool`
（ヘルパー CLI）が担う。

### `portal-opencode-tool`

```
portal-opencode-tool [--opencode-url URL] [--webui-base-url URL] <command>
  feedback --session-id <id> --prompt <text>   セッションへ prompt を非同期注入し {"session_id","webui_url"} を stdout に出力
  list-sessions [--directory <dir>]            セッション一覧
  webui-url                                    {"webui_base_url","server_key"}
  traits                                       {"operations": {role: op_id}, "webui_base_url", "server_key"}
```

- `--opencode-url`（env `OPENCODE_URL`、既定 `http://127.0.0.1:12000`）
- `--webui-base-url`（env `OPENCODE_WEBUI_BASE_URL`、既定は opencode-url。ブラウザから
  到達可能な URL を指定する）
- 出力は JSON。device agent は `result.stdout` として返し、ポータルがパースする。

### `traits.opencode-bridge`

role→operation キーの対応と WebUI 情報を返す:

```json
{
  "trait": "opencode-bridge",
  "operations": {
    "feedback": "opencode.feedback",
    "list_sessions": "opencode.list_sessions",
    "webui_url": "opencode.webui_url"
  },
  "keys": ["opencode.feedback", "opencode.list_sessions", "opencode.webui_url"],
  "webui_base_url": "http://127.0.0.1:12000",
  "server_key": "aHR0cDovLzEyNy4wLjAuMToxMjAwMA"
}
```

ポータルは対象デバイスの `traits.opencode-bridge` を実行してキーを解決・キャッシュし、
WebUI 情報を `app_portal_bridges` に保存する（`bridges/announce` は後方互換のため残置）。

### device agent config 例

```json
{
  "device_id": "opencode-bridge",
  "display_name": "OpenCode Bridge",
  "server_url": "https://portal.syoch.org",
  "bootstrap_token_file": "/etc/nixos/portal-opencode-bridge.token",
  "credentials_file": "/var/lib/portal-device-agent/credentials.json",
  "operations": [
    { "id": "opencode.feedback", "group": "opencode", "name": "Send Feedback",
      "command": ["portal-opencode-tool", "feedback", "--session-id", "{session_id}", "--prompt", "{prompt}"],
      "params_schema": { "type": "object", "properties": { "session_id": {"type":"string"}, "prompt": {"type":"string","ui_hint":{"widget":"textarea"}} } } },
    { "id": "opencode.list_sessions", "group": "opencode", "name": "List Sessions",
      "command": ["portal-opencode-tool", "list-sessions", "--directory", "{directory}"],
      "params_schema": { "type": "object", "properties": { "directory": {"type":"string"} } } },
    { "id": "opencode.webui_url", "group": "opencode", "name": "WebUI URL",
      "command": ["portal-opencode-tool", "webui-url"],
      "params_schema": { "type": "object", "properties": {} } },
    { "id": "traits.opencode-bridge", "group": "opencode", "name": "Traits",
      "command": ["portal-opencode-tool", "traits"],
      "params_schema": { "type": "object", "properties": {} } },
    { "id": "sys.dpms_toggle", "group": "system", "name": "Toggle DPMS",
      "command": ["hyprctl", "dispatch", "dpms", "toggle"],
      "params_schema": { "type": "object", "properties": {} },
      "ui_hint": { "kind": "button", "label": "Toggle DPMS" } }
  ]
}
```

bootstrap token は `python3 manage.py --config <cfg> control issue-bootstrap-token
--device-id opencode-bridge --display-name "OpenCode Bridge"` で発行する（初回登録のみ。
以降は `credentials_file` に保存された bearer token を再利用する）。

syoch-nix (NixOS) では `services.portal-device-agent` モジュール（dotfiles
`components/host/syoch-nix/portal-device-agent.nix`）が設定を生成して起動する。
bootstrap token は sops secret `portal-opencode-bridge-token` から供給される。

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

- `portal/tests/backend/test_app_portal.py` — REST + 配送フロー（コマンド結果は DB でシミュレート）
- `portal/tests/backend/test_opencode_tool.py` — fake OpenCode サーバに対する `OpenCodeOps` / ヘルパー CLI のテスト
- `portal/tests/backend/test_app_portal_delivery_e2e.py` — portal + 汎用 device agent + ヘルパー CLI の配送統合テスト
