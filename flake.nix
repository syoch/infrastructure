{
  description = "Infrastructure deployment with reproducible environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
    deploy-rs.url = "github:serokell/deploy-rs";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      deploy-rs,
    }:
    {
      checks = builtins.mapAttrs (system: deployLib: deployLib.deployChecks self.deploy) deploy-rs.lib;
    }
    // flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        nginxCommands = import ./nix/nginx.nix { inherit pkgs self system; };
        certbotCommands = import ./nix/certbot.nix { inherit pkgs self system; };
        dockerCommands = import ./nix/docker.nix { inherit pkgs; };
      in
      {
        packages = nginxCommands // certbotCommands // dockerCommands;

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            git
            rsync
            openssh
            deploy-rs.packages.${system}.deploy-rs

            curl
            jq

            nginx
            certbot
            openssl

            self.packages.${system}.nginx-start
            self.packages.${system}.nginx-stop
            self.packages.${system}.nginx-restart
            self.packages.${system}.nginx-reload
            self.packages.${system}.nginx-test
            self.packages.${system}.nginx-status
            self.packages.${system}.nginx-logs

            self.packages.${system}.certbot-init
            self.packages.${system}.certbot-renew
            self.packages.${system}.certbot-status
            self.packages.${system}.certbot-dummy

            self.packages.${system}.deploy-git
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
            echo "  deploy .#syoch-vpc  - Deploy to NixOS (deploy-rs, recommended)"
            echo "  deploy-git          - Deploy files via Git (legacy)"
            echo ""
            echo "🧪 VM Testing commands:"
            echo "  vm-test             - Build and run NixOS VM for testing"
            echo "  vm-build            - Build VM without running"
            echo "  vm-quick-test       - Quick VM test with instructions"
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
