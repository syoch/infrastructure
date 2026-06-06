# Control Plane: 作業ログ・試験方法・完了基準

## 概要

Portal に Control Plane 拡張を追加する作業の記録。WebUI/CLI 経由でデバイスを一元管理し、デバイスが advertise する operation (UI 付き) を統一的に dispatch する。

## 設計サマリ

- **dogfooding**: サーバは operation provider にならず、bridge プロセスが `portal-manage control` を subprocess で実行して ACL/デバイス管理を担う
- **デバイス対等**: `Device.kind` 列なし、全デバイス同じスキーマ。`Authorization: Bearer <token>` で認証
- **ACL default-deny**: 該当 ACL が無いと 403
- **first-webui-device**: `is_first_webui_device=True` のデバイスのみ server-side 管理 operation (acl.*, device_admin.*) が見える
- **operation = first-class entity**: OperationSpec テーブル、JSON Schema + ui_hint で WebUI が自動レンダリング
- **正規表現一致**: `source_device` / `target_device` は `device:<regex>` 形式、`operation` は純粋 regex、N² ACL 問題を回避

## アーキテクチャ図

```
WebUI (browser)
    │ REST + Bearer token
    ▼
Portal Server ── ACL 評価 ──► CommandRequest
    │                             │
    │  WS dispatch                │
    ▼                             ▼
Device/Bridge ◄── claim_token ───┘
    │
    │ subprocess
    ▼
portal-manage control ...
```

## スキーマ (5 テーブル)

| テーブル | 役割 |
|----------|------|
| `ctrl_devices` | 登録デバイス (id, display_name, bearer_token, ws_state, last_seen, is_first_webui_device) |
| `ctrl_device_acls` | ACL (source_device, target_device, operation すべて NOT NULL, device: プレフィックス + regex) |
| `ctrl_command_requests` | コマンド (target_device_id, source_device_id, status, claim_token 等) |
| `ctrl_bootstrap_tokens` | デバイス登録用一時トークン |
| `ctrl_operation_specs` | デバイスが advertise する operation (id, provider=device:&lt;id&gt;, group, params_schema, ui_hint) |

## フェーズ別完了基準

### Phase 1: モデル + manager_cli スキャフォールド (現在)

**完了基準**:
- `portal/servers/control_plane/{__init__.py,main.py,models.py,manager_cli.py}` が存在
- `models.py` に 5 テーブルが定義されている
- `manager_cli.py` に以下のサブコマンドが実装されている:
  - `list-acl`
  - `grant --source --target --operation`
  - `revoke --acl-id`
  - `list-devices`
  - `rename-device --device-id --display-name`
  - `set-admin --device-id`
  - `show-admin`
  - `clear-admin`
  - `issue-bootstrap-token --device-id --display-name [--ttl-minutes]`
- `main.py` で `BaseExtension` を継承し、`register_cli_commands` を実装
- `nix develop` 環境下で `portal-manage control list-acl` 等がエラーなく実行可能
- `make test-backend` が通過

### Phase 2: auth + REST API + dispatcher

**完了基準**:
- `auth.py` で `get_current_device` 依存が定義されている
- `api.py` で以下エンドポイントが実装されている:
  - `GET /api/control/devices`
  - `GET /api/control/devices/me` (副作用: 自動昇格)
  - `PATCH /api/control/devices/{id}`
  - `DELETE /api/control/devices/{id}` (admin only)
  - `POST /api/control/devices/register` (bootstrap token 消費)
  - `GET /api/control/acls`
  - `POST /api/control/acls` (admin only)
  - `PATCH /api/control/acls/{id}` (admin only)
  - `DELETE /api/control/acls/{id}` (admin only)
  - `GET /api/control/operations` (フィルタ済み)
  - `POST /api/control/commands`
  - `GET /api/control/commands/{id}`
- `dispatcher.py` で ACL 評価 + provider 解決

### Phase 3: WS

**完了基準**:
- `ws.py` で `/api/control/devices/{id}/ws` エンドポイントが実装されている
- claim_token ベースの claim/result プロトコル
- 再接続時の resume (60s grace)

### Phase 4: nginx WS upgrade

**完了基準**:
- `nixos/web-infrastructure.nix` に WS upgrade ヘッダ設定追加

### Phase 5: WebUI

**完了基準**:
- `#/control/devices`, `#/control/operations`, `#/control/commands` のハッシュルート追加
- operation レンダラ (JSON Schema + ui_hint → form)
- device_picker / operation_picker widget
- SSE で CommandRequest 状態変化を受信

