# Portal Python deps in Nix (single source of truth)

`portal/python-deps.nix` is the only place the portal's Python dependency list lives.
It is a function `ps: with ps; [ fastapi uvicorn sqlalchemy pydantic python-multipart
psycopg2 websockets jsonschema ]`, consumed as `import ./portal/python-deps.nix <ps>`.

Referenced from:
- `portal/default.nix`: `propagatedBuildInputs = (import ./python-deps.nix python3Packages) ++ [ setuptools ]`
  (the package is called with `python3Packages = pkgs.python3Packages`).
- `flake.nix`: `portalPython = pkgs.python3.withPackages (ps: import ./portal/python-deps.nix ps)`,
  used by `test-backend`/`test-e2e` runtimeInputs, `devShells.default` buildInputs, and the shellHook PATH.

Pitfall: `nix build`/`nix develop` only see Git-tracked files in a flake. A new `.nix` file must be
`git add`ed before it can be imported, otherwise: "Path ... is not tracked by Git".

Verify: `nix build .#portal --no-link`, `nix build .#test-backend .#test-e2e --no-link`,
`nix develop --command python3 -c "import fastapi, websockets, pydantic"`.
