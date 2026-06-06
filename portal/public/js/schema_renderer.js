import { escapeHTML } from "./ui.js";
import { renderSchemaEditor } from "./schema_editor.js";

/**
 * schema_renderer.js — render an HTML form from a JSON Schema, suitable for
 * "params input" use cases (the WebUI asks the user to fill in operation params).
 *
 * API:
 *   const { el, getValue, setValue } = renderSchema(schema, container, { initial });
 *   - el:        the root DOM element (also appended to `container` if provided)
 *   - getValue(): current form state as a plain object (or scalar)
 *   - setValue(v): replace form state
 *
 * Supported types: string, number, integer, boolean, null, array, object,
 * plus enum (string-with-enum) and oneOf/anyOf (discriminated union).
 *
 * `ui_hint` properties are honored:
 *   - { widget: "textarea" }    -> multiline text input
 *   - { widget: "password" }    -> password input
 *   - { widget: "json" }        -> multiline JSON text input, parsed on getValue
 *
 * $ref is supported within a single root schema (uses a definitions map).
 */

const DEFAULT_PLACEHOLDER = "";

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function makeEl(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "style" && isPlainObject(v)) {
      Object.assign(el.style, v);
    } else if (k === "class") {
      el.className = v;
    } else if (k === "data") {
      for (const [dk, dv] of Object.entries(v)) el.dataset[dk] = dv;
    } else if (k === "value") {
      el.value = v;
    } else if (k === "checked") {
      el.checked = v;
    } else if (k === "rows") {
      el.rows = v;
    } else if (k === "placeholder") {
      el.placeholder = v;
    } else if (k === "min" || k === "max" || k === "step" || k === "pattern" || k === "minLength" || k === "maxLength") {
      el[k] = v;
    } else if (k.startsWith("on") && typeof v === "function") {
      el.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (v === true) {
      el.setAttribute(k, "");
    } else if (v !== false && v != null) {
      el.setAttribute(k, v);
    }
  }
  for (const c of children) {
    if (c == null || c === false) continue;
    el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return el;
}

function resolveRef(ref, rootSchema) {
  if (!ref.startsWith("#/")) return null;
  const path = ref.slice(2).split("/");
  let node = rootSchema;
  for (const segment of path) {
    if (node == null) return null;
    node = node[decodeURIComponent(segment.replace(/~1/g, "/").replace(/~0/g, "~"))];
  }
  return node;
}

function effectiveType(schema) {
  if (!schema) return "string";
  if (Array.isArray(schema.type)) {
    return schema.type.includes("null") ? "string" : schema.type[0];
  }
  return schema.type || "string";
}

function makeInput(type, attrs = {}) {
  const input = makeEl(type === "textarea" ? "textarea" : "input", {
    type: type === "textarea" ? null : (type || "text"),
    ...attrs,
  });
  return input;
}

function wrap(node, opts = {}) {
  const wrap = makeEl("div", { class: opts.className || "schema-field", style: { display: "flex", flexDirection: "column", gap: "2px" } });
  if (opts.title) {
    const title = makeEl("span", { class: "schema-field-title", style: { fontSize: "0.85em" } });
    title.textContent = opts.title + (opts.required ? " *" : "");
    wrap.appendChild(title);
  }
  wrap.appendChild(node.el);
  return { el: wrap, getValue: node.getValue, setValue: node.setValue };
}

function renderString(schema, ctx) {
  const widget = schema.ui_hint?.widget;
  let inner;
  if (schema.enum) {
    const sel = makeEl("select", {});
    for (const opt of schema.enum) {
      sel.appendChild(makeEl("option", { value: String(opt) }, String(opt)));
    }
    inner = { el: sel, getValue: () => sel.value, setValue: (v) => { sel.value = v == null ? "" : String(v); } };
  } else if (widget === "textarea") {
    const ta = makeEl("textarea", { rows: 3, style: { fontFamily: "monospace", width: "100%", boxSizing: "border-box" } });
    if (schema.description) ta.placeholder = schema.description;
    inner = { el: ta, getValue: () => ta.value, setValue: (v) => { ta.value = v == null ? "" : String(v); } };
  } else if (widget === "password") {
    const inp = makeInput("password");
    if (schema.description) inp.placeholder = schema.description;
    inner = { el: inp, getValue: () => inp.value, setValue: (v) => { inp.value = v == null ? "" : String(v); } };
  } else if (widget === "json") {
    const ta = makeEl("textarea", { rows: 6, style: { fontFamily: "monospace", width: "100%", boxSizing: "border-box" } });
    if (schema.description) ta.placeholder = schema.description;
    inner = {
      el: ta,
      getValue: () => {
        const t = ta.value.trim();
        if (t === "") return undefined;
        try {
          return JSON.parse(t);
        } catch (e) {
          throw new Error(`invalid JSON: ${e.message}`);
        }
      },
      setValue: (v) => {
        if (v == null) { ta.value = ""; return; }
        ta.value = typeof v === "string" ? v : JSON.stringify(v, null, 2);
      },
    };
  } else {
    const inp = makeInput("text");
    if (schema.description) inp.placeholder = schema.description;
    if (schema.pattern) inp.pattern = schema.pattern;
    if (schema.minLength != null) inp.minLength = schema.minLength;
    if (schema.maxLength != null) inp.maxLength = schema.maxLength;
    inner = { el: inp, getValue: () => inp.value, setValue: (v) => { inp.value = v == null ? "" : String(v); } };
  }
  return wrap(inner, { title: schema.title, required: schema._required });
}

