# Adding a portal extension from outside this repository

Portal extensions are Python classes that subclass `backend.extensions.base.BaseExtension`
and are selected per deployment by a stable **ID** in the portal config. First-party
extensions live in `backend/{obtainium,control_plane,app_portal,storage}`; this document
shows how a **third-party package** can add an extension without editing this repository.

Reference implementation: [`examples/hello_extension/`](../examples/hello_extension).

## 1. The extension contract

Subclass `BaseExtension` and declare an `ID` (used by config) and `tags` (used for
service lookup via `host.get_extension(tags=[...])`):

```python
from fastapi import APIRouter
from backend.extensions.base import BaseExtension


class HelloExtension(BaseExtension):
    ID = "hello"

    def __init__(self, core_config, ext_config=None):
        super().__init__(core_config)
        self.ext_config = ext_config or {}
        self.tags = ["greeting"]
        self.router = self._build_router()   # mounted by the server

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/hello", tags=["hello"])

        @router.get("")
        def hello():
            return {"message": self.ext_config.get("greeting", "hello")}

        return router
```

Available hooks (all optional):

| Member | Purpose |
|--------|---------|
| `ID: str` | stable id referenced by config |
| `tags: list[str]` | capability tags for `host.get_extension(tags=...)` |
| `router` (attribute) | `APIRouter` mounted on the app; may be set in `__init__`/`setup` |
| `setup()` | called once at server startup and before CLI registration |
| `register_cli_commands(subparsers)` | add `manage.py` subcommands (`parser.set_defaults(func=...)`) |
| `backup_data(session)` / `restore_data(session, data, strategy)` | DB backup/restore hooks |
| `get_backup_directories()` / `restore_directories(temp_dir)` | physical file backup hooks |
| `get_referenced_file_hashes(session)` | declare hashes for storage GC |
| `get_startup_info(local_ip)` | extra startup log lines |

The constructor signature is always `(core_config, ext_config)`; `ext_config` is the
per-extension `config` object from the portal config.

## 2. Register the ID (entry point)

External distributions are discovered through the `portal.extensions` entry-point group.
In the extension's `pyproject.toml`:

```toml
[project]
name = "portal-hello-extension"
version = "0.1.0"
dependencies = ["portal", "fastapi"]   # "portal" provides BaseExtension

[project.entry-points."portal.extensions"]
hello = "hello_extension.extension:HelloExtension"
```

`backend/core/extensions.py` merges this with the first-party `EXTENSION_REGISTRY`, so
`hello` becomes a valid ID. (First-party code can also add a plain entry to
`EXTENSION_REGISTRY`.) If an external ID collides with a built-in one, the external
target wins and a warning is logged.

## 3. Install and select it

Install the extension into the same Python environment as the portal, then list its ID
in the config's `extensions` array:

```json
{
  "server": { "port": 8000, "host": "0.0.0.0" },
  "extensions": [
    { "id": "hello", "config": { "greeting": "hi" } },
    { "id": "obtainium" }
  ]
}
```

Entries are either `"<id>"` or `{"id": "<id>", "config": {...}}`. Unknown IDs abort
startup (fail fast), so a typo is caught immediately.

Local development install:

```bash
python3 -m pip install -e examples/hello_extension
python3 backend/manage.py --config tests/config.test.json hello world   # CLI hook
python3 backend/app.py --config <cfg>                                   # mounts /api/hello
```

## 4. Deploying with Nix

The `services.portal` module builds a fixed Python environment (`default.nix`). To ship an
external extension, provide an environment that contains both `portal` and the extension
and point the service at it. Sketch:

```nix
let
  portal = pkgs.python3Packages.callPackage ./default.nix { buildNpmPackage = pkgs.buildNpmPackage; };
  hello = pkgs.python3Packages.buildPythonPackage {
    pname = "portal-hello-extension";
    version = "0.1.0";
    src = ./examples/hello_extension;
    propagatedBuildInputs = [ portal pkgs.python3Packages.fastapi ];
    pyproject = true;
  };
  env = pkgs.python3.withPackages (_: [ portal hello ]);
in
{
  services.portal.enable = true;
  # override ExecStart to use `env`; see the module options for configFile/readWritePaths
}
```

Alternatively keep extensions inside the repository (adding an `EXTENSION_REGISTRY`
entry) and they are bundled into `packages.portal` automatically.

## 5. Caveats

- Extensions are **not hot-reloaded**; restart the service after changing them.
- An external extension runs arbitrary in-process Python — only install trusted packages.
- `backup_data` is stored under the extension **class name** in the backup tarball
  (existing on-disk format); keep class names stable, or write a migration.
- Prefer registering new capability tags rather than overloading existing ones
  (`storage-provider`, `index-compiler`, `control-plane`, `app-portal`).

## 6. Verification

```bash
# Discovery without installing anything (fakes an entry point):
python3 backend/core/tests/test_external_extension.py

# With the example installed:
python3 -m pip install -e examples/hello_extension
curl -s localhost:8000/api/hello
```
