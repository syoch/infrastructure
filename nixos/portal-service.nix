{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services.syoch-portal;
  portalPkg = pkgs.python3Packages.callPackage ../portal { };
in
{
  options.services.syoch-portal = {
    enable = mkEnableOption "Android Device Provisioning Portal";
    
    configFile = mkOption {
      type = types.path;
      description = "Path to the config.json configuration file.";
    };

    readWritePaths = mkOption {
      type = types.listOf types.str;
      default = [];
      description = "List of paths that the service is allowed to write to (e.g. SQLite database directory, uploads directory).";
    };
  };

  config = mkIf cfg.enable {
    systemd.services.syoch-portal = {
      description = "Android Device Provisioning Portal Backend Service";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        DynamicUser = true;
        StateDirectory = "syoch-portal";
        
        ReadWritePaths = cfg.readWritePaths;

        ExecStart = "${portalPkg}/bin/portal-server --config ${cfg.configFile}";
        Restart = "always";
      };
    };
  };
}
