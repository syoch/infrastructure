# Phase 9: Documentation

## 概要

Control plane の使い方を AGENTS.md に追記し、専用 skill を作成する。

## ファイル

| ファイル | 役割 |
|---------|------|
| `AGENTS.md` | Control plane セクションを追加 (REST/WS/bridge 仕様、5 テーブル要約、dogfooding 解説) |
| `.opencode/skills/control-plane/SKILL.md` | opencode スキル - control plane を扱う際の自動参照 |

## AGENTS.md への追加

- ディレクトリ表に `servers/` 行に `**ControlPlane**` を追加
- `servers.control_plane` 行を「拡張」セクションに
- `.opencode/control-plane/` 行を追加
- 「ポートとプロセス」セクションに `/api/control/...`、WS、SSE、bridge プロセスを追加
- 新セクション「Control Plane (拡張)」を追加: 5 テーブル、dogfooding、#/control ルート、Phase ドキュメントへの参照

## control-plane skill

`.opencode/skills/control-plane/SKILL.md` に以下を集約:
- Dogfooding architecture の説明
- 5 テーブルの概要
- 全 14 REST エンドポイント + WS/SSE のマトリクス
- WebSocket メッセージプロトコル (client→server, server→client)
- ACL 評価ロジック (re.search, default-deny)
- 同期コンテキストからの WS push の解決方法 (set_main_loop + run_coroutine_threadsafe)
- ファイル一覧と役割
- WebUI / bridge の bootstrap フロー
- テスト実行方法

## 進捗

- [x] AGENTS.md 更新
- [x] control-plane skill 作成
