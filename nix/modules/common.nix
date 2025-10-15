# Common NixOS configuration shared between production and VM
{ config, pkgs, lib, ... }:

let
  # Parse .env file (simple key=value format)
  parseEnvLine = line:
    let
      parts = lib.splitString "=" line;
      key = builtins.head parts;
      value = lib.concatStringsSep "=" (builtins.tail parts);
    in
      lib.nameValuePair key value;

  parseEnvFile = content:
    builtins.listToAttrs (
      map parseEnvLine (
        lib.filter (line: line != "" && !(lib.hasPrefix "#" line))
          (lib.splitString "\n" content)
      )
    );
in
{
  options = {
    infrastructure = {
      # Tailscale configuration
      tailscaleEnv = lib.mkOption {
        type = lib.types.str;
        description = "Tailscale environment variables as string";
      };

      tailscaleConfig = lib.mkOption {
        type = lib.types.attrs;
        default = parseEnvFile config.infrastructure.tailscaleEnv;
        description = "Parsed Tailscale configuration";
      };

      projectDir = lib.mkOption {
        type = lib.types.str;
        description = "Project directory path";
      };

      isProduction = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Whether this is a production environment";
      };
    };
  };

  config = {
    # System version
    system.stateVersion = "24.05";

    # Networking
    networking.hostName = config.infrastructure.tailscaleConfig.TS_HOSTNAME or "nixos-server";

    # Firewall - allow HTTP/HTTPS
    networking.firewall = {
      enable = true;
      allowedTCPPorts = [ 80 443 ];
    };

    # Nginx web server
    services.nginx = {
      enable = true;
      user = "nginx";
      group = "nginx";
    };

    # User configuration
    users.users.syoch = {
      isNormalUser = true;
      extraGroups = [ "wheel" "nginx" ];
    };

    # SSH server
    services.openssh = {
      enable = true;
    };

    # Git for deployment
    programs.git.enable = true;

    # Common system packages
    environment.systemPackages = with pkgs; [
      vim
      htop
      curl
      wget
      git
    ];
  };
}
