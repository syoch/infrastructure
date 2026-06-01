{ config, pkgs, ... }:

{
  imports = [
    ./portal-service.nix
    ./web-infrastructure.nix
  ];
}
