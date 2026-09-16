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


## FastAPI JSON responses typed with TypedDict (2026-09)
REST response bodies are now typed with `TypedDict`s (control-plane in `backend/control_plane/api_common.py`;
app-portal in `backend/app_portal/responses.py`; obtainium in `backend/obtainium/responses.py`; storage +
api_backup define them locally). Serializers (`_device_to_dict` etc.) return the TypedDicts.
- **Mandatory rule:** FastAPI uses a handler's return annotation as `response_model`. Whenever a handler's
  annotation changed from `dict[str, Any]` to a TypedDict, the route decorator MUST also set
  `response_model=None` (e.g. `@router.get("/devices", response_model=None)`) to preserve the old runtime
  behavior (no validation/serialization change). Forgetting it is a silent behavior change.
- Genuinely dynamic payloads stay `dict[str, Any]` with no `response_model` change:
  obtainium `serve_settings_api` (arbitrary setting keys), `serve_export` (compiled export), control-plane
  `api.py` (router wiring only, no dicts). `_opencode_meta`/`_parse_op_result` are internal, not responses.
- Use `NotRequired[...]` for conditionally present keys (`DeviceDict.bearer_token`, `AppDict.feedback`).
- Legacy `Column(...)` non-null columns read into a TypedDict were promoted to `Mapped[...]` on the model
  (DeviceBootstrapToken.device_id/display_name/created_at, OperationSpec.params_schema,
  WebApp/Feedback/Bridge many fields, obtainium App.pinned/allow_id_change/additional_settings,
  LocalAppAPK.id, Category.name/color) rather than lying in the TypedDict.
- Verification gate after such changes: `mypy backend device_agent` Success; reset port 8000 +
  `rm -f tests/portal_test.db*` + `make test-backend` EXIT 0; `make typecheck`; `make test-e2e` 37 passed.
