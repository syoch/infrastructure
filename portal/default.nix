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
}:

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

  # public ディレクトリなど、実行時に必要な静的ファイルを site-packages にコピー
  postInstall = ''
    SITE_PACKAGES=$out/${python.sitePackages}
    cp -r public $SITE_PACKAGES/
    # もし他に実行時に必要なディレクトリがあればコピーする
    # cp -r docs $SITE_PACKAGES/
  '';

  meta = with lib; {
    description = "Android Device Provisioning Portal";
    license = licenses.mit; # 適宜変更
    maintainers = [ ];
  };
}
