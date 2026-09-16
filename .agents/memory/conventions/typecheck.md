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

