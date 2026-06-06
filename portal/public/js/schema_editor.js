import { renderSchema } from "./schema_renderer.js";

/**
 * schema_editor.js — visual editor for a JSON Schema.
 *
 * API:
 *   const { el, getSchema } = renderSchemaEditor(schema, container);
 *   - el:        the root DOM element
 *   - getSchema(): current schema as a JSON Schema object
 *
 * Supports editing of: object, array, string, number, integer, boolean, null,
 * enum, oneOf/anyOf. Each property has add/remove/type/title/description/required.
 */

const TYPE_OPTIONS = [
  "string", "number", "integer", "boolean", "object", "array", "null",
];

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function deepClone(v) {
  if (v == null) return v;
  if (typeof v !== "object") return v;
  if (Array.isArray(v)) return v.map(deepClone);
  const out = {};
  for (const [k, val] of Object.entries(v)) out[k] = deepClone(val);
  return out;
}

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "style" && isPlainObject(v)) Object.assign(e.style, v);
    else if (k === "class") e.className = v;
    else if (k === "value") e.value = v;
    else if (k === "checked") e.checked = v;
    else if (k === "rows") e.rows = v;
    else if (k === "placeholder") e.placeholder = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v === true) e.setAttribute(k, "");
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null || c === false) continue;
    e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return e;
}

function makeTextInput(value, placeholder = "", onChange = null) {
  const inp = el("input", { type: "text", value: value ?? "", placeholder });
  if (onChange) inp.addEventListener("input", () => onChange(inp.value));
  return inp;
}

function makeTextarea(value, placeholder = "", onChange = null, rows = 3) {
  const ta = el("textarea", { rows, placeholder, style: { fontFamily: "monospace", width: "100%", boxSizing: "border-box" } });
  ta.value = value ?? "";
  if (onChange) ta.addEventListener("input", () => onChange(ta.value));
  return ta;
}

function makeSelect(options, value, onChange) {
  const sel = el("select", {});
  for (const opt of options) {
    const o = el("option", { value: opt }, opt);
    if (opt === value) o.selected = true;
    sel.appendChild(o);
  }
  if (onChange) sel.addEventListener("change", () => onChange(sel.value));
  return sel;
}

function makeCheckbox(value, onChange) {
  const cb = el("input", { type: "checkbox", checked: Boolean(value) });
  if (onChange) cb.addEventListener("change", () => onChange(cb.checked));
  return cb;
}

function renderEnumEditor(value, onChange) {
  const wrap = el("div", { class: "schema-editor-enum", style: { display: "flex", flexDirection: "column", gap: "4px" } });
  const list = el("div", { style: { display: "flex", flexDirection: "column", gap: "2px" } });
  wrap.appendChild(list);
  const arr = Array.isArray(value) ? [...value] : [];

  function refresh() {
    while (list.firstChild) list.removeChild(list.firstChild);
    arr.forEach((v, idx) => {
      const inp = makeTextInput(v, "value", (newVal) => { arr[idx] = newVal; onChange([...arr]); });
      const rm = el("button", {
        type: "button", class: "btn btn-secondary",
        onClick: () => { arr.splice(idx, 1); refresh(); onChange([...arr]); },
      }, "×");
      list.appendChild(el("div", { style: { display: "flex", gap: "4px", alignItems: "center" } }, inp, rm));
    });
  }
  refresh();
  wrap.appendChild(el("button", {
    type: "button", class: "btn btn-secondary",
    style: { alignSelf: "flex-start" },
    onClick: () => { arr.push(""); refresh(); onChange([...arr]); },
  }, "+ Add value"));
  return wrap;
}

