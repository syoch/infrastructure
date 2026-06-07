import { renderSchemaEditor } from './schema_editor.js';

const DEFAULT_PLACEHOLDER = '';

type SchemaValue = string | number | boolean | null | object | unknown[] | undefined;

export interface JSONSchema {
  type?: 'string' | 'number' | 'integer' | 'boolean' | 'null' | 'array' | 'object' | string[];
  title?: string;
  description?: string;
  enum?: unknown[];
  oneOf?: JSONSchema[];
  anyOf?: JSONSchema[];
  $ref?: string;
  default?: SchemaValue;
  const?: SchemaValue;
  properties?: Record<string, JSONSchema>;
  required?: string[];
  items?: JSONSchema;
  pattern?: string;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  ui_hint?: { widget?: 'textarea' | 'password' | 'json' | 'schema_editor' };
  _required?: boolean;
}

export interface RenderContext {
  rootSchema: JSONSchema;
  depth: number;
}

export interface SchemaNode {
  el: HTMLElement;
  getValue: () => SchemaValue;
  setValue: (v: SchemaValue) => void;
}

export interface RenderOptions {
  initial?: SchemaValue;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function makeEl(
  tag: string,
  attrs: Record<string, unknown> = {},
  ...children: (HTMLElement | string | null | undefined | false)[]
): HTMLElement {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'style' && isPlainObject(v)) {
      Object.assign(el.style, v as Partial<CSSStyleDeclaration>);
    } else if (k === 'class') {
      el.className = String(v);
    } else if (k === 'data' && isPlainObject(v)) {
      for (const [dk, dv] of Object.entries(v)) el.dataset[dk] = String(dv);
    } else if (k === 'value') {
      if (el instanceof HTMLTextAreaElement) {
        el.value = String(v);
      } else if (el instanceof HTMLInputElement) {
        el.value = String(v);
      } else if (el instanceof HTMLSelectElement) {
        el.value = String(v);
      } else if (el instanceof HTMLOptionElement) {
        el.value = String(v);
      } else if (el instanceof HTMLButtonElement) {
        el.value = String(v);
      } else {
        el.setAttribute(k, String(v));
      }
    } else if (k === 'checked') {
      if (el instanceof HTMLInputElement) {
        el.checked = Boolean(v);
      }
    } else if (k === 'rows') {
      if (el instanceof HTMLTextAreaElement) {
        el.rows = Number(v);
      }
    } else if (k === 'placeholder') {
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
        el.placeholder = String(v);
      }
    } else if (k === 'min' || k === 'max' || k === 'step' || k === 'pattern' || k === 'minLength' || k === 'maxLength') {
      if (el instanceof HTMLInputElement) {
        (el as HTMLInputElement)[k as 'min' | 'max' | 'step' | 'pattern' | 'minLength' | 'maxLength'] = v as string & number;
      }
    } else if (k.startsWith('on') && typeof v === 'function') {
      el.addEventListener(k.slice(2).toLowerCase(), v as EventListener);
    } else if (v === true) {
      el.setAttribute(k, '');
    } else if (v !== false && v != null) {
      el.setAttribute(k, String(v));
    }
  }
  for (const c of children) {
    if (c == null || c === false) continue;
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return el;
}

function resolveRef(ref: string, rootSchema: JSONSchema): JSONSchema | null {
  if (!ref.startsWith('#/')) return null;
  const path = ref.slice(2).split('/');
  let node: unknown = rootSchema;
  for (const segment of path) {
    if (node == null) return null;
    node = (node as Record<string, unknown>)[
      decodeURIComponent(segment.replace(/~1/g, '/').replace(/~0/g, '~'))
    ];
  }
  return (node as JSONSchema) || null;
}

function effectiveType(schema: JSONSchema | null | undefined): string {
  if (!schema) return 'string';
  if (Array.isArray(schema.type)) {
    return schema.type.includes('null') ? 'string' : schema.type[0];
  }
  return schema.type || 'string';
}

function makeInput(type: string, attrs: Record<string, unknown> = {}): HTMLInputElement | HTMLTextAreaElement {
  return makeEl(type === 'textarea' ? 'textarea' : 'input', {
    type: type === 'textarea' ? null : type || 'text',
    ...attrs,
  }) as HTMLInputElement | HTMLTextAreaElement;
}

