{ config, pkgs, ... }:

{
  imports = [ ./portal-service.nix ];

  # Enable the portal backend service
  services.syoch-portal = {
    enable = true;
    configFile = pkgs.writeText "config.json" (builtins.toJSON {
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
            uploads_dir = "/mnt/NAS/Android Root/.tmp/prod/uploads";
          };
        }
        {
          module = "servers.obtainium_repo";
          class = "ObtainiumRepoExtension";
        }
      ];
    });
    
    readWritePaths = [
      "/var/lib/syoch-portal"
      "\"/mnt/NAS/Android Root/.tmp/prod/uploads\""
    ];
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
