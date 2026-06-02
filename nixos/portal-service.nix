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

    user = mkOption {
      type = types.str;
      default = "syoch-portal";
      description = "User account under which the service runs.";
    };

    group = mkOption {
      type = types.str;
      default = "syoch-portal";
      description = "Group under which the service runs.";
    };
  };

  config = mkIf cfg.enable {
    users.users = lib.optionalAttrs (cfg.user == "syoch-portal") {
      syoch-portal = {
        isSystemUser = true;
        group = cfg.group;
        description = "Android Device Provisioning Portal user";
      };
    };

    users.groups = lib.optionalAttrs (cfg.group == "syoch-portal") {
      syoch-portal = { };
    };

    systemd.services.syoch-portal = {
      description = "Android Device Provisioning Portal Backend Service";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        StateDirectory = "syoch-portal";

        ReadWritePaths = cfg.readWritePaths;

        ExecStart = "${portalPkg}/bin/portal-server --config ${cfg.configFile}";
        Restart = "always";

        NoNewPrivileges = true;
        ProtectSystem = "strict";
        PrivateTmp = true;
        RestrictNamespaces = true;
        RestrictAddressFamilies = [ "AF_INET" "AF_INET6" "AF_UNIX" ];
        MemoryDenyWriteExecute = true;
        SystemCallArchitectures = "native";
        SystemCallFilter = [ "@system-service" "~@privileged" "~@resources" ];
        LockPersonality = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
        RemoveIPC = true;
        UMask = "0077";
      };
    };
  };
}