function renderNumber(schema, ctx) {
  const inp = makeInput("number");
  inp.step = schema.type === "integer" ? "1" : "any";
  if (schema.minimum != null) inp.min = schema.minimum;
  if (schema.maximum != null) inp.max = schema.maximum;
  if (schema.description) inp.placeholder = schema.description;
  const inner = {
    el: inp,
    getValue: () => {
      if (inp.value === "") return undefined;
      const n = Number(inp.value);
      if (Number.isNaN(n)) throw new Error(`not a number: ${inp.value}`);
      return schema.type === "integer" ? Math.trunc(n) : n;
    },
    setValue: (v) => { inp.value = v == null ? "" : String(v); },
  };
  return wrap(inner, { title: schema.title, required: schema._required });
}

function renderBoolean(schema, ctx) {
  const label = makeEl("label", { style: { display: "inline-flex", alignItems: "center", gap: "6px" } });
  const cb = makeEl("input", { type: "checkbox" });
  label.appendChild(cb);
  if (schema.title) label.appendChild(document.createTextNode(schema.title));
  return wrap({
    el: label,
    getValue: () => cb.checked,
    setValue: (v) => { cb.checked = Boolean(v); },
  }, { title: schema.title, required: schema._required });
}

function renderNull(schema, ctx) {
  return {
    el: makeEl("span", { style: { color: "#888" } }, "(null)"),
    getValue: () => null,
    setValue: () => {},
  };
}

function _getItemSchema(schema, ctx) {
  if (schema.items) return schema.items;
  return { type: "string" };
}

function renderArray(schema, ctx) {
  const wrap = makeEl("div", { class: "schema-array", style: { display: "flex", flexDirection: "column", gap: "6px" } });
  const addBtn = makeEl("button", {
    type: "button",
    class: "btn btn-secondary",
    style: { alignSelf: "flex-start" },
    onClick: () => addItem(),
  }, "+ Add");
  wrap.appendChild(addBtn);
  const list = makeEl("div", { class: "schema-array-items", style: { display: "flex", flexDirection: "column", gap: "4px" } });
  wrap.appendChild(list);

  const items = [];

  function makeItem(initial) {
    const itemWrap = makeEl("div", {
      class: "schema-array-item",
      style: { display: "flex", alignItems: "flex-start", gap: "6px", border: "1px solid #ddd", padding: "4px", borderRadius: "4px" },
    });
    const removeBtn = makeEl("button", {
      type: "button",
      class: "btn btn-secondary",
      style: { flex: "0 0 auto" },
      onClick: () => {
        const idx = items.findIndex((it) => it._wrap === itemWrap);
        if (idx >= 0) {
          items.splice(idx, 1);
          itemWrap.remove();
        }
      },
    }, "×");
    const itemSchema = _getItemSchema(schema, ctx);
    const inner = renderNode(itemSchema, ctx);
    itemWrap.appendChild(inner.el);
    itemWrap.appendChild(removeBtn);
    if (initial !== undefined) {
      try { inner.setValue(initial); } catch (_) { /* ignore */ }
    }
    return { _wrap: itemWrap, el: inner.el, getValue: () => inner.getValue(), setValue: inner.setValue };
  }

  function addItem(initial) {
    const it = makeItem(initial);
    items.push(it);
    list.appendChild(it._wrap);
  }

  return {
    el: wrap,
    getValue: () => items.map((it) => it.getValue()),
    setValue: (arr) => {
      for (const it of items) it._wrap.remove();
      items.length = 0;
      if (Array.isArray(arr)) for (const v of arr) addItem(v);
    },
  };
}

function renderObject(schema, ctx) {
  const wrapEl = makeEl("div", { class: "schema-object", style: { display: "flex", flexDirection: "column", gap: "8px", borderLeft: "2px solid #eee", paddingLeft: "8px" } });
  const props = schema.properties || {};
  const required = new Set(schema.required || []);
  const fieldNodes = {};

  for (const [name, propSchema] of Object.entries(props)) {
    const isRequired = required.has(name);
    const subSchema = { ...propSchema, title: propSchema.title || name, _required: isRequired };
    const node = renderNode(subSchema, ctx);
    wrapEl.appendChild(node.el);
    fieldNodes[name] = node;
  }

  return {
    el: wrapEl,
    getValue: () => {
      const out = {};
      for (const [name, node] of Object.entries(fieldNodes)) {
        let v;
        try { v = node.getValue(); } catch (e) { throw new Error(`field '${name}': ${e.message}`); }
        if (v !== undefined && v !== "") {
          out[name] = v;
        } else if (required.has(name)) {
          const wrapDiv = node.el;
          const cb = wrapDiv && wrapDiv.querySelector && wrapDiv.querySelector("input[type=checkbox]");
          if (cb) out[name] = false;
        }
      }
      for (const req of required) {
        if (!(req in out)) {
          const f = props[req];
          if (f && f.default !== undefined) out[req] = f.default;
          else throw new Error(`missing required field: ${req}`);
        }
      }
      return out;
    },
    setValue: (v) => {
      if (!isPlainObject(v)) return;
      for (const [name, val] of Object.entries(v)) {
        if (fieldNodes[name]) fieldNodes[name].setValue(val);
      }
    },
  };
}

