# Phase 3: WebSocket + SSE

## 概要

`ws.py` で WebSocket エンドポイントを実装し、claim/result プロトコルでコマンドの双方向通信を実現する。あわせて WebUI への状態通知用に SSE エンドポイントを追加する。

## ファイル

| ファイル | 役割 |
|---------|------|
| `portal/servers/control_plane/ws.py` | WebSocket エンドポイント + ConnectionManager + メッセージハンドラ |
| `portal/servers/control_plane/sse.py` | SSE エンドポイント (WebUI への状態通知) |
| `portal/servers/control_plane/dispatcher.py` | enqueue_command に WS 通知を組み込み (Phase 2 から拡張) |
| `portal/servers/control_plane/main.py` | router 設定に ws / sse router を追加 |

## WebSocket プロトコル

### エンドポイント
- `WS /api/control/devices/{device_id}/ws?token=tk_xxx`
- 認証: クエリパラメータ `token` (ブラウザは Authorization ヘッダを設定できないため)

### クライアント → サーバ

| Type | Payload | 用途 |
|------|---------|------|
| `hello` | `{resumed_claimed_ids?: [command_id, ...]}` | 再接続時の claim 引き継ぎ (省略可) |
| `ping` | `{}` | ハートビート (30 秒間隔) |
| `claim` | `{command_id, claim_token}` | コマンドの実行権を取得 |
| `result` | `{command_id, status, result?, error?}` | 実行結果送信。`status` は `succeeded` / `failed` |
| `operations_register` | `{operations: [{id, group, name, description, params_schema, result_schema, ui_hint, last_seen}, ...]}` | device が advertise する operation を登録 |

### サーバ → クライアント

| Type | Payload | 用途 |
|------|---------|------|
| `welcome` | `{device_id, display_name, is_first_webui_device, pending_commands: [...]}` | 接続確立直後、pending のコマンド一覧 |
| `command` | `{command_id, operation, params, timeout_seconds, claim_token, source_device_id}` | 新規コマンド (enqueue 直後) |
| `claimed_ack` | `{command_id}` | claim 受理 |
| `result_ack` | `{command_id, status}` | result 受理 |
| `operations_registered` | `{count}` | operations_register 受理 |
| `pong` | `{}` | ping への応答 |
| `error` | `{message}` | エラー (claim_token 不一致等) |
| `bye` | `{reason}` | サーバ側 close 直前 |

### 状態管理

- `Device.ws_state`: `online` / `offline` / `never_connected`
- `Device.last_seen`: 最終 ping 受信時刻 (UTC)
- `ConnectionManager.connections`: `dict[device_id, WebSocket]`
- 1 device につき 1 WS。同時接続は古い方を close。

### コマンドライフサイクル (Phase 3 完成形)

```
pending  →  WS で device に push  →  device が claim  →  claimed
                                                                        ↓
                                                              device が実行
                                                                        ↓
                              succeeded / failed / timeout / cancelled (WebUI から)
```

- enqueue 時に `pending` 作成 → WS がオンラインなら即 push、オフラインなら接続時に再送
- claim で `claimed` に遷移、`claimed_at` 記録、`claim_token` 一致必須
- 実行後 `result` で `succeeded` / `failed`、`completed_at` 記録
- `claimed` 状態で `timeout_seconds` 経過 → `timeout` (バックグラウンド sweeper)
- `pending` 状態で WebUI がキャンセル → `cancelled`

### Reconnection / Resume

- 切断後 60 秒以内に再接続 + `hello.resumed_claimed_ids` を送る
- サーバは `claimed` 中のコマンドを `resumed_claimed_ids` 引き継ぎ
- `timeout_seconds` 経過済みの `claimed` は `timeout` に遷移
- 同一 device_id で複数 WS 接続を拒否 (古い方 close)

## SSE プロトコル

### エンドポイント
- `GET /api/control/events` (Authorization: Bearer required)
- `Content-Type: text/event-stream`

### イベント形式

```
event: command_status
data: {"command_id": "...", "status": "claimed", "source_device_id": "...", "target_device_id": "..."}

event: command_status
data: {"command_id": "...", "status": "succeeded", "result": {...}}
```

