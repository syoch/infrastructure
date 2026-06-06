# Phase 6: Bridge

## 概要

`bridge.py` プロセスを作成し、portal サーバと同じマシンで動かす。
この bridge は「`acl.*` / `device_admin.*` という operation 群を提供する普通の device」として振る舞い、
結果として portal 自身が自分の管理操作を self-hosting する (dogfooding)。

## ファイル

| ファイル | 役割 |
|---------|------|
| `portal/servers/control_plane/bridge.py` | bridge 本体。bootstrap トークンでデバイス登録 → WS 接続 → 8 ops advertise |
| `portal/pyproject.toml` | `portal-control-bridge` を `[project.scripts]` に追加 |
| `portal/default.nix` | `websockets` を propagatedBuildInputs に追加 |
| `nixos/portal-service.nix` | `syoch-portal-bridge.service` を追加 (オプションで有効化) |

## Bridge 仕様

### 起動

```bash
portal-control-bridge \
  --server-url http://127.0.0.1:8000 \
  --bootstrap-token <token> \
  --config /var/lib/syoch-portal/config.json
```

- 起動時に `POST /devices/register` を `device_id="bridge"` で実行
- レスポンスの `bearer_token` を保持し、WS 接続時の認証に使用
- 登録後、`operations_register` で 8 ops を advertise
- WebSocket が切断されたら自動再接続 (exponential backoff、最大 30s)

### 提供する operations

| ID | 動作 | 必要な権限 |
|----|------|-----------|
| `acl.list` | `portal-manage control list-acl` | (なし) |
| `acl.create` | `portal-manage control grant --source --target --operation [--extra]` | なし (CLI 側で不要) |
| `acl.update` | `revoke` + `grant` (replace) | なし |
| `acl.delete` | `portal-manage control revoke --acl-id` | なし |
| `device.list` | `portal-manage control list-devices` | なし |
| `device.rename` | `portal-manage control rename-device --device-id --display-name` | なし |
| `device.set_admin` | `set-admin` / `clear-admin` | なし |
| `device.delete` | `portal-manage control delete-device --device-id` | なし |

注意: bridge 自体は ACL でガードしない (admin の代わりに bridge を信頼)。
つまり、bridge に command を送れる = admin と同等。
これは single-user 環境を前提とした設計。

### Claim/Result フロー

1. server から `command` メッセージ受信
2. 直ちに `claim` を返す (`claim_token` 一致確認は server 側)
3. サブプロセスで `portal-manage control ...` を実行 (タイムアウト 30s)
4. 結果を `result` メッセージで送信 (`succeeded` / `failed`)

### 提供する ops は "dogfood" である理由

server 自身が直接 `acl.create` を処理してもよいが、
その場合:
- server に admin ロジック (「特別扱い」) が混ざる
- ACL の評価時に「自分自身は常に許可」みたいな例外処理が必要
- テスト時にモック化が困難

bridge を別 device にすることで、server から見ると「acl.create を発行した一般 device」と
「acl.create を提供している一般 device」が別デバイスで、
すべての権限評価が一貫した ACL ロジックで処理される。

## systemd ユニット (NixOS)

`nixos/portal-service.nix` に追加:

```nix
services.syoch-portal.bridge = {
  enable = true;
  bootstrapTokenFile = /run/secrets/portal-bridge-token;  # agenix / sops で管理
  serverUrl = "http://127.0.0.1:8000";
};
```

`syoch-portal-bridge.service`:
- `requires = [ "syoch-portal.service" ]`
- `Restart = always`, `RestartSec = 5`
- `User = syoch-portal`
- `ExecStart = portal-control-bridge --server-url <...> --bootstrap-token $(cat <...>) --config <...>`

## トークン管理

Bridge が再起動するたびに再登録が必要になるのを避けるため、bootstrap トークンは使い回せないが、
bridge 専用の bootstrap トークンを事前に発行し、それを agenix / sops で暗号化して保存する運用を推奨。

```bash
# 一度だけ実行: サーバ側
portal-manage control issue-bootstrap-token --device-id bridge --display-name "Portal Bridge" --ttl-minutes 0
# → 表示されたトークンを secret manager に保存
```

ttl-minutes=0 で無期限発行 (内部的には token を永続化) できるかは要確認。
現状の manager_cli は `--ttl-minutes 15` デフォルト。
無期限が必要なら `manager_cli.py` に `ttl_minutes=0` → `expires_at=None` のような対応を追加する。

## 進捗

- [x] bridge.py
- [x] pyproject.toml entry_point
- [x] nix package deps
- [x] NixOS systemd unit
- [x] import チェック
- [ ] 統合テスト (E2E or scripted)

## 動作確認 (manual)

1. サーバ起動 (`nix develop -c make dev-server` or systemd)
2. 別ターミナルで bootstrap トークン発行:
   ```
   portal-manage control issue-bootstrap-token --device-id bridge --display-name "Bridge"
   ```
3. `portal-control-bridge --server-url http://127.0.0.1:8000 --bootstrap-token <token> --config <path>` 起動
4. 別ターミナルで `portal-manage control list-operations` → bridge 由来の ops が表示される
5. WebUI (`#/control`) で acl.create ボタン押下 → フォーム送信 → コマンドが bridge に push → claim/result → 一覧に反映
