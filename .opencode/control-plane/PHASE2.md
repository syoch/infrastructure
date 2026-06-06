# Phase 2: auth + REST API + dispatcher

## 概要

`auth.py` (Bearer 認証 + first-webui-device 自動昇格)、`dispatcher.py` (ACL 評価 + provider 解決)、`api.py` (REST エンドポイント群) を実装する。Phase 3 (WS) より前の段階で、HTTP API 経由で device / ACL / operation / command が一通り管理可能になることを目標とする。

## ファイル

| ファイル | 役割 |
|---------|------|
| `portal/servers/control_plane/auth.py` | `get_current_device` 依存、`get_current_device_with_promotion` 依存 |
| `portal/servers/control_plane/dispatcher.py` | `can_issue` (ACL 評価)、`resolve_provider` (operation → target device)、`enqueue_command`、operation の filter |
| `portal/servers/control_plane/api.py` | REST エンドポイント (router 定義) |
| `portal/servers/control_plane/main.py` | router を `setup_routes()` で `get_routes()` 経由で登録 |

## エンドポイント一覧 (確定)

| Method | Path | 認可 | 動作 |
|--------|------|------|------|
| GET | `/api/control/devices` | Bearer | 全 device 一覧 (他 device 情報は read-only) |
| GET | `/api/control/devices/me` | Bearer | 自分の device 詳細 (副作用: first-webui-device 自動昇格) |
| PATCH | `/api/control/devices/{id}` | Bearer (self or admin) | display_name 変更 |
| DELETE | `/api/control/devices/{id}` | admin only | device 削除 |
| POST | `/api/control/devices/{id}/set-admin` | admin only | admin flag 移譲 |
| POST | `/api/control/devices/register` | なし (bootstrap token) | bootstrap token 消費 + device 登録 + bearer_token 発行 |
| GET | `/api/control/acls` | Bearer | ACL 一覧 |
| POST | `/api/control/acls` | admin only | ACL 作成 |
| PATCH | `/api/control/acls/{id}` | admin only | ACL 更新 (source/target/operation 変更可) |
| DELETE | `/api/control/acls/{id}` | admin only | ACL 削除 |
| GET | `/api/control/operations` | Bearer | filter 済み operation 一覧 |
| POST | `/api/control/commands` | Bearer (ACL 必須) | コマンド投入 (pending で dispatch) |
| GET | `/api/control/commands` | Bearer | コマンド一覧 (recent) |
| GET | `/api/control/commands/{id}` | Bearer (source or admin) | コマンド詳細 |

## 設計上の決定

### 認証
- 全エンドポイントで `Authorization: Bearer <token>` ヘッダを要求 (register エンドポイントのみ例外)
- CF Access は portal 側で一切不関与 (設計確定済み)

### first-webui-device 自動昇格
- `GET /api/control/devices/me` で発火
- どの device も `is_first_webui_device=True` を持っていない場合のみ、自分を昇格
- 競合: last-writer-wins (Q-final-G = a)
- uvicorn 1 worker + SQLite のため現実的競合は起きにくい

### ACL 評価
- `can_issue(source_id, target_id, operation)` で全 ACL を走査
- いずれかが (source_match AND target_match AND operation_match) で許可
- マッチなし → 403

### Provider 解決
- `OperationSpec.provider` から `device:<id>` を抽出
- target device とする
- operation 未登録 → 404 (コマンド投入時)

### Dispatcher (Phase 2 範囲)
- ACL 評価 + CommandRequest 作成 + OperationSpec 解決
- 実際の WS 送信は Phase 3 で実装
- Phase 2 ではコマンドは `pending` のまま残り、Phase 3 の WS 実装が拾う
- 検証として、コマンド作成の動作 (DB に pending が残る) と 403/404 のエラーパスを確認

## 試験

### 単体テスト (`portal/tests/backend/test_control_plane.py`)

