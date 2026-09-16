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
- pyproject `[tool.mypy]` is auto-discovered when mypy runs from `portal/` — no extra flags needed.
