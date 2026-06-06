# Phase 10 — Visual Schema Editor

**Status**: DONE

## Goal
Provide a full-featured, general-purpose JSON Schema → HTML form renderer, plus
a visual schema editor for authoring JSON Schemas in the portal WebUI. The
control plane's operation params input, ACL extra field, and any future
"schema-driven form" use case should all be backed by the same renderer.

## Files added
- `portal/public/js/schema_renderer.js` — JSON Schema → HTML form renderer
  (export: `renderSchema(schema, container, opts) → {el, getValue, setValue}`)
- `portal/public/js/schema_editor.js` — visual editor for a JSON Schema
  (export: `renderSchemaEditor(schema, container) → {el, getSchema}`)
- `portal/public/test_schema_renderer.html` — browser-based test harness with
  11 test cases (string, integer, boolean, enum, object, json widget, array
  of strings, nested object in array, oneOf selection, schema editor add,
  schema editor rename)
- `portal/tests/schema_renderer.spec.js` — Playwright E2E tests (2 cases:
  harness pass + control plane form renders)

## Files changed
- `portal/public/js/control_op_renderer.js` — refactored to use the new
  `renderSchema` from `schema_renderer.js` (no duplication)
- `AGENTS.md` — added Phase 10 reference
- `flake.nix` — `make test-e2e` runs `schema_renderer.spec.js`

## Renderer (`schema_renderer.js`) features

### Types supported
- `string` — text input, password, textarea, json, select (for enum)
- `number` / `integer` — number input with `min`/`max`/`step`
- `boolean` — checkbox
- `null` — read-only "(null)" label
- `array` — list with add/remove buttons
- `object` — labelled property list

### Composition
- `enum` — auto-renders as `<select>`
- `oneOf` / `anyOf` — variant selector + recursive form for selected variant
- `$ref` — resolved against `rootSchema` (e.g. `"#/definitions/Foo"`)

### `ui_hint` widgets (string only)
- `widget: "json"` — `<textarea rows=6>`; `getValue()` parses JSON, throws
  `invalid JSON: ...` on bad input
- `widget: "textarea"` — `<textarea rows=3>`
- `widget: "password"` — `<input type=password>`

### Constraints honored
- string: `pattern`, `minLength`, `maxLength` → input attrs
- number: `minimum`, `maximum`, `type: integer` → step="1" + Math.trunc
- object: `required` → asterisk on label, validation error in `getValue()`
  (with fallback to `default` if defined)

### API
```js
import { renderSchema } from "./schema_renderer.js";

const { el, getValue, setValue } = renderSchema(
  { type: "string", title: "Name", minLength: 1 },
  document.getElementById("form"),
);
el;            // root DOM element (a wrapper div, with optional title)
getValue();    // current form value (string/number/object/array/...)
setValue(v);   // replace form state
```

`el` is always a wrapper `<div class="schema-field">` (or `schema-object` /
`schema-array` / `schema-oneof`). This makes `el.querySelector("input")` work
for both scalar and compound types — important for E2E tests.

## Editor (`schema_editor.js`) features

### Editing surfaces
- Root type selector (string/number/integer/boolean/object/array/null)
- Object: add / remove / rename properties; per-property "required" toggle
- Property: per-property type selector, title, description, default (JSON)
- String: enum on/off; enum values list (add/remove)
- Number/integer: min/max
- Array: items editor (recursive)

### API
```js
import { renderSchemaEditor } from "./schema_editor.js";

const { el, getSchema } = renderSchemaEditor(
  { type: "object", properties: { foo: { type: "string" } } },
  document.getElementById("editor"),
);
getSchema();   // current schema as a JSON Schema object
```

### Out of scope for this phase
- `oneOf` / `anyOf` in the editor (renderer still supports them)
- `definitions` / `$ref` editor

## Test results
- All 11 harness cases pass
- 2 Playwright E2E cases pass (harness pass + control plane form renders)
- 20/20 E2E tests pass (`make test-e2e`)
- 64/64 backend tests pass (`make test-backend`)

## Implementation notes
- `makeEl(tag, attrs, ...children)` is the shared element factory. It
  correctly handles `class`, `style`, `data-*`, `on*` listeners, `value`,
  `checked`, `rows`, `placeholder`, `min`/`max`/`step`/`pattern`/
  `minLength`/`maxLength`, and falls through to `setAttribute` for anything
  else. The fallback `setAttribute` is essential — without it, attributes
  like `type="button"` and `value="0"` silently fail (an early bug where
  `select.value = "1"` couldn't match a numeric option).
- `addEventListener` is registered with `k.slice(2).toLowerCase()` because
  `addEventListener` is case-sensitive (`onClick` would otherwise attach
  to "Click" and never fire).
- All `el` returned from a renderer call is a wrapper div containing the
  actual input — this makes `el.querySelector("input")` work uniformly
  for the test harness and for production use (e.g. ACL create form's
  `extra` field renders as a json widget textarea).
- `control_op_renderer.js` was rewritten to delegate to `renderSchema`
  (instead of duplicating logic), reducing the surface area for bugs.
