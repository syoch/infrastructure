# Svelte 5 Dashboard migration (portal/public/src)

Dashboard + app-edit views migrated from vanilla `js/dashboard.ts` to:
- `src/views/Dashboard.svelte` (list, categories bar, global settings, backup/restore, route-driven modals)
- `src/views/AppEdit.svelte` (detailed editor, self-hosted APK card)
- `src/components/AppModal.svelte`, `src/components/CategoryModal.svelte`
- `src/lib/toast.ts` (`showCustomToast`, body-level `#custom-toast`)

## Non-obvious constraints discovered

1. **Playwright `expect(locator).not.toHaveClass()` FAILS if the element is detached.**
   `_expectCore` returns `matches: options.isNot` for missing elements, but the client
   matcher does not treat detached as success. Verified empirically. Therefore the modal
   DOM contract (`#app-modal`, `#category-modal`) must exist on the `#edit?type=app` route.
   Fix: `AppEdit.svelte` renders `<AppModal active={false}/>` and
   `<CategoryModal active={false}/>` so the nodes persist when Dashboard unmounts.
   (By contrast `not.toBeVisible()` *does* pass for detached elements.)

2. **`<!-- svelte-ignore a11y_click_events_have_key_events -->` does not suppress the
   warning.** Using `onclick` on `<span>` still warns. Convert interactive tags to
   `<button type="button" class="category-tag ...">` instead. `a11y_no_static_element_interactions`
   *is* suppressible via svelte-ignore (used for the APK dropzone div with drag handlers).

3. Dashboard route strings must be `#list` (no slash). E2E regex is `/#list|#$/`; `#/list`
   does not match. Use `navigate('#list')`, not `'#/list'`.

4. `.ts` extension imports (e.g. `'../lib/store.svelte.ts'`) are the project convention and
   work in Vite build, but `npm run typecheck` (svelte-check) reports
   `allowImportingTsExtensions` errors for all migrated files. This is pre-existing; not fixed.

5. `npm run typecheck` is not part of required verification; the gate is
   `nix develop --command bash -c "cd portal/public && npm run build"` then Playwright
   `dashboard.spec.js` (12 tests). Server serves `portal/public/dist`.

## Verification result (2026-09-15)
- `npm run build`: OK, no new a11y warnings (16 pre-existing AppPortal label warnings remain).
- `npx playwright test dashboard.spec.js`: 12 passed.