| テスト | 確認内容 |
|--------|---------|
| `test_acl_exact_match` | 完全一致でマッチ |
| `test_acl_wildcard` | `.*` で全マッチ |
| `test_acl_regex_match` | regex 部分マッチ |
| `test_acl_no_match` | マッチなしで 403 |
| `test_acl_field_validation` | type prefix 欠落 / 不正 regex で ValueError |
| `test_auth_valid_token` | 有効な token で device 解決 |
| `test_auth_invalid_token` | 無効な token で 401 |
| `test_auth_missing_header` | ヘッダ無しで 401 |
| `test_first_webui_promotion` | 最初の /me で自動昇格、2 回目は昇格しない |
| `test_api_register_bootstrap` | bootstrap token で device 登録 |
| `test_api_register_expired` | 期限切れ token で 410 |
| `test_api_register_consumed` | 使用済み token で 410 |
| `test_api_acl_admin_only` | 非 admin の POST /acls で 403 |
| `test_api_acl_self_rename` | self rename は OK、他人 rename は admin 必要 |
| `test_api_command_acl_denied` | ACL なしで 403 |
| `test_api_command_acl_allowed` | ACL ありで 201 |
| `test_api_command_unknown_operation` | 未登録 operation で 404 |

### 実行

```bash
make test-backend
```

## 完了基準

- 全 17 個の単体テストが通過
- `make test-backend` が既存テスト + 新規テストを通過
- 既存 E2E テスト (`make test-e2e`) は影響を受けない (新エンドポイントは未配線)
- WS は Phase 3 のため未実装、`pending` のコマンドが DB に残ることを確認

## 進捗

- [x] auth.py (`get_current_device`, `get_current_device_with_promotion`, `require_admin`)
- [x] dispatcher.py (`can_issue`, `resolve_provider`, `provider_device_id`, `filter_operations_for_device`, `enqueue_command`)
- [x] api.py (14 エンドポイント)
- [x] main.py 統合 (router を `self.router` に設定)
- [x] 単体テスト 24 ケース (`test_control_plane.py`)
- [x] Makefile 更新
- [x] make test-backend 通過

## 実装サマリ

### auth.py
- `get_current_device`: Bearer ヘッダ → Device 解決 (失敗時 401)
- `get_current_device_with_promotion`: 誰も admin でなければ自分を昇格 (last-writer-wins)
- `require_admin`: `is_first_webui_device=True` を要求 (依存として使う)

### dispatcher.py
- `can_issue(source, target, operation)`: 全 ACL 走査、3 軸マッチで True
- `resolve_provider(operation_id)`: OperationSpec を返す or None
- `provider_device_id(spec)`: `device:<id>` から id 抽出
- `filter_operations_for_device`: admin は全件、それ以外は ACL で発行可能なもののみ
- `enqueue_command`: `pending` 状態で CommandRequest 作成 (Phase 3 の WS が拾う)

### api.py (14 endpoints)
- GET/PATCH/DELETE `/api/control/devices`, `/api/control/devices/me`, `/api/control/devices/{id}`, `/api/control/devices/{id}/set-admin`
- POST `/api/control/devices/register` (bootstrap token 消費)
- GET/POST/PATCH/DELETE `/api/control/acls`, `/api/control/acls/{id}`
- GET `/api/control/operations` (ACL filter 適用)
- POST/GET `/api/control/commands`, `/api/control/commands/{id}`
- Pydantic バリデーション: device id pattern、type prefix 必須 (source/target)、regex compile 検証 (operation)

### テスト 24 ケース (全通過)
1. auth: missing header → 401
2. auth: invalid token → 401
3. first-webui-device: 自動昇格
4. first-webui-device: 2 回目は昇格しない (last-writer-wins)
5. devices: list (admin)
6. rename: self OK
7. rename: 他人 (non-admin) → 403
8. rename: 他人 (admin) OK
9. ACL: non-admin POST → 403
10. ACL: admin wildcard 作成 OK
11. ACL: バリデーションエラー (missing type prefix) → 422
12. ACL: 重複 → 409
13. ACL: list
14. ACL: revoke
15. register: bootstrap token 成功
16. register: consumed → 410
17. command: no ACL → 403
18. command: ACL あり → 200 (pending)
19. command: unknown operation → 404
20. command: GET by id OK
21. command: 他 device GET → 403
22. operations: non-admin filter
23. operations: admin 全件
24. admin: 移譲
25. admin: 旧 admin 降格確認
26. admin: non-admin set-admin → 403
27. delete: admin が他 device 削除

### 既知の未実装項目 (次フェーズ以降)

- Phase 3: WS エンドポイント (claim/result プロトコル、コマンド dispatch の実体)
- Phase 3: dispatcher から enqueue したコマンドを WS で該当 device に送信
- Phase 5: WebUI
- Phase 6: bridge プロセス
- Phase 7: device agent