function renderOneOf(schema, ctx) {
  const variants = schema.oneOf || schema.anyOf || [];
  if (variants.length === 0) return { el: document.createTextNode(""), getValue: () => undefined, setValue: () => {} };
  const wrap = makeEl("div", { class: "schema-oneof", style: { display: "flex", flexDirection: "column", gap: "4px", border: "1px dashed #aaa", padding: "6px", borderRadius: "4px" } });

  const variantNames = variants.map((v, i) => v.title || v.$ref || `variant ${i}`);
  const sel = makeEl("select", {});
  for (let i = 0; i < variants.length; i++) {
    sel.appendChild(makeEl("option", { value: String(i) }, variantNames[i]));
  }
  const label = makeEl("label", { style: { display: "flex", flexDirection: "column", gap: "2px" } });
  label.appendChild(makeEl("span", { style: { fontSize: "0.85em" } }, "type"));
  label.appendChild(sel);
  wrap.appendChild(label);

  const content = makeEl("div", { class: "schema-oneof-content" });
  wrap.appendChild(content);

  let currentNode = null;
  function setVariant(i) {
    while (content.firstChild) content.removeChild(content.firstChild);
    const v = variants[i];
    let resolved = v;
    if (v.$ref) {
      resolved = resolveRef(v.$ref, ctx.rootSchema) || v;
    }
    currentNode = renderNode(resolved, ctx);
    content.appendChild(currentNode.el);
  }
  sel.addEventListener("change", () => setVariant(Number(sel.value)));
  setVariant(0);

  return {
    el: wrap,
    getValue: () => currentNode ? currentNode.getValue() : undefined,
    setValue: (v) => { if (currentNode) currentNode.setValue(v); },
  };
}

function renderConst(schema, ctx) {
  const wrap = makeEl("div", { style: { padding: "4px", color: "#666" } });
  wrap.textContent = `(constant: ${JSON.stringify(schema.const)})`;
  return {
    el: wrap,
    getValue: () => schema.const,
    setValue: () => {},
  };
}

function renderNode(schema, ctx) {
  if (!schema || typeof schema !== "object") {
    return { el: document.createTextNode(""), getValue: () => undefined, setValue: () => {} };
  }
  if (schema.$ref) {
    const resolved = resolveRef(schema.$ref, ctx.rootSchema);
    if (resolved) return renderNode(resolved, ctx);
  }
  if (schema.const !== undefined) return renderConst(schema, ctx);
  if (schema.oneOf || schema.anyOf) return renderOneOf(schema, ctx);
  if (schema.enum) return renderString({ ...schema, type: "string" }, ctx);

  if (schema.ui_hint?.widget === "schema_editor") {
    const container = makeEl("div", {});
    const editor = renderSchemaEditor(schema.default || { type: "object", properties: {} }, container);
    return wrap({
      el: container,
      getValue: () => editor.getSchema(),
      setValue: (v) => {
        container.innerHTML = "";
        const newEditor = renderSchemaEditor(v || { type: "object", properties: {} }, container);
        editor.getSchema = newEditor.getSchema;
      }
    }, { title: schema.title, required: schema._required });
  }

  const t = effectiveType(schema);
  switch (t) {
    case "string": return renderString({ ...schema, type: "string" }, ctx);
    case "number":
    case "integer": return renderNumber(schema, ctx);
    case "boolean": return renderBoolean(schema, ctx);
    case "null": return renderNull(schema, ctx);
    case "array": return renderArray(schema, ctx);
    case "object": return renderObject(schema, ctx);
    default: {
      const inp = makeInput("text");
      if (schema.description) inp.placeholder = schema.description;
      return wrap({
        el: inp,
        getValue: () => inp.value,
        setValue: (v) => { inp.value = v == null ? "" : String(v); },
      }, { title: schema.title, required: schema._required });
    }
  }
}

export function renderSchema(schema, container, opts = {}) {
  const rootSchema = schema || { type: "object", properties: {} };
  const ctx = { rootSchema, depth: 0 };
  const node = renderNode(rootSchema, ctx);
  if (container) container.appendChild(node.el);
  return {
    el: node.el,
    getValue: () => {
      try {
        const v = node.getValue();
        if (rootSchema.type === "object" && (!isPlainObject(v))) return {};
        return v;
      } catch (e) {
        throw e;
      }
    },
    setValue: (v) => node.setValue(v),
  };
}

export { escapeHTML };