function makeObjectPropertiesEditor(initialProperties, initialRequired, onChange) {
  const wrap = el("div", { class: "schema-editor-properties", style: { display: "flex", flexDirection: "column", gap: "6px" } });
  const list = el("div", { style: { display: "flex", flexDirection: "column", gap: "4px" } });
  wrap.appendChild(list);

  const state = {
    props: { ...(initialProperties || {}) },
    required: new Set(initialRequired || []),
  };

  function emit() {
    onChange({ ...state.props }, [...state.required]);
  }

  function makeRow(name, sch) {
    const propState = { ...deepClone(sch) };
    const row = el("div", {
      class: "schema-editor-property-row",
      style: { display: "flex", gap: "4px", alignItems: "flex-start", border: "1px solid #ddd", padding: "6px", borderRadius: "4px", background: "#fafafa" },
    });
    const nameCol = el("div", { style: { display: "flex", flexDirection: "column", gap: "2px", minWidth: "120px" } });
    const nameInp = makeTextInput(name, "name");
    nameInp.style.width = "120px";
    nameCol.appendChild(nameInp);
    const reqLbl = el("label", { style: { display: "flex", alignItems: "center", gap: "4px", fontSize: "0.75em" } });
    reqLbl.appendChild(makeCheckbox(state.required.has(name), (v) => {
      if (v) state.required.add(name); else state.required.delete(name);
      emit();
    }));
    reqLbl.appendChild(document.createTextNode("required"));
    nameCol.appendChild(reqLbl);
    row.appendChild(nameCol);

    const propCol = el("div", { style: { flex: "1", minWidth: "0" } });
    function propEmit() {
      state.props[name] = deepClone(propState);
      emit();
    }
    const propBody = makeNodeEditor(propState, propEmit);
    propCol.appendChild(propBody);
    row.appendChild(propCol);

    row.appendChild(el("button", {
      type: "button", class: "btn btn-secondary",
      style: { flex: "0 0 auto" },
      onClick: () => {
        delete state.props[name];
        state.required.delete(name);
        refresh();
        emit();
      },
    }, "×"));

    nameInp.addEventListener("change", () => {
      const newName = nameInp.value.trim();
      if (newName === "" || newName === name) {
        nameInp.value = name;
        return;
      }
      if (newName in state.props) {
        nameInp.value = name;
        return;
      }
      const wasRequired = state.required.has(name);
      delete state.props[name];
      state.required.delete(name);
      state.props[newName] = deepClone(propState);
      if (wasRequired) state.required.add(newName);
      refresh();
      emit();
    });

    return row;
  }

  function refresh() {
    while (list.firstChild) list.removeChild(list.firstChild);
    for (const [name, sch] of Object.entries(state.props)) {
      list.appendChild(makeRow(name, sch));
    }
  }
  refresh();

  wrap.appendChild(el("button", {
    type: "button", class: "btn btn-secondary",
    style: { alignSelf: "flex-start" },
    onClick: () => {
      let i = 1;
      let n = `property${i}`;
      while (n in state.props) { i++; n = `property${i}`; }
      state.props[n] = { type: "string" };
      refresh();
      emit();
    },
  }, "+ Add property"));
  return wrap;
}

