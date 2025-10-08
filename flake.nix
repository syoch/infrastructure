{
  description = "Infrastructure deployment with reproducible environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        packages = {
          # ========================================
          # リモートサーバー用 Nginx 管理コマンド
          # ========================================

          # Nginx起動スクリプト
          nginx-start = pkgs.writeShellScriptBin "nginx-start" ''
            set -e

            PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
            cd "$PROJECT_DIR"

            # ログディレクトリの作成
            mkdir -p nginx/logs nginx/tmp/{client_body,proxy,fastcgi,uwsgi,scgi}

            echo "Starting nginx (requires root for ports 80/443)..."
            sudo ${pkgs.nginx}/bin/nginx -c "$PROJECT_DIR/nginx/nginx.conf" -p "$PROJECT_DIR"

            echo "✓ Nginx started successfully"
            echo "  PID file: nginx/logs/nginx.pid"
            echo "  Error log: nginx/logs/error.log"
            echo "  Access log: nginx/logs/access.log"
          '';

          # Nginx停止スクリプト
          nginx-stop = pkgs.writeShellScriptBin "nginx-stop" ''
            set -e

            PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
            cd "$PROJECT_DIR"

            if [ -f nginx/logs/nginx.pid ]; then
              echo "Stopping nginx (requires root)..."
              sudo ${pkgs.nginx}/bin/nginx -s stop -c "$PROJECT_DIR/nginx/nginx.conf" -p "$PROJECT_DIR"
              echo "✓ Nginx stopped"
            else
              echo "Nginx is not running (PID file not found)"
              exit 1
            fi
          '';

          # Nginx再起動スクリプト
          nginx-restart = pkgs.writeShellScriptBin "nginx-restart" ''
            set -e

            PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"

            # 停止 (エラーを無視)
            ${self.packages.${system}.nginx-stop}/bin/nginx-stop || true

            # 起動
            ${self.packages.${system}.nginx-start}/bin/nginx-start
          '';

          # Nginx設定リロード
          nginx-reload = pkgs.writeShellScriptBin "nginx-reload" ''
            set -e

            PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
            cd "$PROJECT_DIR"

            if [ -f nginx/logs/nginx.pid ]; then
              echo "Reloading nginx configuration (requires root)..."
              sudo ${pkgs.nginx}/bin/nginx -s reload -c "$PROJECT_DIR/nginx/nginx.conf" -p "$PROJECT_DIR"
              echo "✓ Nginx configuration reloaded"
            else
              echo "Nginx is not running (PID file not found)"
              exit 1
            fi
          '';

          # Nginx設定テスト
          nginx-test = pkgs.writeShellScriptBin "nginx-test" ''
            set -e

            PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
            cd "$PROJECT_DIR"

            echo "Testing nginx configuration..."
            # SSL証明書がない場合のエラーは無視
            if ${pkgs.nginx}/bin/nginx -t -c "$PROJECT_DIR/nginx/nginx.conf" -p "$PROJECT_DIR" 2>&1 | \
               grep -v "could not open error log file" | \
               grep -v "cannot load certificate" | \
               grep -E "emerg|error" > /dev/null; then
              echo "✗ Nginx configuration has errors"
              ${pkgs.nginx}/bin/nginx -t -c "$PROJECT_DIR/nginx/nginx.conf" -p "$PROJECT_DIR" 2>&1
              exit 1
            else
              echo "✓ Nginx configuration is valid (SSL certificate warnings ignored)"
            fi
          '';

          # Nginxステータス確認
          nginx-status = pkgs.writeShellScriptBin "nginx-status" ''
            set -e

            PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
            cd "$PROJECT_DIR"

            if [ -f nginx/logs/nginx.pid ]; then
              PID=$(cat nginx/logs/nginx.pid)
              if kill -0 "$PID" 2>/dev/null; then
                echo "✓ Nginx is running (PID: $PID)"
                echo ""
                echo "Listening ports:"
                ss -tlnp | grep "$PID" || echo "  (no ports found - check permissions)"
              else
                echo "✗ Nginx PID file exists but process is not running"
                exit 1
              fi
            else
              echo "✗ Nginx is not running (PID file not found)"
              exit 1
            fi
          '';

          # ログ表示
          nginx-logs = pkgs.writeShellScriptBin "nginx-logs" ''
            PROJECT_DIR="''${PROJECT_DIR:-$HOME/infrastructure}"
            cd "$PROJECT_DIR"

            LOG_TYPE="''${1:-access}"

            case "$LOG_TYPE" in
              access)
                echo "=== Access Log ==="
                tail -f nginx/logs/access.log
                ;;
              error)
                echo "=== Error Log ==="
                tail -f nginx/logs/error.log
                ;;
              *)
                echo "Usage: $0 {access|error}"
                exit 1
                ;;
            esac
          '';

          # ========================================
          # Certbot (Let's Encrypt) 管理コマンド
          # ========================================

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

          # ========================================
          # ローカル用デプロイコマンド
          # ========================================
          deploy = pkgs.writeShellScriptBin "deploy" ''
            set -e

            DEST_HOST="''${DEPLOY_HOST:-syoch-vpn}"
            DEST_PATH="''${DEPLOY_PATH:-~/infrastructure}"
            BRANCH="''${BRANCH:-main}"

            echo "=== Git-based Deployment ==="
            echo ""

            # Gitの変更確認
            if ! ${pkgs.git}/bin/git diff-index --quiet HEAD --; then
              echo "⚠️  Uncommitted changes detected!"
              echo "Please commit your changes first:"
              echo "  git add -A"
              echo "  git commit -m 'Your message'"
              exit 1
            fi

            echo "Step 1: Pushing to Git..."
            ${pkgs.git}/bin/git push origin "$BRANCH"

            echo ""
            echo "Step 2: Pulling on remote..."
            ${pkgs.openssh}/bin/ssh "$DEST_HOST" \
              "cd $DEST_PATH && ${pkgs.git}/bin/git pull origin $BRANCH"

            echo ""
            echo "Step 3: Testing configuration..."
            ${pkgs.openssh}/bin/ssh "$DEST_HOST" \
              "cd $DEST_PATH && PROJECT_DIR=$DEST_PATH nix run .#nginx-test"

            echo ""
            echo "Step 4: Applying changes..."
            ${pkgs.openssh}/bin/ssh "$DEST_HOST" \
              "cd $DEST_PATH && PROJECT_DIR=$DEST_PATH nix run .#deploy-local"

            echo ""
            echo "✓ Git deployment complete!"
          '';

          # サービス管理スクリプト（Docker用 - 後方互換性のため残す）
          manage = pkgs.writeShellScriptBin "manage-service" ''
            set -e

            DEST_HOST="''${DEPLOY_HOST:-syoch-vpn}"
            DEST_PATH="''${DEPLOY_PATH:-~/infrastructure}"

            case "$1" in
              down)
                echo "Stopping all services on $DEST_HOST"
                ${pkgs.openssh}/bin/ssh "$DEST_HOST" "cd $DEST_PATH && ${pkgs.docker-compose}/bin/docker-compose down"
                ;;
              up)
                SERVICE_NAME="$2"
                if [ -z "$SERVICE_NAME" ]; then
                  echo "Usage: $0 up <service_name>"
                  exit 1
                fi
                echo "Starting service $SERVICE_NAME on $DEST_HOST"
                ${pkgs.openssh}/bin/ssh "$DEST_HOST" "cd $DEST_PATH && ${pkgs.docker-compose}/bin/docker-compose up -d $SERVICE_NAME"
                ;;
              restart)
                SERVICE_NAME="$2"
                if [ -z "$SERVICE_NAME" ]; then
                  echo "Usage: $0 restart <service_name>"
                  exit 1
                fi
                echo "Restarting service $SERVICE_NAME on $DEST_HOST"
                ${pkgs.openssh}/bin/ssh "$DEST_HOST" "cd $DEST_PATH && ${pkgs.docker-compose}/bin/docker-compose restart $SERVICE_NAME"
                ;;
              logs)
                SERVICE_NAME="$2"
                echo "Showing logs for $SERVICE_NAME on $DEST_HOST"
                ${pkgs.openssh}/bin/ssh "$DEST_HOST" "cd $DEST_PATH && ${pkgs.docker-compose}/bin/docker-compose logs -f $SERVICE_NAME"
                ;;
              *)
                echo "Usage: $0 {down|up|restart|logs} [service_name]"
                exit 1
                ;;
            esac
          '';

        };

        # デフォルトパッケージ
        packages.default = self.packages.${system}.deploy-nginx;

        # 開発環境
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # デプロイツール
            git
            rsync
            openssh
            docker-compose

            # 監視・デバッグツール
            curl
            jq

            # nginx & certbot
            nginx
            certbot
            openssl

            # リモートサーバー用コマンド（ローカルでも使える）
            self.packages.${system}.nginx-start
            self.packages.${system}.nginx-stop
            self.packages.${system}.nginx-restart
            self.packages.${system}.nginx-reload
            self.packages.${system}.nginx-test
            self.packages.${system}.nginx-status
            self.packages.${system}.nginx-logs

            # Certbot コマンド
            self.packages.${system}.certbot-init
            self.packages.${system}.certbot-renew
            self.packages.${system}.certbot-status
            self.packages.${system}.certbot-dummy

            # デプロイ用スクリプト
            self.packages.${system}.deploy
            self.packages.${system}.manage
          ];

          shellHook = ''
            if [ -z "$PROJECT_DIR" ]; then
              export PROJECT_DIR="$(pwd)"
            fi
            if [ -z "$DEPLOY_HOST" ]; then
              export DEPLOY_HOST="syoch-vpn"
            fi
            if [ -z "$DEPLOY_PATH" ]; then
              export DEPLOY_PATH="~/infrastructure"
            fi

            echo "Infrastructure deployment environment"
            echo ""
            echo "⚡ Nginx commands (works locally and remotely):"
            echo "  nginx-start         - Start nginx"
            echo "  nginx-stop          - Stop nginx"
            echo "  nginx-restart       - Restart nginx"
            echo "  nginx-reload        - Reload config (no downtime)"
            echo "  nginx-test          - Test configuration"
            echo "  nginx-status        - Check status"
            echo "  nginx-logs access   - View access logs"
            echo "  nginx-logs error    - View error logs"
            echo ""
            echo "🔒 Certbot commands (Let's Encrypt):"
            echo "  certbot-dummy       - Create dummy certificate for testing"
            echo "  certbot-init        - Obtain initial certificate"
            echo "  certbot-renew       - Renew certificates"
            echo "  certbot-status      - Show certificate status"
            echo ""
            echo "🚀 Deploy commands:"
            echo "  deploy              - Deploy files (via Git, recommended)"
            echo ""
            echo "🐳 Docker commands (legacy):"
            echo "  manage-service      - Manage Docker services"
            echo ""
            echo "Environment variables:"
            echo "  DEPLOY_HOST         - Deployment target (default: syoch-vpn)"
            echo "  DEPLOY_PATH         - Deployment path (default: ~/infrastructure)"
            echo "  PROJECT_DIR         - Local nginx project dir (default: current dir)"
            echo "  CERTBOT_EMAIL       - Email for Let's Encrypt (required for certbot-init)"
            echo "  CERTBOT_DOMAIN      - Domain name (default: syoch.f5.si)"
            echo "  CERTBOT_STAGING     - Use staging environment (default: 0, set 1 for test)"
            echo ""
          '';
        };
      }
    );
}
