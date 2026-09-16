# Skeleton v5 shared UI foundation (frontend/src)

Phase A migrated the portal frontend's shared UI to Skeleton v5 (Zag-based).

## Components / APIs
- `src/lib/toast.ts`: exports `toaster` (`createToaster({ placement:'bottom-end', overlap:true, gap:12 })`),
  `showToast(message, type='info', duration=3000)`, and legacy alias `showCustomToast(msg, type, duration)`.
  `ui.ts` no longer defines `showToast` (old DOM-hack `#custom-toast` removed).
  `Toast.Group` + toast anatomy rendered once in `src/routes/+layout.svelte`; toast elements carry
  `data-testid="toast"` / `data-testid="toast-title"`.
- `src/lib/dialogs.svelte.ts`: promise-based `confirmDialog(opts): Promise<boolean>` and
  `promptDialog(opts): Promise<string|null>` backed by module-level `$state` request objects.
  Hosts `src/lib/components/ConfirmDialog.svelte` / `PromptDialog.svelte` rendered once in `+layout.svelte`,
  portaled, `z-[90]/z-[100]`, `closeOnInteractOutside={false}`; testids `confirm-dialog`,
  `confirm-dialog-confirm`, `prompt-dialog`, `prompt-dialog-input`, `prompt-dialog-confirm`.
- `AppModal.svelte` / `CategoryModal.svelte` rewritten on Skeleton `Dialog` (keep ids `#app-modal`,
  `#category-modal`, inner form ids). Shell header/nav/footer uses Skeleton tokens; the control
  dropdown is Skeleton `Menu` (ids `#control-dropdown`/`#nav-control` kept, testids
  `control-menu`, `control-menu-devices`, `control-menu-acl`).

## Gotchas (cost real debugging)
1. **Skeleton `*.Title` / `element` snippet + id spread order:** if you render a custom element via
   `{#snippet element(attributes)}`, put your own `id`/`class` AFTER `{...attributes}`;
   Zag injects an auto id that otherwise overrides yours (`#app-modal-title` went missing).
2. **`not.toHaveClass()` fails on detached elements** (pre-existing repo note). With Skeleton dialogs the
   content unmounts when closed, so assert `toBeHidden()` (passes for detached) instead of class checks.
3. **Nested Skeleton dialogs** (confirm on top of app/category dialog) need explicit higher z-index
   (`z-[100]` positioner) than the modal (`z-[90]`).
4. Playwright `getByTestId('confirm-dialog-confirm')` replaces all native `page.once('dialog', …)` /
   `waitForEvent('dialog')` mocks; toast text replaces native `alert()` assertions.
5. Skeleton `Dialog.Trigger`/`Menu.Trigger` typing excludes `id` from props; to keep a DOM id use the
   `element` snippet (`<button {...attributes} id="…">`).
6. Escape: Skeleton Dialog closes itself via `onOpenChange` → wire that to `goto('/list')`; the old
   Dashboard `<svelte:window onkeydown>` `.modal-backdrop.active` navigation was removed.
   Operations.svelte still uses the legacy `.modal-backdrop.active` (left untouched).

## Verification (all green)
`svelte-check found 0 errors and 0 warnings`; `npm run build` writes `dist/`;
`make test-e2e` = 37 passed (port 8000 killed first).

## Update 2026-09-16: Control Plane views migrated (supersedes gotcha 6)
`src/views/Control.svelte` and `src/views/Operations.svelte` now use Skeleton v5:
- Control: `Switch` for the per-device admin toggle (controlled `checked={device.is_first_webui_device}`,
  `onCheckedChange` -> confirm; a cancelled confirm simply keeps state, no manual `.checked` revert),
  `input`/`select` classes, `table`+`table-wrap`, `badge preset-*` for WS state / token status,
  `btn preset-filled-primary-500` / `btn preset-tonal-error`.
- Operations: `Tabs` (root `value={activeTab}` + `onValueChange`, triggers `data-testid=tab-ops|tab-cmds`
  with `aria-selected`; contents keep ids `#ops-pane`/`#cmds-pane`), `Pagination`
  (`count`/`pageSize`/`page` from `Math.floor(offset/limit)+1`, `onPageChange` -> offset; Prev/Next
  keep ids `#cmds-page-prev|next`), filter `input`/`select` classes, `badge` for command status,
  provider `card` keeps class `.provider-card`.
- Operation-form modal is now a Skeleton `Dialog` (`id/data-testid=op-modal`, `#op-form`), replacing
  the legacy `.modal-backdrop.active`. E2E specs updated accordingly
  (`getByTestId('op-modal')`, `getByTestId('tab-cmds')` + `toHaveAttribute('aria-selected','true')`).
- Gotcha: template narrowing `{#if modalOp && modalNode}` does NOT propagate into a
  `Dialog.Title` `{#snippet element}`; compute `$derived` title/description strings instead.

## Obtainium views migration (Dashboard/Portal/AppEdit + modals)
`Portal.svelte`, `Dashboard.svelte`, `AppEdit.svelte`, `AppModal.svelte`, `CategoryModal.svelte` now use
Skeleton `table`/`input`/`select`/`checkbox`/`label-text`/`card`/`btn preset-*`/`badge`/`chip`/`h1..h5`
+ Tailwind utilities. All existing ids preserved (`#dashboard-apps-list`, `#apps-table-body`,
`#global-setting-*`, `#apk-*`, modal ids, …).
- Legacy test-hook classes were replaced by `data-testid`: `dashboard-list-section`, `app-name-text`,
  `category-tag`, `category-tags`, `app-row`, `empty-row`, and Portal `apps-table`. Both obtainium specs
  were updated accordingly (portal `.apps-table`→`[data-testid="apps-table"]` etc.).