function makeNodeEditor(state, onChange) {
  const wrap = el("div", { class: "schema-editor-node", style: { display: "flex", flexDirection: "column", gap: "4px" } });
  const header = el("div", { style: { display: "flex", gap: "4px", alignItems: "center", flexWrap: "wrap" } });
  wrap.appendChild(header);

  let body = el("div", {});
  wrap.appendChild(body);

  const typeSel = makeSelect(TYPE_OPTIONS, state.type || "string", (v) => {
    state.type = v;
    if (v === "object" && !state.properties) state.properties = {};
    if (v === "array" && !state.items) state.items = { type: "string" };
    if (v === "string") { /* keep enum if any */ }
    rebuild();
    onChange();
  });
  header.appendChild(el("span", { style: { fontSize: "0.8em", color: "#666" } }, "type:"));
  header.appendChild(typeSel);

  header.appendChild(el("span", { style: { fontSize: "0.8em", color: "#666" } }, "title:"));
  header.appendChild(makeTextInput(state.title, "title", (v) => { state.title = v || undefined; onChange(); }));
  header.appendChild(el("span", { style: { fontSize: "0.8em", color: "#666" } }, "desc:"));
  header.appendChild(makeTextInput(state.description, "description", (v) => { state.description = v || undefined; onChange(); }));

  function rebuild() {
    while (body.firstChild) body.removeChild(body.firstChild);
    if (state.type === "object") {
      const ed = makeObjectPropertiesEditor(state.properties, state.required, (newProps, required) => {
        state.properties = newProps;
        state.required = required;
        onChange();
      });
      body.appendChild(ed);
    } else if (state.type === "array") {
      body.appendChild(el("div", { style: { fontSize: "0.8em", color: "#666" } }, "items:"));
      const itemState = state.items || { type: "string" };
      state.items = itemState;
      const ed = makeNodeEditor(itemState, onChange);
      body.appendChild(ed);
    } else if (state.type === "string") {
      const hasEnum = Array.isArray(state.enum);
      const lbl = el("label", { style: { display: "flex", alignItems: "center", gap: "4px", fontSize: "0.8em" } });
      lbl.appendChild(document.createTextNode("enum:"));
      lbl.appendChild(makeCheckbox(hasEnum, (v) => {
        if (v) { state.enum = [""]; }
        else { delete state.enum; }
        rebuild();
        onChange();
      }));
      body.appendChild(lbl);
      if (hasEnum) {
        body.appendChild(renderEnumEditor(state.enum, (v) => { state.enum = v; onChange(); }));
      }
    } else if (state.type === "number" || state.type === "integer") {
      const r1 = el("div", { style: { display: "flex", gap: "4px", alignItems: "center" } });
      r1.appendChild(el("span", { style: { fontSize: "0.8em", color: "#666" } }, "min:"));
      r1.appendChild(makeTextInput(state.minimum, "min", (v) => {
        if (v === "" || v == null) delete state.minimum;
        else state.minimum = Number(v);
        onChange();
      }));
      r1.appendChild(el("span", { style: { fontSize: "0.8em", color: "#666" } }, "max:"));
      r1.appendChild(makeTextInput(state.maximum, "max", (v) => {
        if (v === "" || v == null) delete state.maximum;
        else state.maximum = Number(v);
        onChange();
      }));
      body.appendChild(r1);
    }
    const dRow = el("div", { style: { display: "flex", gap: "4px", alignItems: "center" } });
    dRow.appendChild(el("span", { style: { fontSize: "0.8em", color: "#666" } }, "default:"));
    const dInp = makeTextarea(state.default !== undefined ? JSON.stringify(state.default) : "", "default (JSON)", (v) => {
      if (v === "") delete state.default;
      else {
        try { state.default = JSON.parse(v); } catch (_) { /* ignore parse error during typing */ }
      }
      onChange();
    });
    dInp.style.flex = "1";
    dRow.appendChild(dInp);
    body.appendChild(dRow);
  }
  rebuild();
  return wrap;
}

export function renderSchemaEditor(schema, container) {
  const state = { type: "object", ...deepClone(schema || {}) };
  if (!state.properties && state.type === "object") state.properties = {};
  const wrap = el("div", {
    class: "schema-editor-root",
    style: { display: "flex", flexDirection: "column", gap: "8px", border: "1px solid #aaa", padding: "8px", borderRadius: "4px" },
  });
  const head = el("div", { style: { display: "flex", gap: "4px", alignItems: "center" } });
  head.appendChild(el("strong", {}, "Root type:"));
  head.appendChild(makeSelect(TYPE_OPTIONS, state.type, (v) => {
    state.type = v;
    if (v === "object" && !state.properties) state.properties = {};
    if (v === "array" && !state.items) state.items = { type: "string" };
    rebuild();
  }));
  wrap.appendChild(head);

  const bodyWrap = el("div", {});
  wrap.appendChild(bodyWrap);

  function rebuild() {
    while (bodyWrap.firstChild) bodyWrap.removeChild(bodyWrap.firstChild);
    if (state.type === "object") {
      bodyWrap.appendChild(makeObjectPropertiesEditor(state.properties, state.required, (newProps, required) => {
        state.properties = newProps;
        state.required = required;
      }));
    } else if (state.type === "array") {
      bodyWrap.appendChild(el("div", { style: { fontSize: "0.8em", color: "#666" } }, "items:"));
      const itemState = state.items || { type: "string" };
      state.items = itemState;
      bodyWrap.appendChild(makeNodeEditor(itemState, () => {}));
    } else {
      bodyWrap.appendChild(makeNodeEditor(state, () => {}));
    }
  }
  rebuild();
  if (container) container.appendChild(wrap);
  return {
    el: wrap,
    getSchema: () => deepClone(state),
  };
}
