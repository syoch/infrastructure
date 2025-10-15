# Certbot (Let's Encrypt) management commands
{ pkgs, self, system }:

{
  # 初回証明書取得
  certbot-init = pkgs.writeShellScriptBin "certbot-init" ''
    set -e

    PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
    cd "$PROJECT_DIR"

    DOMAIN="''${CERTBOT_DOMAIN:-syoch.f5.si}"
    EMAIL="''${CERTBOT_EMAIL}"
    STAGING="''${CERTBOT_STAGING:-0}"

    if [ -z "$EMAIL" ]; then
      echo "Error: CERTBOT_EMAIL environment variable is required"
      echo "Usage: CERTBOT_EMAIL=your@email.com certbot-init"
      exit 1
    fi

    # ダミー証明書の削除
    if [ -f "certbot/conf/live/$DOMAIN/DUMMY" ]; then
      echo "Removing dummy certificate..."
      rm -rf "certbot/conf/live/$DOMAIN"
    fi

    # 証明書ディレクトリの作成
    mkdir -p certbot/conf certbot/www certbot/work certbot/logs

    echo "Obtaining certificate for $DOMAIN..."
    echo "Email: $EMAIL"

    # ステージング環境フラグ
    STAGING_ARG=""
    if [ "$STAGING" -eq 1 ]; then
      STAGING_ARG="--staging"
      echo "Using Let's Encrypt staging environment (test mode)"
    fi

    # Certbotで証明書を取得
    ${pkgs.certbot}/bin/certbot certonly \
      --webroot \
      -w "$PROJECT_DIR/certbot/www" \
      --config-dir "$PROJECT_DIR/certbot/conf" \
      --work-dir "$PROJECT_DIR/certbot/work" \
      --logs-dir "$PROJECT_DIR/certbot/logs" \
      $STAGING_ARG \
      --email "$EMAIL" \
      --agree-tos \
      --no-eff-email \
      --domain "$DOMAIN" \
      --non-interactive

    echo "✓ Certificate obtained successfully"
    echo "  Certificate: certbot/conf/live/$DOMAIN/fullchain.pem"
    echo "  Private key: certbot/conf/live/$DOMAIN/privkey.pem"
    echo ""
    echo "Next steps:"
    echo "  1. Start or reload nginx: nginx-start or nginx-reload"
    echo "  2. Set up auto-renewal: certbot-renew-setup"
  '';

  # 証明書の更新
  certbot-renew = pkgs.writeShellScriptBin "certbot-renew" ''
    set -e

    PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
    cd "$PROJECT_DIR"

    echo "Renewing certificates..."

    # Certbotで証明書を更新
    ${pkgs.certbot}/bin/certbot renew \
      --config-dir "$PROJECT_DIR/certbot/conf" \
      --work-dir "$PROJECT_DIR/certbot/work" \
      --logs-dir "$PROJECT_DIR/certbot/logs" \
      --deploy-hook "cd $PROJECT_DIR && PROJECT_DIR=$PROJECT_DIR ${self.packages.${system}.nginx-reload}/bin/nginx-reload"

    echo "✓ Certificate renewal complete"
  '';

  # 証明書情報の表示
  certbot-status = pkgs.writeShellScriptBin "certbot-status" ''
    PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
    cd "$PROJECT_DIR"

    DOMAIN="''${CERTBOT_DOMAIN:-syoch.f5.si}"

    echo "Certificate status for $DOMAIN:"
    echo ""

    if [ -f "certbot/conf/live/$DOMAIN/fullchain.pem" ]; then
      echo "✓ Certificate exists"
      echo ""
      echo "Certificate details:"
      ${pkgs.openssl}/bin/openssl x509 -in "certbot/conf/live/$DOMAIN/fullchain.pem" -noout -text | \
        grep -E "(Subject:|Issuer:|Not Before|Not After )"
      echo ""
      echo "Files:"
      ls -lh "certbot/conf/live/$DOMAIN/"
    else
      echo "✗ Certificate not found"
      echo ""
      echo "To obtain a certificate, run:"
      echo "  CERTBOT_EMAIL=your@email.com certbot-init"
    fi
  '';

  # ダミー証明書の生成
  certbot-dummy = pkgs.writeShellScriptBin "certbot-dummy" ''
    set -e

    PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
    cd "$PROJECT_DIR"

    DOMAIN="''${CERTBOT_DOMAIN:-syoch.f5.si}"

    echo "Creating dummy certificate for $DOMAIN..."

    # 証明書ディレクトリの作成
    mkdir -p "certbot/conf/live/$DOMAIN"

    # ダミー証明書の生成
    ${pkgs.openssl}/bin/openssl req -x509 -nodes -newkey rsa:4096 -days 1 \
      -keyout "certbot/conf/live/$DOMAIN/privkey.pem" \
      -out "certbot/conf/live/$DOMAIN/fullchain.pem" \
      -subj "/CN=localhost"

    touch "certbot/conf/live/$DOMAIN/DUMMY"

    echo "✓ Dummy certificate created"
    echo "  Certificate: certbot/conf/live/$DOMAIN/fullchain.pem"
    echo "  Private key: certbot/conf/live/$DOMAIN/privkey.pem"
    echo ""
    echo "⚠️  This is a dummy certificate valid for 1 day only!"
    echo ""
    echo "Next steps:"
    echo "  1. Start nginx: sudo nginx-start"
    echo "  2. Obtain real certificate: certbot-init"
    echo "  3. Reload nginx: sudo nginx-reload"
  '';
}
