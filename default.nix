{
  lib,
  buildPythonApplication,
  python,
  python3Packages,
  setuptools,
  buildNpmPackage,
}:

let
  frontend = buildNpmPackage {
    pname = "portal-frontend";
    version = "0.1.0";
    src = ./frontend;
    npmDepsHash = "sha256-XdJHWJvT5ZZeA/8yWJWbXO1mvhgogG3lEHQY1gUpdhM=";
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
      ./device_agent
      ./frontend
      ./pyproject.toml
      ./python-deps.nix
    ];
  };

  propagatedBuildInputs = (import ./python-deps.nix python3Packages) ++ [ setuptools ];

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
