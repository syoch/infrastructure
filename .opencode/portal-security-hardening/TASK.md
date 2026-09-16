# Task: portal のアプリレベル認証強化 (残タスク)

**Status**: TODO
**担当**: portal / infrastructure 担当エージェント
**関連**: `portal-architecture` skill, `portal-basic-auth/TASK.md`, `nixos/portal-service.nix`

---

## 背景

ペネトレーションテスト (2026-08) で、portal の防御が「Cloudflare Access + 一部
パスバイパス」に依存しており、アプリレベル (FastAPI) の認証が欠けている/弱い
箇所が判明した。8 サブドメインへの CF Access 適用は完了済みだが、Access を
突破された場合の最終防壁としてアプリ側の認証強化が残っている。

---

## タスク一覧 (概要のみ)

### 1. `/api/backup`・`/api/restore` に認証を追加

- **問題**: バックアップ全体のダウンロード (`GET /api/backup`) と任意 tar.gz による
  復元/上書き (`POST /api/restore`) が、CF Access 通過後は誰でも実行可能
  (アプリレベルの認証チェックなし)
- **対応方針**: admin 相当の Bearer トークン (control-plane の `require_admin`
  相当) を必須にする
- **注意点**: control-plane とは別のルート登録なので、認証ヘルパーの共通化を検討。

### 2. `/api/control/devices/me` の自動 admin 昇格を廃止

- **問題**: admin デバイスが存在しない場合、`/api/control/devices/me` にアクセスした
  任意デバイスが `is_first_webui_device` に暗黙昇格する。bootstrap token 入手と
  組み合わせると、ACL 作成 → `/api/control/commands` 経由で任意デバイスに
  shell 実行 (RCE) へ到達しうる
- **対応方針**: 暗黙昇格を廃止し、初回 admin は CLI (`manage.py` / `set-admin`) で
  明示的に設定する
- **注意点**: 既存テスト (E2E / backend) が昇格に依存しているため、テストの
  変更も同時に行う。

### 3. `/api/control/*` の保護の整合性確認 (情報提供)

- **状態**: 8 サブドメインの CF Access 適用により `/api/control/*` も 302 化された
  (二重防御: CF Access + Bearer 認証)。追加対応は不要と想定するが、Access の
  パスバイパス設定が戻らないよう注意。

---

## 注意点 (全体共通)

- **破壊的変更に注意**: 認証追加は「自分のデバイス・bridge プロセス」も通らなくなる
  可能性がある。認証付与対象 (bridge の service token 等) を先に確保してから
  ロールアウトする。
- **テスト**: `tests/` (backend + Playwright E2E) を必ず更新・実行する。
- **シークレット**: 認証用トークン・パスワードは sops secret 経由で配布し、
  リポジトリに平文で置かない。
- 詳細設計は担当エージェントと議論の上決定する (この文書は概要と注意点のみ)。
