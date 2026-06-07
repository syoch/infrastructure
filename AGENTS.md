# AGENTS.md - syoch/infrastructure

## プロジェクト概要

Android Device Provisioning Portal を中心としたセルフホストインフラストラクチャ。
Obtainium と連携し、APK の配信・更新管理を行う。

## ディレクトリ構成

| ディレクトリ | 役割 |
|-------------|------|
| `portal/` | Python/FastAPI ベースの Portal Web アプリ |
| `portal/backend/` | コアサーバー (extension loader, backup manager, database) |
| `portal/servers/` | エクステンション (StorageManager, ObtainiumRepo, **ControlPlane**) |
| `portal/public/` | フロントエンド (SPA, vanilla JS) |
| `portal/tests/` | E2E テスト (Playwright) + バックエンドテスト |
| `portal/tests/obtainium-integration/` | Obtainium 統合試験 (AVD 使用) |
| `nixos/` | NixOS モジュール (portal-service, web-infrastructure) |
| `tailscale/` | Tailscale VPN 設定テンプレート |
| `gamemcbe/` | Minecraft Bedrock Dedicated Server |
| `.opencode/control-plane/` | Control plane 設計ドキュメント (Phase 1-12) |

## 開発環境

```bash
# nix develop で全ツールが利用可能になる
# pwd はリポジトリルート必須 (flake.nix を検出するため)
nix develop --command bash

# または direnv が自動で有効化 (.envrc: "use flake")
```

dev shell で提供される主なツール: Node.js, Python 3 (sqlalchemy, fastapi, uvicorn), Chromium, curl, jq, rsync, Android tools (aapt, adb)

## テスト実行

```bash
# 全テスト
make test

# バックエンドテストのみ
make test-backend
# 注: control_plane_ws テストは `nix develop` 環境 (websockets パッケージ) を必要とします

# Playwright E2E テスト (pwd はリポジトリルート必須)
make test-e2e
# または
nix develop --command bash -c "cd portal/tests && npx playwright test --reporter=list"

# Obtainium 統合試験 (AVD 起動中 + バックアップ tarball 必須)
make test-obtainium BACKUP=path/to/backup.tgz

# Obtainium スモークテスト (3アプリ)
make test-obtainium-smoke BACKUP=path/to/backup.tgz
```

## テスト作成の注意

### 網羅性
- 正常系だけでなく異常系・境界値もカバーする
- Pydantic バリデーション: `overrideSource: null`, `preferredApkIndex: null` が通ること
- 削除操作時は dialog accept のハンドリングを明示的に行う

### sleep を避ける
- `sleep` による待機は絶対に使わない
- 状態検出: `ui_dump` (uiautomator), ファイル存在チェック, HTTP ステータス確認
- UI 要素の表示待機: Playwright の `waitForSelector`, `expect().toBeVisible()`

### テスト環境
- E2E: `nix develop --command` で実行 (pwd はリポジトリルート必須)
- Obtainium: AVD 起動中 + バックアップ tarball 必須
- シードデータ: `bootstrap/seed_backup.tar.gz`
- テスト自動起動: Playwright が `webServer` 設定で事前にサーバーを起動

### クリーンアップ
- 各テストは作成したデータを自身で削除する
- テスト間の状態共有は避ける (独立性)

### UI テスト固有の注意
- ハッシュベースルーティング (`#/dashboard`, `#/edit?type=app&id=...`)
- confirm ダイアログ: `page.once('dialog', ...)` で事前登録
- APK アップロード: マジックバイト `PK\x03\x04` で始まる必要あり
- テスト終了後、作成したアプリ・カテゴリは必ず削除する

## ポートとプロセス

- Portal サーバー: `http://localhost:8000` (テスト時)
- テスト DB: `portal/tests/portal_test.db` (SQLite, WAL モード)
- テスト設定: `portal/tests/config.test.json`
- Control plane REST: `/api/control/{devices,acls,operations,commands,events}`
- Control plane WS: `/api/control/devices/{device_id}/ws?token=tk_xxx`
- Control plane bridge: `portal-control-bridge --server-url <...> --bootstrap-token <...>`
- Device agent: `portal-device-agent --config /path/to/config.json` (generic shell-command-based)
- Device dogfooding: `bridge.py` が `acl.*` / `device_admin.*` を advertise
- WebUI: `#/control` ルート (Phase 12 で分割: `#/control/devices`, `#/control/acl`, `#/operations`)
- Control JS モジュール: `portal/public/js/control_{router,bootstrap,devices,acl,operations,api}.js`
- Operations クエリ: `#/operations?status=&from=&to=&op=&limit=&offset=`
- 管理者昇格 CLI: `python3 manage.py --config <cfg> control set-admin --device-id <id>`
- Schema renderer: `portal/public/js/schema_renderer.js` (JSON Schema → form, `ui_hint.widget: json|textarea|password`)
- Schema editor: `portal/public/js/schema_editor.js` (visual JSON Schema editor)
- 設計: `.opencode/control-plane/PHASE{1..12}.md` を参照
## 注意事項

- `nix develop` はリポジトリルートで実行してください (flake.nix の検索)
- プレコミットフックが秘密情報のスキャンを行います (`.githooks/pre-commit`)
- Cloudflare Access が `portal.syoch.org` を保護しています
- APK は Content-Addressable Storage (SHA-256) で管理されます
