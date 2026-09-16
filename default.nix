{
  lib,
  buildPythonApplication,
  python,
  setuptools,
  buildNpmPackage,
}:

let
  frontend = buildNpmPackage {
    pname = "portal-frontend";
    version = "0.1.0";
    src = ./frontend;
    npmDepsHash = "sha256-4txrj/kQV68/cuG9wd1j3WSRAvbzesLv+ZeVTbSkvJM=";
    installPhase = ''
      mkdir -p $out
      cp -r dist $out/
    '';
  };
in
buildPythonApplication {
  pname = "portal";
  version = "0.1.0";
  pyproject = true;

  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./backend
      ./extensions
      ./frontend
      ./pyproject.toml
      ./python-deps.nix
    ];
  };

  propagatedBuildInputs = (import ./python-deps.nix python.pkgs) ++ [ setuptools ];

  # ビルド時にフロントエンドの成果物を取り込む
  postInstall = ''
    SITE_PACKAGES=$out/${python.sitePackages}
    cp -r frontend $SITE_PACKAGES/
    # ビルド済みの dist を derivation からコピー（ソースの dist を上書き）
    rm -rf $SITE_PACKAGES/frontend/dist
    cp -r ${frontend}/dist $SITE_PACKAGES/frontend/
  '';

  meta = with lib; {
    description = "Android Device Provisioning Portal";
    license = licenses.mit;
    maintainers = [ ];
  };
}
