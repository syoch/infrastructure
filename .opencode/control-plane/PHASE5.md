# Phase 5: WebUI

## 概要

既存の portal WebUI に `#/control` ルートを追加し、control plane の Devices / Operations / Commands / ACL をブラウザから操作できるようにする。SSE でリアルタイム更新。

## ファイル

| ファイル | 役割 |
|---------|------|
| `portal/public/index.html` | `#control-view` セクション + `#nav-control` ボタン追加 |
| `portal/public/js/control_api.js` | control plane API クライアント + SSE subscriber + bearer token 管理 (localStorage) |
| `portal/public/js/control_dashboard.js` | Devices / Operations / Commands / ACL のレンダリングとイベントハンドラ |
| `portal/public/js/control_op_renderer.js` | JSON Schema + ui_hint ベースのフォームレンダラ + モーダル起動 |

`portal/public/app.js` の router に `control` ルートを追加。

## 認証フロー

WebUI は special な "device" (`device_id="webui"`) として登録される。

1. ユーザーがサーバー側で bootstrap トークンを発行:
   ```
   portal-manage control issue-bootstrap-token --device-id webui --display-name "WebUI"
   ```
2. WebUI 初回アクセス時に localStorage に token なし → セットアップフォーム表示
3. ユーザーが bootstrap token を貼り付け → `POST /devices/register`
4. レスポンスの `bearer_token` を localStorage に保存
5. 以降の API 呼び出しは `Authorization: Bearer <token>` ヘッダで認証
6. SSE は `?token=...` クエリパラメータで認証 (EventSource はカスタムヘッダ非対応)

## 機能

### Devices セクション

- 登録された device 一覧
- `ws_state` を色分け表示 (`online`=緑, `offline`=灰, `never_connected`=黄)
- `last_seen` タイムスタンプ
- admin の場合:
  - "admin" チェックボックス → `POST /devices/{id}/set-admin`
  - "Delete" ボタン → `DELETE /devices/{id}` (確認ダイアログあり)

### Operations セクション

- provider ごとにグループ化 (`device:hostname` ラベル)
- 各 operation の `ui_hint.label` をボタン名として表示
- ボタンクリック → JSON Schema から form を生成し `renderOpForm` でモーダル起動
- フォーム送信で `POST /commands` → 一覧の自動更新
- provider が offline ならボタンを disable

### Commands セクション

- 直近 20 件の command
- `status` を色分け表示
- SSE で `command_status` イベントを受信したら該当行を更新
- `result` / `error` の最初の 60 文字を表示

### ACL セクション (admin のみ)

- 既存 ACL 一覧 + 削除ボタン
- 追加フォーム (source_device / target_device / operation / extra)

## JSON Schema ベースフォーム生成

`renderOpForm` は `params_schema` を見て input を動的生成:

| Schema 型 | UI 要素 |
|----------|--------|
| `string` | `<input type="text">` |
| `number` | `<input type="number" step="any">` |
| `integer` | `<input type="number">` |
| `boolean` | `<input type="checkbox">` |
| `enum: [...]` | `<select>` |

`required` 配列に含まれるフィールドには `*` を表示。
`description` は placeholder に設定。

## デザイン

- 既存 portal の `var(--bg-card)`, `var(--text-secondary)`, `var(--btn-*)` 変数を継承
- テーブルは `control-table` クラス
- モーダルは既存の `modal-backdrop` / `modal-content` クラスを再利用

## テスト

### 既存テストの維持

- `make test-backend` 通過 (24 REST + 5 WS = 29 tests)
- 既存 Playwright E2E テストを破壊しない

### 今後の E2E テスト (TODO Phase 5 follow-up)

`portal/tests/e2e/` に control plane の E2E テストを追加する想定:
- テスト用 bootstrap token 発行
- WebUI セットアップフローのテスト
- コマンド発行 → claim → result → WebUI 上での status 反映
- SSE 経由の live update

## 進捗

- [x] control_api.js (auth + SSE + 各種 REST)
- [x] control_dashboard.js (render + event handlers)
- [x] control_op_renderer.js (JSON Schema → form)
- [x] index.html (`#control-view` + nav)
- [x] app.js (routing 統合)
- [x] SSE auth 拡張 (auth.py が `?token=` も受理)
- [ ] Playwright E2E テスト (Phase 5 follow-up)

## 動作確認 (manual)

1. サーバを起動 (`nix develop -c make dev-server` or systemd)
2. 別のターミナルで bootstrap token 発行:
   ```
   portal-manage control issue-bootstrap-token --device-id webui --display-name "WebUI"
   ```
3. ブラウザで `http://localhost:8000/#/control` を開く
4. セットアップフォームに token を貼り付け
5. Devices タブに `webui` が出現 (admin 昇格済みのはず)
6. Operations タブは空 (まだ device が op を advertise していない)
7. 別ターミナルで device agent を起動 (Phase 7) するか、`portal-manage` から手動で bootstrap → WS 接続 → operations_register
8. Operations タブに provider:device id ごとにボタン表示、押下でフォーム起動
9. 実行 → Commands タブに新規行、status が SSE 経由で更新される
