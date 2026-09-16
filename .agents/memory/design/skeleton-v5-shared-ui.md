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
