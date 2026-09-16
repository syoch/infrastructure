# Type checking (portal)

## Gate
`make typecheck` runs both:
1. `cd frontend && npm run typecheck` (svelte-check; `tsconfig.json` needs `noEmit: true` + `allowImportingTsExtensions: true` for `.svelte.ts` imports)
2. `mypy backend device_agent`

Run inside `nix develop` (devShell now provides `mypy`; the devShell python also has sqlalchemy so the plugin is importable).

## mypy config (`pyproject.toml [tool.mypy]`)
`python_version=3.12`, `mypy_path="."`, `explicit_package_bases`, `namespace_packages`, `ignore_missing_imports`, `follow_imports="silent"`, `check_untyped_defs`, `no_implicit_optional`, `plugins=["sqlalchemy.ext.mypy.plugin"]`, `exclude=["tests/","build/"]`.

## Pitfalls
- `ruff check` is a **linter, not a type checker**. It cannot replace mypy for type errors (it can catch undefined names / unused imports, but not `Column[str]` vs `str`). Repo has no `[tool.ruff]` config; default rules reported ~458 findings.
- SQLAlchemy 2.0.40 + mypy plugin: legacy `Column()` attributes are inferred as `T | None` **regardless of `nullable=False`**. To get a non-Optional type you must annotate the left-hand side with `Mapped[...]` (e.g. `bridge_device_id: Mapped[str] = Column(String(64), nullable=False, index=True)`), or use `cast` at the use-site.
- `relationship()` attributes likewise need explicit `Mapped`/collection annotations (`categories: Mapped[list["Category"]] = relationship(...)`) or the plugin errors with "Can't infer scalar or collection".
- Without the plugin, plain `Column` attributes surface as `Column[str]` and produce many `arg-type` errors.
- pyproject `[tool.mypy]` is auto-discovered when mypy runs from the repo root — no extra flags needed.

## Strict flags enabled (2026-09)
`[tool.mypy]` additionally sets `disallow_any_generics = true`, `disallow_untyped_defs = true`,
`disallow_incomplete_defs = true` (plus `warn_return_any = true`). `mypy backend device_agent`
= Success across 47 source files; `make typecheck` (svelte-check + mypy) passes.

### Patterns used to satisfy strict mypy without behavior change
- Every function/method (incl. nested defs) needs params + return annotations. Use concrete types:
  `dict[str, Any]`, `list[str]`, `set[str]`, `tuple[int, str, str]`, `asyncio.Queue[dict[str, Any]]`,
  `Callable[[], Session]`, ORM types.
- FastAPI handlers: annotate deps as `Any` (e.g. `device: Any = Depends(...)`,
  `_admin: Any = Depends(require_admin_device)`) and return `dict[str, Any]` / `FileResponse` /
  `StreamingResponse`.
- `warn_return_any`: a value from `json.loads(...)`/`request.get(...)` is `Any`; assign it to an
  explicitly-annotated local (`pending: list[dict[str, Any]] = ...`) to avoid returning `Any`
  without `cast`.
- Legacy `Column()` with `nullable=False` is still inferred `T | None`; fix at the model with a
  left-hand `Mapped[...]` (`Device.bearer_token`, `DeviceACL.created_at`, `CommandRequest.created_at`,
  `App.url`, `Setting.key`). `Optional[...]` return values need an explicit `return None` (bare
  `return` is rejected).
- Keep `device_agent/` standalone: use local types/`Any`, never import from `backend`.


## FastAPI JSON responses: TypedDict + Pydantic response_model (2026-09)
REST response bodies are typed with `TypedDict`s (control-plane in `extensions/control_plane/portal_control_plane/api_common.py`;
app-portal in `extensions/app_portal/portal_app_portal/responses.py`; obtainium in `extensions/obtainium/portal_obtainium/responses.py`; storage +
api_backup define them locally). Serializers (`_device_to_dict` etc.) return the TypedDicts.
- **Mandatory rule:** FastAPI uses a handler's return annotation as `response_model` when the decorator
  does not set one. Leaving it unset with a bare `dict[str, Any]`-style TypedDict return is a silent
  behavior change (FastAPI would validate/serialize through the annotation). The current convention is to
  give every JSON route an explicit Pydantic `BaseModel` `response_model` (see below), NOT
  `response_model=None` (that was the older stopgap, now removed repo-wide).
- **Pydantic response models mirror the TypedDicts** next to them and are set as
  `response_model=<Model>` so `/openapi.json` gains response schemas (control-plane: `DeviceOut`/`ACLOut`/
  `OperationOut`/`CommandOut`/`TokenOut` + `*ListOut` wrappers + `DeleteOut`; app-portal: `FeedbackOut`/
  `AppOut`/`BridgeOut` + wrappers + `BridgeAnnounceOut`/`DeleteOut`; obtainium: `LocalApkOut`/
  `ObtainiumAppOut` + `ObtainiumAppsOut`/`StatusMessageOut`/`StatusMessageCountOut`/`LocalApkUploadOut`;
  storage: `StorageFileOut`/`StorageUploadOut`/`StorageDeleteOut`; api_backup: `StatusMessageOut`).
- **Conditional (`NotRequired`) keys** (`DeviceDict.bearer_token`, `AppDict.feedback`) are declared with a
  default in the model and the route sets `response_model_exclude_unset=True` (device list/me/register,
  app get/list/create/patch) so the key stays absent rather than becoming `null`. `None`-able fields stay
  nullable (no `exclude_none`) so literal `null` is still emitted.
- Any stays Any for dynamic payloads (`params`, `result`, `params_schema`, `ui_hint`,
  `additionalSettings`). Genuinely dynamic routes stay unmodeled: obtainium `serve_settings_api`
  (arbitrary setting keys), `serve_export` (compiled export), `/api/settings`; binary/streaming routes
  (`/api/backup`, `/api/storage/files/{hash}` download, `/api/apps/download/*`, `/api/control/events`
  SSE, `scrape-index.html`) keep no JSON model.
- Verification gate after such changes: `make typecheck` (svelte-check 0 + mypy Success); reset port 8000 +
  `rm -f tests/portal_test.db*` + `make test-backend` EXIT 0; `make test-e2e` 37 passed. OpenAPI check:
  `python3 backend/app.py --config tests/config.test.json` then grep the new model names under
  `components.schemas` and confirm affected paths declare `$ref` response schemas.

## Extensions moved out of backend (2026-09)
`make typecheck` now runs:
`mypy backend device_agent extensions/obtainium/portal_obtainium extensions/control_plane/portal_control_plane extensions/app_portal/portal_app_portal extensions/storage/portal_storage`
= Success in 53 source files. `[tool.mypy] mypy_path` includes the four extension package dirs
(`.:extensions/obtainium:extensions/control_plane:extensions/app_portal:extensions/storage`) so
cross-package `portal_*` imports resolve; `exclude=["tests/","build/"]` still skips all test dirs.
Delete `.mypy_cache` after moving packages (stale `backend.<feature>` module entries).
