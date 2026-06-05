# AGENTS.md - syoch/infrastructure

## プロジェクト概要

Android Device Provisioning Portal を中心としたセルフホストインフラストラクチャ。
Obtainium と連携し、APK の配信・更新管理を行う。

## ディレクトリ構成

| ディレクトリ | 役割 |
|-------------|------|
| `portal/` | Python/FastAPI ベースの Portal Web アプリ |
| `portal/backend/` | コアサーバー (extension loader, backup manager, database) |
| `portal/servers/` | エクステンション (StorageManager, ObtainiumRepo) |
| `portal/public/` | フロントエンド (SPA, vanilla JS) |
| `portal/tests/` | E2E テスト (Playwright) + バックエンドテスト |
| `portal/tests/obtainium-integration/` | Obtainium 統合試験 (AVD 使用) |
| `nixos/` | NixOS モジュール (portal-service, web-infrastructure) |
| `tailscale/` | Tailscale VPN 設定テンプレート |
| `gamemcbe/` | Minecraft Bedrock Dedicated Server |

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

## 注意事項

- `nix develop` はリポジトリルートで実行してください (flake.nix の検索)
- プレコミットフックが秘密情報のスキャンを行います (`.githooks/pre-commit`)
- Cloudflare Access が `portal.syoch.org` を保護しています
- APK は Content-Addressable Storage (SHA-256) で管理されます