### Phase 6: Bridge + systemd

**完了基準**:
- `portal/servers/control_plane/bridge.py` 実装
- `portal-control-bridge` entry_point 追加
- `nixos/portal-service.nix` に systemd unit 追加
- 2 台相互検証: bridge 経由で ACL 作成 → 反映確認

### Phase 7: Device agent

**完了基準**:
- NixOS module: `nixos/control-plane-agent.nix`
- nix-on-droid 用スクリプト
- reboot / status の動作確認

### Phase 8: backup/restore

**完了基準**:
- `backup_data` / `restore_data` 実装
- portal backup/restore test 通過

### Phase 9: ドキュメント

**完了基準**:
- AGENTS.md 更新
- `.opencode/skills/control-plane/SKILL.md` 作成

## 試験方法

### Phase 1 試験

```bash
# nix develop 環境下で実行
cd /home/syoch/ghq/github.com/syoch/infrastructure
nix develop --command bash -c "cd portal && python -m portal_manage control list-acl"
nix develop --command bash -c "cd portal && python -m portal_manage control list-devices"
nix develop --command bash -c "cd portal && python -m portal_manage control show-admin"

# テスト実行
make test-backend
```

### フェーズ共通の試験コマンド

```bash
# フルテスト
make test

# バックエンドのみ
make test-backend

# E2E
make test-e2e
```

## 開発上の注意

- コードコメントは書かない (AGENTS.md の方針)
- 既存 portal の拡張パターン (`BaseExtension`) に従う
- `flake.nix` の `python3Packages.callPackage ../portal` で同梱される
- entry_point は `pyproject.toml` に追加
- DB migration は SQLAlchemy の `Base.metadata.create_all` で OK (本番は Alembic 検討)

## ファイル配置

```
portal/servers/control_plane/
├── __init__.py
├── main.py            # ControlPlaneExtension (BaseExtension)
├── models.py          # 5 テーブル
├── manager_cli.py     # portal-manage control サブコマンド
├── auth.py            # get_current_device 依存 (Phase 2)
├── api.py             # REST エンドポイント (Phase 2)
├── ws.py              # WS エンドポイント (Phase 3)
├── dispatcher.py      # operation dispatch (Phase 2)
└── bridge.py          # bridge プロセス (Phase 6)
```

## 進捗

### Phase 1
- [x] ディレクトリ作成
- [x] models.py (Device, DeviceACL, CommandRequest, DeviceBootstrapToken, OperationSpec)
- [x] manager_cli.py (list-acl / grant / revoke / list-devices / rename-device / delete-device / set-admin / show-admin / clear-admin / issue-bootstrap-token / list-operations / list-commands / show-command)
- [x] main.py (ControlPlaneExtension: setup / register_cli_commands / backup_data / restore_data / get_startup_info)
- [x] pyproject.toml パッケージ追加
- [x] tests/config.test.json に拡張登録
- [x] 動作確認 (grant / list-acl / list-devices / show-admin / set-admin / clear-admin / rename-device / revoke / issue-bootstrap-token / バリデーション)
- [x] make test-backend 通過

### 実装サマリ

- **5 テーブル**: `ctrl_devices`, `ctrl_device_acls`, `ctrl_command_requests`, `ctrl_bootstrap_tokens`, `ctrl_operation_specs`
- **Device.bearer_token**: 全デバイス必須
- **DeviceACL**: `source_device` / `target_device` / `operation` すべて NOT NULL、CheckConstraint で `provider LIKE 'device:%'` 強制
- **CommandRequest**: `target_device_id` / `source_device_id` (FK 制約あり、`source_device_id` は NOT NULL)
- **is_first_webui_device**: Device に追加 (last-writer-wins 昇格は Phase 2 で実装)
- **バリデーション**:
  - device id: `^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$`
  - source_device / target_device: `device:<regex>` プレフィックス必須 + regex compile 検証
  - operation: 純粋 regex、compile 検証
- **CLI サブコマンド** 13 個すべて動作確認済み
- **backup_data / restore_data**: 全 5 テーブル対応実装 (overwrite / merge strategy 対応)

### 既知の未実装項目 (次フェーズ以降)

- Phase 2: auth.py (get_current_device) + api.py (REST エンドポイント) + dispatcher.py
- Phase 3: ws.py (WebSocket エンドポイント)
- Phase 5: WebUI
- Phase 6: bridge.py
- Phase 7: device agent
- Phase 8: backup/restore のテスト追加
- OperationSpec への seed (現状は seed なし、デバイスが register する運用)