- APK upload now uses Skeleton `FileUpload` (Zag). The native hidden input **keeps `id="apk-file-input"`**
  by passing `id` as a prop: Skeleton's `mergeProps(getHiddenInputProps(), rest)` applies `rest` last, so
  our id overrides Zag's auto id. Playwright `setInputFiles('#apk-file-input', …)` DOES trigger Zag
  `oninput` → `onFileChange`, so version/arch auto-fill works. Clearing after upload/populate is done by
  remounting via `{#key apkUploadKey}` (no `bind:this` input ref anymore).
- Sort headers are `<button>` inside `<th>` (ids kept on the button) to avoid a11y warnings.
- Verified locally without the portal server/port 8000: `npm run build` → `npx vite preview --port 5199`
  + Playwright route-mocking `/obtainium-export.json`, `/api/apps` (must return `{apps:[...]}` — a bare
  array yields empty), `/api/settings`, `/api/control/**`; then assert DOM + `setInputFiles`.

## Obtainium views: legacy style.css class removal (final pass)
Removed the last `frontend/style.css`-defined classes from `Dashboard.svelte`, `Portal.svelte`,
`AppEdit.svelte`, `SchemaForm.svelte`, `SchemaEditor.svelte` (so `style.css` can be deleted).
- `btn-secondary` → Skeleton `btn preset-tonal` (SchemaForm/SchemaEditor). `dashboard-card` /
  `app-identity` / `table-actions` / `source-identity` / `source-type` were already redundant with
  existing utilities, so the class was simply dropped.
- `search-box`/`hero-section`/`empty-state`/`directory-section`/`version-text`/`apk-table`/
  `apk-hash-text`/`upload-dropzone-*` recreated with Tailwind tokens (e.g. `pt-16 pb-10 text-center`,
  `rounded border border-secondary-500/10 bg-secondary-500/5 px-1.5 py-0.5`, `break-all font-semibold
  text-success-500`).
- **`btn-sm` gotcha:** Skeleton v5 DOES define a `btn-sm` `@utility` (sets `--btn-size: var(--text-sm)`)
  — but style.css also defined `.btn-sm`, and the deletion task's grep forbade the literal `btn-sm`.
  Exact equivalent used instead: arbitrary property `[--btn-size:var(--text-sm)]` (verified emitted in
  the built CSS and ordered after `.btn`).
- **Paired-color gotcha:** Skeleton only ships specific light/dark token pairs
  (`surface-50-950,100-900,200-800,300-700,600-400,700-300,900-100,950-50`). `surface-500-400` does NOT
  exist and Tailwind silently emits nothing → use `surface-600-400` for muted text/placeholders.
- Spec hook: `.delete-apk-btn` class removed; button now `data-testid="apk-delete-btn"` and
  `dashboard.spec.js` locator updated to `#apk-list-tbody [data-testid="apk-delete-btn"]`
  (name avoids the forbidden `delete-apk-btn` substring).
- Verified: `svelte-check found 0 errors and 0 warnings`; `npm run build` succeeds.

## Obtainium pages refactor: self-contained pages + granular components (2026-09-17, supersedes "views")
Deleted `src/views/{Dashboard,AppEdit,Portal}.svelte` entirely. The `src/views/` directory is now gone
for all features (app_portal/control_plane did the same concurrently). New convention:
**each `src/routes/**/+page.svelte` is a composition root that reads its own params/search params**, and
never imports a whole view from `src/views/`.
- New `src/components/obtainium/`: `SortHeader`, `DashboardHeader`, `CategoriesBar`, `AppsTable`,
  `PortalAppsTable`, `GlobalSettingsPanel`, `SystemBackupPanel`, `AppEditHeader`, `AppDetailedForm`,
  `SelfHostedApkManager`, plus moved `AppModal`/`CategoryModal` (were `src/components/`).
- Page → components:
  - `/` → hero + search/filter + `PortalAppsTable` (sort state lives in the page).
  - `/dashboard`, `/list` → `DashboardHeader`+`CategoriesBar`+`AppsTable`+`GlobalSettingsPanel`+`SystemBackupPanel`.
  - `/new` → same dashboard set + `AppModal`(active `type=app`) / `CategoryModal`(active `type=category`).
  - `/edit` → `type=app`: `AppEditHeader`+`AppDetailedForm`+`SelfHostedApkManager`; else dashboard set with
    route-driven quick-app/category modals.
- Cross-component state on `/edit?type=app`: the page owns `appSource` (`bind:appSource` into
  `AppDetailedForm`) and passes `isSelfHosted={appSource === 'HTML'}` to `SelfHostedApkManager`, preserving
  the original "changing source to HTML reveals the APK card" behaviour.
- Gotcha: `SortHeader` receives `onclick` as a normal Svelte 5 component callback prop and applies it to
  the DOM `<button {onclick}>`; icon id must be `id={iconId}` (a bare `{iconId}` would become the wrong attr).
- All existing ids/`data-testid` preserved verbatim → obtainium specs unchanged. Gates: svelte-check
  0 errors/0 warnings, `npm run build` OK, `ls src/views` → no such directory.
