# Svelte Control Plane + JSON Schema migration (portal/public/src)

Migrated the control-plane area from vanilla `js/control_*.ts` to Svelte 5:
- `src/views/Control.svelte` (bootstrap form / Devices / ACL; admin visibility from `auth.me.is_first_webui_device`)
- `src/views/Operations.svelte` (ops + commands tabs, provider cards, filter/pagination/hash sync, SSE)
- `src/components/SchemaForm.svelte`, `src/components/SchemaEditor.svelte` (recursive, self-import)
- `src/lib/schema.svelte.ts` (reactive `SchemaNode` value model + editor state; runes in class fields)
- `js/schema_api.ts` rewritten as an imperative adapter that `mount()`s the Svelte components and reads the model (`getValue`/`getSchema`)
Deleted: control_bootstrap/devices/acl/operations/op_renderer + schema_renderer/editor (.ts).
`js/control_router.ts` and `app.ts` are now orphaned (not Vite inputs) but intentionally left.

## Non-obvious constraints
1. **Never call `ensureMe()` (or any shared `$state` reader/writer) synchronously inside a `$effect`.**
   `src/lib/auth.svelte.ts` uses `$state`; reading `auth.loaded`/writing it (`ensureMe(true)`) inside the
   effect registers a dependency → infinite re-render/loop (symptoms: forms detached from DOM,
   Playwright "element is not stable/detached"). Fix: capture reactive deps first, then run the async
   work inside `untrack(() => { void load(...) })` from `svelte`.
2. **`ensureMe()` caches a null result when there is no token.** Direct hash navigation after setting
   `localStorage` (same-document `page.goto('/#/...')`) does not remount, so the app must force a fresh
   fetch (`ensureMe(true)`) in Control, otherwise it sticks on the bootstrap form.
3. **Schema test harness mutates DOM values directly.** `public-static/test_schema_renderer.html` now
   dispatches bubbling `input`/`change` events after setting `.value`/`.checked`. Structural Svelte
   changes (array add, oneOf variant switch) need `flushSync()` inside the handler so the harness's
   immediate `querySelectorAll` sees the new nodes.
4. `mount(Component, {target, props})` renders synchronously and returns component exports; components
   can import themselves for recursion (replaces `svelte:self`).
5. Vue of `#cmds-pane td:nth-child(5)` = status, `td:nth-child(8)` = result (kept column order).

## Verification (all pass)
- `nix develop --command bash -c "cd portal/public && npm run build"` (no new a11y warnings)
- Playwright: control_split.spec.js + schema_renderer.spec.js + device_agent_integration.spec.js = 16 passed.
