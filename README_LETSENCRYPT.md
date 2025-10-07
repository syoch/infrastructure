# Let's Encrypt SSL証明書の設定

このプロジェクトでは、certbotを使用してLet's Encrypt SSL証明書を自動的に取得・更新します。

## 初回セットアップ

1. **初回証明書の取得**

   以下のコマンドを実行して、SSL証明書を取得します:

   ```bash
   ./init-letsencrypt.sh your-email@example.com
   ```

   - `your-email@example.com`を実際のメールアドレスに置き換えてください
   - このメールアドレスは証明書の更新通知などに使用されます

2. **テスト環境での動作確認（推奨）**

   初めて証明書を取得する場合は、まずテスト環境で動作確認することをお勧めします。

   `init-letsencrypt.sh`の`staging`変数を`1`に変更してください:
   ```bash
   staging=1  # テスト環境
   ```

   動作確認後、`staging=0`に戻して本番環境の証明書を取得してください。

## 証明書の自動更新

- certbotコンテナが12時間ごとに証明書の更新をチェックします
- nginxコンテナが6時間ごとに設定をリロードします
- 証明書の有効期限が30日未満になると自動的に更新されます

## ディレクトリ構造

```
certbot/
├── conf/          # Let's Encrypt証明書と設定ファイル
└── www/           # ACMEチャレンジ用のWebroot
```

## トラブルシューティング

### 証明書の取得に失敗する場合

1. ドメイン名が正しく設定されているか確認
   - `nginx.conf`の`server_name`
   - `init-letsencrypt.sh`の`domain`変数

2. ポート80と443がファイアウォールで開放されているか確認

3. DNSレコードが正しく設定されているか確認
   - `syoch.f5.si`がサーバーのIPアドレスを指していること

### 証明書を再取得する場合

既存の証明書を削除して再取得:

```bash
sudo rm -rf ./certbot/conf/live/syoch.f5.si
./init-letsencrypt.sh your-email@example.com
```

### ログの確認

```bash
# certbotのログ
docker-compose logs certbot

# nginxのログ
docker-compose logs nginx
```

## 手動での証明書更新

通常は自動更新されますが、手動で更新する場合:

```bash
docker-compose run --rm certbot renew
docker-compose exec nginx nginx -s reload
```
