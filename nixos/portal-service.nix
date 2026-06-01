{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services.portal;
  portalPkg = pkgs.python3Packages.callPackage ../portal { };
in
{
  options.services.portal = {
    enable = mkEnableOption "Android Device Provisioning Portal";
    
    port = mkOption {
      type = types.port;
      default = 8000;
      description = "Internal port for portal server.";
    };

    host = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = "Host to bind the portal server.";
    };

    uploadsDir = mkOption {
      type = types.str;
      default = "/mnt/NAS/Android Root/.tmp/prod/uploads";
      description = "Path to store uploaded APKs.";
    };

    stateDir = mkOption {
      type = types.str;
      default = "/var/lib/portal";
      description = "Directory to store state and sqlite database.";
    };
  };

  config = mkIf cfg.enable {
    systemd.services.portal = {
      description = "Android Device Provisioning Portal Backend Service";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        DynamicUser = true;
        StateDirectory = "portal";
        
        # Explicitly grant read-write access to the state and uploads directory
        # Wrap uploadsDir in quotes to handle paths with spaces safely in systemd
        ReadWritePaths = [ cfg.stateDir "\"${cfg.uploadsDir}\"" ];

        ExecStart = ''
          ${portalPkg}/bin/portal-server \
            --config ${pkgs.writeText "config.json" (builtins.toJSON {
              database = {
                url = "sqlite:///${cfg.stateDir}/database.db";
                sqlite_wal = true;
              };
              server = {
                port = cfg.port;
                host = cfg.host;
              };
              extensions = [
                {
                  module = "servers.storage_manager";
                  class = "StorageManagerExtension";
                  config = {
                    uploads_dir = cfg.uploadsDir;
                  };
                }
                {
                  module = "servers.obtainium_repo";
                  class = "ObtainiumRepoExtension";
                }
              ];
            })}
        '';
        Restart = "always";
      };
    };
  };
}
