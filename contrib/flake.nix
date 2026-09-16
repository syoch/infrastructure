{
  description = "Non-portal odds and ends: Android rooting tools, Minecraft Bedrock server, Tailscale helper";

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
      in
      rec {
        packages = {
          magisk = pkgs.fetchurl {
            url = "https://github.com/topjohnwu/Magisk/releases/download/v30.7/app-debug.apk";
            hash = "sha256-QHKVJeKYoR2tbhNYainvpIpI6Xy/ACA3mOgEfRxxDLI=";
          };

          magiskboot =
            let
              sys = if system == "x86_64-linux" then "x86_64" else "arm64";
              exe_path = "lib/${sys}/libmagiskboot.so";
            in
            pkgs.stdenv.mkDerivation {
              name = "magiskboot";
              version = "30.7";
              src = packages.magisk;
              unpackPhase = ''
                mkdir -p $out
                ${pkgs.unzip}/bin/unzip -j $src "${exe_path}" -d $out
              '';
              buildPhase = ''
                mkdir -p $out/bin
                mv $out/libmagiskboot.so $out/bin/magiskboot
                chmod +x $out/bin/magiskboot
              '';
            };

          ksud-next = pkgs.stdenv.mkDerivation {
            name = "ksud-next";
            version = "3.2.0";
            src = pkgs.fetchurl (
              if system == "x86_64-linux" then
                {
                  url = "https://github.com/KernelSU-Next/KernelSU-Next/releases/download/v3.2.0/ksud-x86_64-unknown-linux-musl";
                  hash = "sha256-NUi3XwR2HvBiy1KmPuaOS9W4b6LQEDIChybz6kjOd50=";
                }
              else if system == "aarch64-linux" then
                {
                  url = "https://github.com/KernelSU-Next/KernelSU-Next/releases/download/v3.2.0/ksud-aarch64-unknown-linux-musl";
                  hash = "";
                }
              else
                throw "Unsupported system: ${system}"
            );

            unpackPhase = "true";

            buildPhase = ''
              mkdir -p $out/bin
              cp $src $out/bin/ksud-next
              chmod +x $out/bin/ksud-next
            '';
          };
        };

        apps.ksud-next = {
          type = "app";
          program = "${packages.ksud-next}/bin/ksud-next";
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            aapt
            android-tools
            dtc
            usbutils
            sunxi-tools
            scrcpy
            unzip
            git
            openssl
          ];
        };
      }
    );
}
