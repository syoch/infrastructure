# Portal Python deps in Nix (single source of truth)

`python-deps.nix` is the only place the portal's Python dependency list lives.
It is a function `ps: with ps; [ fastapi uvicorn sqlalchemy pydantic python-multipart
psycopg2 websockets jsonschema ]`, consumed as `import ./python-deps.nix <ps>`.

Referenced from:
- `default.nix`: `propagatedBuildInputs = (import ./python-deps.nix python3Packages) ++ [ setuptools ]`
  (the package is called with `python3Packages = pkgs.python3Packages`).
- `flake.nix`: `portalPython = pkgs.python3.withPackages (ps: import ./python-deps.nix ps)`,
  used by `test-backend`/`test-e2e` runtimeInputs, `devShells.default` buildInputs, and the shellHook PATH.

Pitfall: `nix build`/`nix develop` only see Git-tracked files in a flake. A new `.nix` file must be
`git add`ed before it can be imported, otherwise: "Path ... is not tracked by Git".

Verify: `nix build .#portal --no-link`, `nix build .#test-backend .#test-e2e --no-link`,
`nix develop --command python3 -c "import fastapi, websockets, pydantic"`.

## First-party extensions in extensions/ (2026-09)
`default.nix` src fileset now unions `./extensions` (in addition to backend/frontend/pyproject.toml/
python-deps.nix) so setuptools' `package-dir` can find the `portal_*` packages. Built output installs
`portal_obtainium`, `portal_control_plane`, `portal_app_portal`, `portal_storage`, `backend`, and
`frontend` into site-packages; entry_points.txt carries the four `portal.extensions` IDs.
