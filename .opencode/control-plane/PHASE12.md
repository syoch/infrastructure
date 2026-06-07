# Phase 12: Control UI Split into Multiple Routes

**Status**: DONE

## Goal
Split the monolithic Control dashboard into focused, navigable sub-pages. Provide
filtering and pagination for the Commands list, and make the navigation
discoverable via a top-level dropdown. Each screen has a clear, single
responsibility; URL state is preserved across reloads.

## Routes

| Route                              | Section                | Visibility           |
| ---------------------------------- | ---------------------- | -------------------- |
| `#/control`                        | Bootstrap landing      | All users            |
| `#/control/devices`                | Devices table          | Authenticated        |
| `#/control/acl`                    | ACL form + table       | Admin only (in-page guard for non-admin) |
| `#/operations`                     | Operations + Commands  | Authenticated        |

`#/control` is rewritten instantly to one of the above (no backward compat).
`#/control` shows the bootstrap form when no token is present, otherwise it
lands on `#/control/devices`.

## Nav structure

- **Control** dropdown (`#nav-control` toggle): opens to reveal Devices + ACL.
  - ACL is hidden from the nav for non-admin (`data-requires-admin` attribute;
    `app.js` toggles `.hidden` based on `me.is_first_webui_device`).
- **Operations** top-level (`#nav-operations`): single click goes to
  `#/operations`.

Click-outside closes the dropdown. Keyboard support is limited to click
(open/close) — no arrow-key navigation.

## File layout

### New JS modules (under `portal/public/js/`)
- `router.js` — `parseHash()` now returns `{route, sub, params}` (was
  `{route, params}`). Adds `buildHash(route, sub, params)` helper for hash
  reconstruction. Replaces `pushState`/`replaceState` direct calls.
- `control_router.js` — sub-route dispatcher. Exports
  `initControlSubroute(sub)`, `teardownControlSubroute()`,
  `getCurrentControlSub()`. Routes to bootstrap / devices / acl based on
  bootstrap state + sub.
- `control_bootstrap.js` — token registration form. On success, redirects to
  `#/control/devices`.
- `control_devices.js` — devices table, admin checkbox toggle, delete button.
  Single-file section, no sub-tabs.
- `control_acl.js` — ACL form + ACL table. Shows a `.control-guard` div with
  "Devices に戻る" button for non-admin users instead of 404/403.
- `control_operations.js` — combines Operations (Ops tab, default) and
  Commands (Cmds tab) into one page. SSE-driven updates, filter bar,
  pagination, URL hash sync.
- `control_api.js` — added `fetchCommands({status, from, to, op, limit, offset})`
  returning `{commands, total, limit, offset}`.

### Deleted
- `control_dashboard.js` — replaced by the modules above.

### New CSS
~300 lines in `portal/public/style.css` (marked at end as "Phase 12"):
- `.nav-dropdown*` for the Control dropdown
- `.control-section*` for screen layout
- `.control-table`, `.control-form`, `.control-tabs/tab` for table/form/tabs
- `.control-filter-bar`, `.control-pagination` for commands list
- `.control-guard` for non-admin ACL access
- `.bootstrap-*` for the bootstrap form
- `.provider-card` for operation cards

## Backend changes

`portal/servers/control_plane/api.py` — `GET /api/control/commands` now
accepts:
- `status` — one of `pending`, `running`, `succeeded`, `failed`, `cancelled`;
  invalid value returns 400
- `from_`, `to` — ISO 8601 datetime bounds (inclusive)
- `op` — operation id substring match
- `limit` — page size, default 25, max 100
- `offset` — page offset, default 0

Response body: `{commands, total, limit, offset}`. The `total` field enables
client-side pagination.

## URL hash state

`#/operations` accepts query string params in the hash:
```
#/operations?status=succeeded&from=2026-06-01T00:00:00&to=2026-06-07T23:59:59&op=echo&limit=10&offset=0
```

The filter inputs and pagination buttons all update the hash via
`window.location.replace(newHash)` (no history pollution). On load,
`parseHash().params` populates the filter state and the active page.

## Tests

### New E2E: `portal/tests/control_split.spec.js` (10 cases)
- bootstrap flow: `#/control` without token shows bootstrap form
- after bootstrap, `#/control` lands on Devices
- ACL hidden from nav for non-admin, accessible directly with guard message
- ACL shown for admin
- operations page: ops tab is default, cmds tab is switchable
- operations page: filter and pagination controls are present
- operations page: filter changes update URL hash
- nav dropdown: control dropdown opens, lists Devices and ACL
- backend: GET /api/control/commands supports filter and pagination
- backend: invalid status filter returns 400

### Updated E2E
- `device_agent_integration.spec.js` — uses new routes
  (`#/control`, `#/control/acl`, `#/operations`); added `promoteToAdmin`
  helper that uses `manage.py ... control set-admin --device-id` to make
  the test self-sufficient regardless of test ordering.
- `schema_renderer.spec.js` — uses `.provider-card button` selector for
  operation buttons; tests now navigate via `#/operations`.

## Test results
- 33/33 E2E tests pass
- 68/68 backend tests pass

## Implementation notes
- `parseHash` in `router.js` now returns a sub-route key. `app.js` passes
  `route.sub` to the section init function. The Operations page takes over
  its own sub-routing (tabs are local to that page).
- `control_operations.js` keeps the SSE connection alive even when the Cmds
  tab is inactive — the Ops tab depends on `device_status` events for
  online/offline indicator updates. On `command_status` events, if the
  user is at `offset === 0` (first page) and the event is unknown, a minimal
  stub is prepended to keep the list live.
- Auto-refresh: `setInterval(refreshAll, 30000)` for the commands list
  (defensive in case SSE drops).
- The dropdown click-outside handler is registered globally on `document`
  and checks `!dropdown.contains(e.target)`. The dropdown is closed on
  hash change as well.
- `control_acl.js` does not call any admin-only API on non-admin mount —
  it just renders `.control-guard` and the form area is omitted. This
  keeps the page from appearing "broken" with a 403 popup.

## Out of scope for this phase
- Per-user dashboard layouts / saved views
- Bulk operations on commands (cancel-all, retry-all)
- Per-device history drilldown
- Drag-and-drop reordering
