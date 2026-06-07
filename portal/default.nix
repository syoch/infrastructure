{
  lib,
  buildPythonApplication,
  python,
  fastapi,
  uvicorn,
  sqlalchemy,
  pydantic,
  python-multipart,
  psycopg2,
  websockets,
  jsonschema,
  setuptools,
  buildNpmPackage,
}:

let
  frontend = buildNpmPackage {
    pname = "portal-frontend";
    version = "0.1.0";
    src = ./public;
    npmDepsHash = "sha256-NE75Agamw3ztrgvbCD66JL5TIQbVgx1Eb+2Su40tmno=";
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

  propagatedBuildInputs = [
    fastapi
    uvicorn
    sqlalchemy
    pydantic
    python-multipart
    psycopg2
    websockets
    jsonschema
    setuptools
  ];

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
