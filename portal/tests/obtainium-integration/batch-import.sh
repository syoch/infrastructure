#!/usr/bin/env bash
# batch-import.sh - 一括インポート用スクリプト

export OI_OBTAINIUM_PKG="dev.imranr.obtainium"
export OI_TMP_DIR="/tmp/batch-import"
mkdir -p "$OI_TMP_DIR"

# 共通ライブラリをロード (common.sh, deep_link.sh など)
source ./portal/tests/obtainium-integration/lib/common.sh
source ./portal/tests/obtainium-integration/lib/deep_link.sh

# 1. 準備: ポータルのURLを取得
PORTAL_URL="http://127.0.0.1:18000"
EXPORT_FILE="$OI_TMP_DIR/export.json"

# エクスポートを取得
curl -s "$PORTAL_URL/obtainium-export.json" > "$EXPORT_FILE"

# 2. 一括インポート
# jsonからアプリ一覧を抽出 (簡易的に)
APPS=$(python3 -c "import json; print(' '.join([a['id'] for a in json.load(open('$EXPORT_FILE'))['apps']]))")

for APP_ID in $APPS; do
    echo "Importing $APP_ID..."
    # deep link を生成して送信
    # (既存の send_deep_link を利用)
    # ここでは簡易的にインポートコマンドをシミュレート
    adb shell am start -a android.intent.action.VIEW -d "obtainium://app/$(python3 -c "import urllib.parse, json; print(urllib.parse.quote(json.dumps({'id': '$APP_ID', 'url': '$PORTAL_URL/$APP_ID'})))")" >/dev/null 2>&1
    sleep 2 # インポートダイアログを待つ
    # 「Continue」をタップ
    adb shell input tap 750 1150 # Continueボタンの座標 (適宜調整が必要)
    sleep 1
done