function wrap(node: SchemaNode, opts: { className?: string; title?: string; required?: boolean } = {}): SchemaNode {
  const wrap = makeEl('div', {
    class: opts.className || 'schema-field',
    style: { display: 'flex', flexDirection: 'column', gap: '2px' },
  });
  if (opts.title) {
    const title = makeEl('span', { class: 'schema-field-title', style: { fontSize: '0.85em' } });
    title.textContent = opts.title + (opts.required ? ' *' : '');
    wrap.appendChild(title);
  }
  wrap.appendChild(node.el);
  return { el: wrap, getValue: node.getValue, setValue: node.setValue };
}

function renderString(schema: JSONSchema, _ctx: RenderContext): SchemaNode {
  const widget = schema.ui_hint?.widget;
  let inner: SchemaNode;
  if (schema.enum) {
    const sel = makeEl('select', {}) as HTMLSelectElement;
    for (const opt of schema.enum) {
      sel.appendChild(makeEl('option', { value: String(opt) }, String(opt)));
    }
    inner = {
      el: sel,
      getValue: () => sel.value,
      setValue: (v) => { sel.value = v == null ? '' : String(v); },
    };
  } else if (widget === 'textarea') {
    const ta = makeEl('textarea', {
      rows: '3',
      style: { fontFamily: 'monospace', width: '100%', boxSizing: 'border-box' },
    }) as HTMLTextAreaElement;
    if (schema.description) ta.placeholder = schema.description;
    inner = {
      el: ta,
      getValue: () => ta.value,
      setValue: (v) => { ta.value = v == null ? '' : String(v); },
    };
  } else if (widget === 'password') {
    const inp = makeInput('password') as HTMLInputElement;
    if (schema.description) inp.placeholder = schema.description;
    inner = {
      el: inp,
      getValue: () => inp.value,
      setValue: (v) => { inp.value = v == null ? '' : String(v); },
    };
  } else if (widget === 'json') {
    const ta = makeEl('textarea', {
      rows: 6,
      style: { fontFamily: 'monospace', width: '100%', boxSizing: 'border-box' },
    }) as HTMLTextAreaElement;
    if (schema.description) ta.placeholder = schema.description;
    inner = {
      el: ta,
      getValue: () => {
        const t = ta.value.trim();
        if (t === '') return undefined;
        try {
          return JSON.parse(t);
        } catch (e) {
          throw new Error(`invalid JSON: ${e instanceof Error ? e.message : String(e)}`);
        }
      },
      setValue: (v) => {
        if (v == null) { ta.value = ''; return; }
        ta.value = typeof v === 'string' ? v : JSON.stringify(v, null, 2);
      },
    };
  } else {
    const inp = makeInput('text') as HTMLInputElement;
    if (schema.description) inp.placeholder = schema.description;
    if (schema.pattern) inp.pattern = schema.pattern;
    if (schema.minLength != null) inp.minLength = schema.minLength;
    if (schema.maxLength != null) inp.maxLength = schema.maxLength;
    inner = {
      el: inp,
      getValue: () => inp.value,
      setValue: (v) => { inp.value = v == null ? '' : String(v); },
    };
  }
  return wrap(inner, { title: schema.title, required: schema._required });
}

function renderNumber(schema: JSONSchema, _ctx: RenderContext): SchemaNode {
  const inp = makeInput('number') as HTMLInputElement;
  inp.step = schema.type === 'integer' ? '1' : 'any';
  if (schema.minimum != null) inp.min = String(schema.minimum);
  if (schema.maximum != null) inp.max = String(schema.maximum);
  if (schema.description) inp.placeholder = schema.description;
  const inner: SchemaNode = {
    el: inp,
    getValue: () => {
      if (inp.value === '') return undefined;
      const n = Number(inp.value);
      if (Number.isNaN(n)) throw new Error(`not a number: ${inp.value}`);
      return schema.type === 'integer' ? Math.trunc(n) : n;
    },
    setValue: (v) => { inp.value = v == null ? '' : String(v); },
  };
  return wrap(inner, { title: schema.title, required: schema._required });
}

function renderBoolean(schema: JSONSchema, _ctx: RenderContext): SchemaNode {
  const label = makeEl('label', {
    style: { display: 'inline-flex', alignItems: 'center', gap: '6px' },
  });
  const cb = makeEl('input', { type: 'checkbox' }) as HTMLInputElement;
  label.appendChild(cb);
  if (schema.title) label.appendChild(document.createTextNode(schema.title));
  return wrap(
    {
      el: label,
      getValue: () => cb.checked,
      setValue: (v) => { cb.checked = Boolean(v); },
    },
    { title: schema.title, required: schema._required }
  );
}

function renderNull(_schema: JSONSchema, _ctx: RenderContext): SchemaNode {
  return {
    el: makeEl('span', { style: { color: '#888' } }, '(null)'),
    getValue: () => null,
    setValue: () => { /* noop */ },
  };
}