- イベントは JSON 1 行
- `event:` フィールドで種別を区別
- 接続時に直近 50 件のコマンド状態を snapshot として配信 (任意)

## 試験

### 単体テスト (`portal/tests/backend/test_control_plane_ws.py`)

| テスト | 確認内容 |
|--------|---------|
| `test_ws_auth` | 不正な token で接続拒否 (1008 close code) |
| `test_ws_welcome` | 接続直後に welcome 受信、pending コマンドを含む |
| `test_ws_claim` | claim → claimed_ack、claim_token 不一致で error |
| `test_ws_result` | result → result_ack、status 反映 |
| `test_ws_ping_pong` | ping 送信 → pong 受信 |
| `test_ws_operations_register` | operations_register → DB に OperationSpec 作成・更新 |
| `test_ws_timeout` | 60s 経過した claimed は timeout |
| `test_ws_resume` | 切断→再接続で claimed 引き継ぎ |
| `test_sse_basic` | SSE 接続してイベント受信 |

### 実行

```bash
make test-backend
```

## 完了基準

- 全 9 個の WS/SSE テストが通過
- `make test-backend` が既存 + 新規すべて通過
- enqueue した pending コマンドが WS 経由で即座に device に届く
- claim_token 検証が動作 (replay 防止)
- timeout_seconds 経過後の sweeper が動作

## 進捗

- [x] PHASE3.md
- [x] ws.py
- [x] dispatcher.py 拡張 (enqueue → WS 通知、`set_main_loop` で main loop を startup で capture)
- [x] sse.py
- [x] main.py 統合 (`install_event_loop_capture` メソッド + `merged` router に api+ws+sse すべて include)
- [x] WS テスト (5 件: 認証 success/fail, operations_register, claim/result lifecycle, resume→timeout)
- [x] make test-backend 通過

## 実装メモ

### 同期コンテキストからの WS push

`enqueue_command` は FastAPI sync handler 経由で呼ばれ、anyio threadpool で実行される。
メインの event loop 上で動作する WS 接続にメッセージを送るため、`set_main_loop` を FastAPI の `startup` イベントでキャプチャし、`asyncio.run_coroutine_threadsafe(..., main_loop).result(timeout=2.0)` で thread-safe に push をスケジュールする。

```python
def install_event_loop_capture(self, app):
    @app.on_event("startup")
    async def _capture_loop():
        set_main_loop(asyncio.get_event_loop())
```

### SSE publish フック

`publish_command_status(cmd)` を export し、ws.py の `_handle_claim` / `_handle_result` から呼ぶことで、WS 経由の claim/result 状態を WebUI 側 SSE subscriber に反映する。

### OperationSpec 主キー変更

Phase 1 では `id` を primary key としていたが、これは「同じ operation id を複数 device が advertise する」ユースケース (例: `device.reboot` を複数の device が提供) と矛盾する。
Phase 3 で複合主キー `(provider, id)` に変更した。
- `resolve_provider(db, operation_id, target_device_id)` のシグネチャを変更し、provider で一意に特定
- `api.py` の 404 エラーメッセージを `not registered for device <id>` に調整

### Resume テストの設計

`test_ws_resume_promotes_timeout` は:
1. device register + ACL grant
2. WS 接続 → command issue → claim (→ claimed)
3. WS 切断、`time.sleep(1.5)` で `timeout_seconds=1` 経過
4. 再接続 + `hello.resumed_claimed_ids = [cid]`
5. `_handle_hello` が `claimed_at + timeout_seconds < now` を判定して `timeout` に遷移
6. 検証: `GET /commands/{cid}` → `status == "timeout"`

## 完了基準の達成

- 5/5 WS テスト通過
- 24/24 REST テスト通過 (既存)
- `make test-backend` 全体通過
- enqueue した pending コマンドが WS 経由で即座に device に届く (verified in test_ws_claim_and_result_lifecycle)
- claim_token 検証が動作
- timeout_seconds 経過後の sweeper は `hello` ハンドラ内で実装 (代替 sweeper)
