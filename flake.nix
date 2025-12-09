{
  description = "Infrastructure deployment with reproducible environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
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
      in
      {

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
          '';
        };
      }
    );
}