function getItemSchema(schema: JSONSchema, _ctx: RenderContext): JSONSchema {
  if (schema.items) return schema.items;
  return { type: 'string' };
}

function renderArray(schema: JSONSchema, ctx: RenderContext): SchemaNode {
  const wrapEl = makeEl('div', {
    class: 'schema-array',
    style: { display: 'flex', flexDirection: 'column', gap: '6px' },
  });
  const list = makeEl('div', {
    class: 'schema-array-items',
    style: { display: 'flex', flexDirection: 'column', gap: '4px' },
  });

  const items: { _wrap: HTMLElement; getValue: () => SchemaValue; setValue: (v: SchemaValue) => void }[] = [];

  function addItem(initial?: SchemaValue): void {
    const itemWrap = makeEl('div', {
      class: 'schema-array-item',
      style: { display: 'flex', alignItems: 'flex-start', gap: '6px', border: '1px solid #ddd', padding: '4px', borderRadius: '4px' },
    });
    const removeBtn = makeEl(
      'button',
      {
        type: 'button',
        class: 'btn btn-secondary',
        style: { flex: '0 0 auto' },
        onClick: () => {
          const idx = items.findIndex((it) => it._wrap === itemWrap);
          if (idx >= 0) {
            items.splice(idx, 1);
            itemWrap.remove();
          }
        },
      },
      '×'
    );
    const itemSchema = getItemSchema(schema, ctx);
    const inner = renderNode(itemSchema, ctx);
    itemWrap.appendChild(inner.el);
    itemWrap.appendChild(removeBtn);
    if (initial !== undefined) {
      try {
        inner.setValue(initial);
      } catch {
        /* ignore */
      }
    }
    const itemRecord = { _wrap: itemWrap, getValue: () => inner.getValue(), setValue: inner.setValue };
    items.push(itemRecord);
    list.appendChild(itemWrap);
  }

  const addBtn = makeEl(
    'button',
    {
      type: 'button',
      class: 'btn btn-secondary',
      style: { alignSelf: 'flex-start' },
      onClick: () => addItem(),
    },
    '+ Add'
  );
  wrapEl.appendChild(addBtn);
  wrapEl.appendChild(list);

  return {
    el: wrapEl,
    getValue: () => items.map((it) => it.getValue()),
    setValue: (arr) => {
      for (const it of items) it._wrap.remove();
      items.length = 0;
      if (Array.isArray(arr)) for (const v of arr) addItem(v as SchemaValue);
    },
  };
}

