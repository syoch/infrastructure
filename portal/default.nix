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
    src = ./public;
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

  src = ./.;

  propagatedBuildInputs = (import ./python-deps.nix python3Packages) ++ [ setuptools ];

  # ビルド時にフロントエンドの成果物を取り込む
  postInstall = ''
    SITE_PACKAGES=$out/${python.sitePackages}
    cp -r public $SITE_PACKAGES/
    # ビルド済みの dist を derivation からコピー（ソースの dist を上書き）
    rm -rf $SITE_PACKAGES/public/dist
    cp -r ${frontend}/dist $SITE_PACKAGES/public/
  '';

  meta = with lib; {
    description = "Android Device Provisioning Portal";
    license = licenses.mit;
    maintainers = [ ];
  };
}
