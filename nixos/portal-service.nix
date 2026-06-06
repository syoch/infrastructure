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

    bridge = {
      enable = mkOption {
        type = types.bool;
        default = true;
        description = "Whether to run the control-plane bridge as a separate systemd unit.";
      };

      bootstrapTokenFile = mkOption {
        type = types.nullOr types.path;
        default = null;
        description = "Path to a file containing the bootstrap token for the bridge device. Required if bridge.enable.";
      };

      serverUrl = mkOption {
        type = types.str;
        default = "http://127.0.0.1:8000";
        description = "Base URL of the portal server that the bridge connects to.";
      };
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

    systemd.services.syoch-portal-bridge = mkIf cfg.bridge.enable {
      description = "Portal control-plane bridge (dogfood: exposes acl.* and device_admin.* via WebSocket)";
      after = [ "syoch-portal.service" "network.target" ];
      wantedBy = [ "multi-user.target" ];
      requires = [ "syoch-portal.service" ];

      serviceConfig = mkIf (cfg.bridge.bootstrapTokenFile != null) {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        StateDirectory = "syoch-portal";

        ExecStart = "${portalPkg}/bin/portal-control-bridge --server-url ${cfg.bridge.serverUrl} --bootstrap-token $(cat ${cfg.bridge.bootstrapTokenFile}) --config ${cfg.configFile}";
        Restart = "always";
        RestartSec = 5;

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