function renderObject(schema: JSONSchema, ctx: RenderContext): SchemaNode {
  const wrapEl = makeEl('div', {
    class: 'schema-object',
    style: { display: 'flex', flexDirection: 'column', gap: '8px', borderLeft: '2px solid #eee', paddingLeft: '8px' },
  });
  const props = schema.properties || {};
  const required = new Set(schema.required || []);
  const fieldNodes: Record<string, SchemaNode> = {};

  for (const [name, propSchema] of Object.entries(props)) {
    const isRequired = required.has(name);
    const subSchema: JSONSchema = { ...propSchema, title: propSchema.title || name, _required: isRequired };
    const node = renderNode(subSchema, ctx);
    wrapEl.appendChild(node.el);
    fieldNodes[name] = node;
  }

  return {
    el: wrapEl,
    getValue: () => {
      const out: Record<string, SchemaValue> = {};
      for (const [name, node] of Object.entries(fieldNodes)) {
        let v: SchemaValue;
        try {
          v = node.getValue();
        } catch (e) {
          throw new Error(`field '${name}': ${e instanceof Error ? e.message : String(e)}`);
        }
        if (v !== undefined && v !== '') {
          out[name] = v;
        } else if (required.has(name)) {
          const wrapDiv = node.el;
          const cb = wrapDiv && wrapDiv.querySelector && wrapDiv.querySelector('input[type=checkbox]');
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
        if (fieldNodes[name]) fieldNodes[name].setValue(val as SchemaValue);
      }
    },
  };
}

function renderOneOf(schema: JSONSchema, ctx: RenderContext): SchemaNode {
  const variants = schema.oneOf || schema.anyOf || [];
  if (variants.length === 0) {
    return { el: document.createTextNode('') as unknown as HTMLElement, getValue: () => undefined, setValue: () => { /* noop */ } };
  }
  const wrapEl = makeEl('div', {
    class: 'schema-oneof',
    style: { display: 'flex', flexDirection: 'column', gap: '4px', border: '1px dashed #aaa', padding: '6px', borderRadius: '4px' },
  });

  const variantNames = variants.map((v, i) => v.title || v.$ref || `variant ${i}`);
  const sel = makeEl('select', {}) as HTMLSelectElement;
  for (let i = 0; i < variants.length; i++) {
    sel.appendChild(makeEl('option', { value: String(i) }, variantNames[i]));
  }
  const label = makeEl('label', { style: { display: 'flex', flexDirection: 'column', gap: '2px' } });
  label.appendChild(makeEl('span', { style: { fontSize: '0.85em' } }, 'type'));
  label.appendChild(sel);
  wrapEl.appendChild(label);

  const content = makeEl('div', { class: 'schema-oneof-content' });
  wrapEl.appendChild(content);

  let currentNode: SchemaNode | null = null;
  function setVariant(i: number): void {
    while (content.firstChild) content.removeChild(content.firstChild);
    const v = variants[i];
    let resolved = v;
    if (v.$ref) {
      const ref = resolveRef(v.$ref, ctx.rootSchema);
      if (ref) resolved = ref;
    }
    currentNode = renderNode(resolved, ctx);
    content.appendChild(currentNode.el);
  }
  sel.addEventListener('change', () => setVariant(Number(sel.value)));
  setVariant(0);

  return {
    el: wrapEl,
    getValue: () => (currentNode ? currentNode.getValue() : undefined),
    setValue: (v) => { if (currentNode) currentNode.setValue(v); },
  };
}

function renderConst(schema: JSONSchema, _ctx: RenderContext): SchemaNode {
  const wrapEl = makeEl('div', { style: { padding: '4px', color: '#666' } });
  wrapEl.textContent = `(constant: ${JSON.stringify(schema.const)})`;
  return {
    el: wrapEl,
    getValue: () => schema.const ?? null,
    setValue: () => { /* noop */ },
  };
}

function renderNode(schema: JSONSchema, ctx: RenderContext): SchemaNode {
  if (!schema || typeof schema !== 'object') {
    return { el: document.createTextNode('') as unknown as HTMLElement, getValue: () => undefined, setValue: () => { /* noop */ } };
  }
  if (schema.$ref) {
    const resolved = resolveRef(schema.$ref, ctx.rootSchema);
    if (resolved) return renderNode(resolved, ctx);
  }
  if (schema.const !== undefined) return renderConst(schema, ctx);
  if (schema.oneOf || schema.anyOf) return renderOneOf(schema, ctx);
  if (schema.enum) return renderString({ ...schema, type: 'string' }, ctx);

  if (schema.ui_hint?.widget === 'schema_editor') {
    const container = makeEl('div', {});
    let editor = renderSchemaEditor(
      (schema.default as JSONSchema) || { type: 'object', properties: {} },
      container
    );
    return wrap(
      {
        el: container,
        getValue: () => editor.getSchema() as SchemaValue,
        setValue: (v) => {
          container.innerHTML = '';
          editor = renderSchemaEditor((v as JSONSchema) || { type: 'object', properties: {} }, container);
        },
      },
      { title: schema.title, required: schema._required }
    );
  }

  const t = effectiveType(schema);
  switch (t) {
    case 'string':
      return renderString({ ...schema, type: 'string' }, ctx);
    case 'number':
    case 'integer':
      return renderNumber(schema, ctx);
    case 'boolean':
      return renderBoolean(schema, ctx);
    case 'null':
      return renderNull(schema, ctx);
    case 'array':
      return renderArray(schema, ctx);
    case 'object':
      return renderObject(schema, ctx);
    default: {
      const inp = makeInput('text') as HTMLInputElement;
      if (schema.description) inp.placeholder = schema.description;
      return wrap(
        {
          el: inp,
          getValue: () => inp.value,
          setValue: (v) => { inp.value = v == null ? '' : String(v); },
        },
        { title: schema.title, required: schema._required }
      );
    }
  }
}

export function renderSchema(
  schema: JSONSchema,
  container?: HTMLElement,
  _opts: RenderOptions = {}
): SchemaNode {
  const rootSchema = schema || { type: 'object', properties: {} };
  const ctx: RenderContext = { rootSchema, depth: 0 };
  const node = renderNode(rootSchema, ctx);
  if (container) container.appendChild(node.el);
  return {
    el: node.el,
    getValue: () => {
      try {
        const v = node.getValue();
        if (rootSchema.type === 'object' && !isPlainObject(v)) return {};
        return v;
      } catch (e) {
        throw e;
      }
    },
    setValue: (v) => node.setValue(v),
  };
}