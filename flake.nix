{
  description = "Infrastructure deployment with reproducible environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      rec {
        packages = {
          magisk = pkgs.fetchurl {
            url = "https://github.com/topjohnwu/Magisk/releases/download/v30.7/app-debug.apk";
            hash = "sha256-QHKVJeKYoR2tbhNYainvpIpI6Xy/ACA3mOgEfRxxDLI=";
          };
          magiskboot =
            let
              sys = if system == "x86_64-linux" then "x86_64" else "arm64";
              exe_path = "lib/${sys}/libmagiskboot.so";
            in
            pkgs.stdenv.mkDerivation {
              name = "magiskboot";
              version = "30.7";
              src = packages.magisk;
              unpackPhase = ''
                mkdir -p $out
                ${pkgs.unzip}/bin/unzip -j $src "${exe_path}" -d $out
              '';
              buildPhase = ''
                mkdir -p $out/bin
                mv $out/libmagiskboot.so $out/bin/magiskboot
                chmod +x $out/bin/magiskboot
              '';
            };
          ksud-next =
            let
              pkgs-x86 = if system == "x86_64-linux" then pkgs else import nixpkgs { system = "x86_64-linux"; };
            in
            pkgs.stdenv.mkDerivation {
              name = "ksud-next";
              version = "3.2.0";
              src = pkgs.fetchurl (
                if system == "x86_64-linux" then
                  {
                    url = "https://github.com/KernelSU-Next/KernelSU-Next/releases/download/v3.2.0/ksud-x86_64-unknown-linux-musl";
                    hash = "sha256-NUi3XwR2HvBiy1KmPuaOS9W4b6LQEDIChybz6kjOd50=";
                  }
                else if system == "aarch64-linux" then
                  {
                    url = "https://github.com/KernelSU-Next/KernelSU-Next/releases/download/v3.2.0/ksud-aarch64-unknown-linux-musl";
                    hash = "";
                  }
                else
                  throw "Unsupported system: ${system}"
              );

              unpackPhase = "true";

              buildPhase = ''
                mkdir -p $out/bin
                cp $src $out/bin/ksud-next
                chmod +x $out/bin/ksud-next
              '';
            };
          portal = pkgs.python3Packages.callPackage ./portal { };
          test-backend = pkgs.writeShellApplication {
            name = "run-backend-tests";
            runtimeInputs = with pkgs; [
              (python3.withPackages (ps: with ps; [
                sqlalchemy
                psycopg2
                fastapi
                uvicorn
                python-multipart
              ]))
            ];
            text = ''
              PROJECT_ROOT=$(git rev-parse --show-toplevel)
              cd "$PROJECT_ROOT"
              echo "=== Running Python Backend Tests ==="
              python3 portal/tests/backend/test_backup_restore.py
              python3 portal/tests/backend/verify_roundtrip.py
            '';
          };
          test-e2e = pkgs.writeShellApplication {
            name = "run-e2e-tests";
            runtimeInputs = with pkgs; [
              python3
              nodejs
              chromium
              (python3.withPackages (ps: with ps; [
                sqlalchemy
                psycopg2
                fastapi
                uvicorn
                python-multipart
              ]))
            ];
            text = ''
              set -e
              PROJECT_ROOT=$(git rev-parse --show-toplevel)
              cd "$PROJECT_ROOT"
              echo "=== Running Playwright E2E Tests ==="
              cd portal/tests
              if [ ! -d node_modules ]; then
                npm install
              fi
              export CHROMIUM_PATH="${pkgs.chromium}/bin/chromium"
              npx playwright test "$@"
            '';
          };
          test-all = pkgs.writeShellApplication {
            name = "run-all-tests";
            runtimeInputs = [ packages.test-backend packages.test-e2e ];
            text = ''
              set -e
              run-backend-tests
              run-e2e-tests
            '';
          };
        };

        apps = {
          default = {
            type = "app";
            program = "${packages.portal}/bin/portal-server";
          };
          ksud-next = {
            type = "app";
            program = "${packages.ksud-next}/bin/ksud-next";
          };
          portal = {
            type = "app";
            program = "${packages.portal}/bin/portal-server";
          };
          portal-manage = {
            type = "app";
            program = "${packages.portal}/bin/portal-manage";
          };
          test = {
            type = "app";
            program = "${packages.test-all}/bin/run-all-tests";
          };
          test-backend = {
            type = "app";
            program = "${packages.test-backend}/bin/run-backend-tests";
          };
          test-e2e = {
            type = "app";
            program = "${packages.test-e2e}/bin/run-e2e-tests";
          };
        };

        checks = pkgs.lib.optionalAttrs pkgs.stdenv.isLinux {
          portal-test = pkgs.nixosTest {
            name = "portal-integration-test";
            
            nodes.machine = { config, pkgs, lib, ... }: {
              imports = [ ./nixos/web-infrastructure.nix ];
              
              # Override the portal config for the test machine to use test paths
              services.syoch-portal.configFile = lib.mkForce (pkgs.writeText "config.json" (builtins.toJSON {
                database = {
                  url = "sqlite:////var/lib/syoch-portal/database.db";
                  sqlite_wal = true;
                };
                server = {
                  port = 8000;
                  host = "127.0.0.1";
                };
                extensions = [
                  {
                    module = "servers.storage_manager";
                    class = "StorageManagerExtension";
                    config = {
                      uploads_dir = "/var/uploads";
                    };
                  }
                  {
                    module = "servers.obtainium_repo";
                    class = "ObtainiumRepoExtension";
                  }
                ];
              }));

              services.syoch-portal.readWritePaths = lib.mkForce [
                "/var/lib/syoch-portal"
                "/var/uploads"
              ];

              # Override domains and ACME settings for the local virtual test execution
              services.nginx.virtualHosts."test.local" = {
                locations."/" = {
                  proxyPass = "http://127.0.0.1:8000";
                };
              };

              systemd.tmpfiles.rules = [
                "d /var/uploads 0755 root root - -"
              ];
            };

            testScript = ''
              machine.wait_for_unit("syoch-portal.service")
              machine.wait_for_unit("nginx.service")
              machine.wait_for_open_port(8000)
              machine.wait_for_open_port(80)
              response = machine.succeed("curl -f -H 'Host: test.local' http://127.0.0.1/obtainium-export.json")
              print("Response:", response)
            '';
          };
        };


        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodejs
            chromium
            git
            rsync
            openssh

            curl
            jq

            nginx
            certbot
            openssl
            unzip

            # Android root dev tools
            aapt
            android-tools
            dtc
            usbutils
            sunxi-tools
            scrcpy
            packages.ksud-next
            (python3.withPackages (
              ps: with ps; [
                sqlalchemy
                psycopg2
                fastapi
                uvicorn
                python-multipart
              ]
            ))
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

            export PATH=${
              (pkgs.python3.withPackages (
                ps: with ps; [
                  sqlalchemy
                  psycopg2
                  fastapi
                  uvicorn
                  python-multipart
                ]
              ))
            }/bin:$PATH
            function find_flake_root() {
              local dir="$PWD"
              while [ "$dir" != "/" ]; do
                if [ -f "$dir/flake.nix" ]; then
                  echo "$dir"
                  return 0
                fi
                dir=$(dirname "$dir")
              done
              return 1
            }
            export PATH=$PATH:`find_flake_root`/app2/bin
            export CHROMIUM_PATH="${pkgs.chromium}/bin/chromium"
          '';
        };
      }
    );
}

