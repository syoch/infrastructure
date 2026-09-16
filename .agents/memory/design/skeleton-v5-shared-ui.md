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
