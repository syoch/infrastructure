{ config, pkgs, ... }:

{
  imports = [ ./portal-service.nix ];

  # Enable the portal backend service
  services.portal = {
    enable = true;
    port = 8000;
    host = "127.0.0.1";
  };

  # Global ACME settings
  security.acme = {
    acceptTerms = true;
    defaults.email = "syoch64@example.com";
  };

  # Nginx Reverse Proxy with TLS integration
  services.nginx = {
    enable = true;
    recommendedProxySettings = true;
    recommendedTlsSettings = true;

    virtualHosts = {
      "kgoelamv.syoch.f5.si" = {
        enableACME = true;
        forceSSL = true;
        locations."/" = {
          proxyPass = "http://127.0.0.1:8000";
          proxyWebsockets = true;
        };
      };
      "btwainft.syoch.f5.si" = {
        enableACME = true;
        forceSSL = true;
        locations."/" = {
          proxyPass = "http://127.0.0.1:8000";
          proxyWebsockets = true;
        };
      };
    };
  };
}
