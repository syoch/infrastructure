{
  description = "Android Device Provisioning Portal (syoch/infrastructure)";

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
        portalPython = pkgs.python3.withPackages (ps: import ./python-deps.nix ps);
      in
      rec {
        packages = {
          portal = pkgs.python3Packages.callPackage ./default.nix {
            buildNpmPackage = pkgs.buildNpmPackage;
          };
          test-backend = pkgs.writeShellApplication {
            name = "run-backend-tests";
            runtimeInputs = [ portalPython ];
            text = ''
              PROJECT_ROOT=$(git rev-parse --show-toplevel)
              cd "$PROJECT_ROOT"
              echo "=== Running Python Backend Tests ==="
              python3 backend/core/tests/test_backup_restore.py
              python3 backend/core/tests/verify_roundtrip.py
              python3 backend/obtainium/tests/test_export_schema.py
              python3 backend/obtainium/tests/test_obtainium_compiler.py
              python3 backend/control_plane/tests/test_control_plane.py
              python3 backend/control_plane/tests/test_control_plane_core.py
              python3 backend/control_plane/tests/test_control_plane_backup.py
              python3 backend/control_plane/tests/test_control_plane_ws.py
              python3 backend/control_plane/tests/test_device_agent.py
              python3 backend/app_portal/tests/test_app_portal.py
              python3 backend/app_portal/tests/test_opencode_tool.py
              python3 backend/app_portal/tests/test_app_portal_delivery_e2e.py
            '';
          };
          test-e2e = pkgs.writeShellApplication {
            name = "run-e2e-tests";
            runtimeInputs = [
              pkgs.nodejs
              pkgs.chromium
              portalPython
            ];
            text = ''
              set -e
              PROJECT_ROOT=$(git rev-parse --show-toplevel)
              cd "$PROJECT_ROOT"
              echo "=== Building portal frontend (Vite) ==="
              (cd frontend && npm install && npm run build)
              echo "=== Running Playwright E2E Tests ==="
              cd frontend
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
              imports = [ ./nixos/portal-service.nix ];

              services.portal.enable = true;
              services.nginx.enable = true;
              services.nginx.recommendedProxySettings = true;
              services.nginx.recommendedTlsSettings = true;

              # Override the portal config for the test machine to use test paths
              services.portal.configFile = lib.mkForce (pkgs.writeText "config.json" (builtins.toJSON {
                database = {
                  url = "sqlite:////var/lib/portal/database.db";
                  sqlite_wal = true;
                };
                server = {
                  port = 8000;
                  host = "127.0.0.1";
                };
                extensions = [
                  {
                    id = "storage";
                    config = {
                      uploads_dir = "/var/uploads";
                    };
                  }
                  {
                    id = "obtainium";
                  }
                ];
              }));

              services.portal.readWritePaths = lib.mkForce [
                "/var/lib/portal"
                "/var/uploads"
              ];

              # Portal nginx vhost + Basic Auth (Obtainium bypass protection)
              services.portal.nginx = {
                enable = true;
                hostName = "portal.test.local";
              };
              services.portal.basicAuth = {
                enable = true;
                htpasswdFile = pkgs.writeText "obtainium.htpasswd" "obtainium:{SHA}IGyAQTualsExLMNGt9JRe4RGPt0=";
              };

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
              machine.wait_for_unit("portal.service")
              machine.wait_for_unit("nginx.service")
              machine.wait_for_open_port(8000)
              machine.wait_for_open_port(80)
              response = machine.succeed("curl -f -H 'Host: test.local' http://127.0.0.1/obtainium-export.json")
              print("Response:", response)

              # Basic Auth: unauthenticated requests to protected paths must return 401
              machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -H 'Host: portal.test.local' http://127.0.0.1/scrape-index.html | grep -q '^401$'")
              machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -H 'Host: portal.test.local' http://127.0.0.1/api/apps/download/1/test.apk | grep -q '^401$'")
              machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -H 'Host: portal.test.local' http://127.0.0.1/obtainium-export.json | grep -q '^401$'")

              # Basic Auth: authenticated requests must reach the app (200; download returns 404 for missing APK but passes auth)
              machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -u obtainium:testpass -H 'Host: portal.test.local' http://127.0.0.1/scrape-index.html | grep -q '^200$'")
              machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -u obtainium:testpass -H 'Host: portal.test.local' http://127.0.0.1/obtainium-export.json | grep -q '^200$'")
              machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -u obtainium:testpass -H 'Host: portal.test.local' http://127.0.0.1/api/apps/download/1/test.apk | grep -q '^404$'")

              # Basic Auth: default / (dashboard) remains reachable
              machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -H 'Host: portal.test.local' http://127.0.0.1/ | grep -q '^200$'")
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

            mypy

            nginx
            certbot
            openssl

            # Android tooling (adb) for the Obtainium integration test
            android-tools
            portalPython
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

            export PATH=${portalPython}/bin:$PATH
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
    ) // {
      nixosModules = {
        portal = ./nixos/portal-service.nix;
        portal-device-agent = ./nixos/portal-device-agent.nix;
        default = ./nixos;
      };
    };
}

