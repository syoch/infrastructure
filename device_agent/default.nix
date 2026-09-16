{
  lib,
  buildPythonApplication,
  setuptools,
  websockets,
  jsonschema,
}:

buildPythonApplication {
  pname = "portal-device-agent";
  version = "0.1.0";
  pyproject = true;

  src = ./.;

  propagatedBuildInputs = [
    websockets
    jsonschema
  ];

  nativeBuildInputs = [ setuptools ];

  meta = with lib; {
    description = "Portal control-plane device agent (standalone)";
    license = licenses.mit;
    maintainers = [ ];
  };
}
