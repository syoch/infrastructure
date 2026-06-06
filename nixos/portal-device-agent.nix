{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services.syoch-portal-device-agent;
  portalPkg = pkgs.python3Packages.callPackage ../portal { };
in
{
  options.services.syoch-portal-device-agent = {
    enable = mkEnableOption "Portal control-plane device agent";

    configFile = mkOption {
      type = types.path;
      description = "Path to the device agent's config.json.";
    };

    bootstrapTokenFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "Path to a file containing the bootstrap token (used only on first run; subsequent runs use the saved bearer token).";
    };

    serverUrl = mkOption {
      type = types.str;
      default = "http://127.0.0.1:8000";
      description = "Base URL of the portal server that the agent connects to.";
    };

    user = mkOption {
      type = types.str;
      default = "syoch-portal-device-agent";
      description = "User account under which the service runs.";
    };

    group = mkOption {
      type = types.str;
      default = "syoch-portal-device-agent";
      description = "Group under which the service runs.";
    };

    stateDirectory = mkOption {
      type = types.str;
      default = "syoch-portal-device-agent";
      description = "State directory (used for the credentials file).";
    };
  };

  config = mkIf cfg.enable {
    users.users = lib.optionalAttrs (cfg.user == "syoch-portal-device-agent") {
      syoch-portal-device-agent = {
        isSystemUser = true;
        group = cfg.group;
        description = "Portal control-plane device agent";
      };
    };

    users.groups = lib.optionalAttrs (cfg.group == "syoch-portal-device-agent") {
      syoch-portal-device-agent = { };
    };

    systemd.services.syoch-portal-device-agent = {
      description = "Portal control-plane device agent";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        StateDirectory = cfg.stateDirectory;

        ExecStart = "${portalPkg}/bin/portal-device-agent --config ${cfg.configFile}";
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
