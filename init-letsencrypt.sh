#!/bin/bash

# 初回のLet's Encrypt証明書取得スクリプト
# 使用方法: ./init-letsencrypt.sh <your-email@example.com>

if [ -z "$1" ]; then
  echo "使用方法: ./init-letsencrypt.sh <your-email@example.com>"
  exit 1
fi

email=$1
domain="syoch.f5.si"
staging=0 # 本番環境の場合は0、テスト環境の場合は1に設定

# 既存の証明書を削除(必要な場合のみ)
if [ -d "./certbot/conf/live/$domain" ]; then
  echo "既存の証明書が見つかりました。続行しますか? (y/n)"
  read -r response
  if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "既存の証明書を削除します..."
    sudo rm -rf ./certbot/conf/live/$domain
  else
    echo "処理を中断しました。"
    exit 1
  fi
fi

# ダミー証明書を作成してnginxを起動
echo "### ダミー証明書を作成しています..."
path="/etc/letsencrypt/live/$domain"
mkdir -p "./certbot/conf/live/$domain"
sudo docker-compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:4096 -days 1\
    -keyout '$path/privkey.pem' \
    -out '$path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

echo ""
echo "### nginxを起動しています..."
sudo docker-compose up -d nginx

echo ""
echo "### ダミー証明書を削除しています..."
sudo docker-compose run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/$domain && \
  rm -Rf /etc/letsencrypt/archive/$domain && \
  rm -Rf /etc/letsencrypt/renewal/$domain.conf" certbot

echo ""
echo "### Let's Encrypt証明書を取得しています..."

# テスト環境の設定
staging_arg=""
if [ $staging -eq 1 ]; then
  staging_arg="--staging"
fi

sudo docker-compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    --email $email \
    --agree-tos \
    --no-eff-email \
    -d $domain" certbot

echo ""
echo "### nginxをリロードしています..."
sudo docker-compose exec nginx nginx -s reload

echo ""
echo "### 完了しました!"
echo "証明書は12時間ごとに自動更新されます。"
