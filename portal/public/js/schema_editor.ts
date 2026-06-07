import { renderSchema, JSONSchema, SchemaNode } from './schema_renderer.js';

const TYPE_OPTIONS = [
  'string', 'number', 'integer', 'boolean', 'object', 'array', 'null',
] as const;

type SchemaType = typeof TYPE_OPTIONS[number];

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function deepClone<T>(v: T): T {
  if (v == null) return v;
  if (typeof v !== 'object') return v;
  if (Array.isArray(v)) return v.map(deepClone) as unknown as T;
  const out: Record<string, unknown> = {};
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) out[k] = deepClone(val);
  return out as T;
}

function el(
  tag: string,
  attrs: Record<string, unknown> = {},
  ...children: (HTMLElement | string | null | undefined | false)[]
): HTMLElement {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'style' && isPlainObject(v)) Object.assign(e.style, v as Partial<CSSStyleDeclaration>);
    else if (k === 'class') e.className = String(v);
    else if (k === 'value') {
      if (e instanceof HTMLInputElement || e instanceof HTMLTextAreaElement || e instanceof HTMLSelectElement) {
        e.value = String(v);
      }
    }
    else if (k === 'checked') {
      if (e instanceof HTMLInputElement) e.checked = Boolean(v);
    }
    else if (k === 'rows') {
      if (e instanceof HTMLTextAreaElement) e.rows = Number(v);
    }
    else if (k === 'placeholder') {
      if (e instanceof HTMLInputElement || e instanceof HTMLTextAreaElement) e.placeholder = String(v);
    }
    else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2).toLowerCase(), v as EventListener);
    else if (v === true) e.setAttribute(k, '');
    else if (v !== false && v != null) e.setAttribute(k, String(v));
  }
  for (const c of children) {
    if (c == null || c === false) continue;
    e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return e;
}

function makeTextInput(
  value: string | undefined | null,
  placeholder = '',
  onChange: ((v: string) => void) | null = null
): HTMLInputElement {
  const inp = el('input', { type: 'text', value: value ?? '', placeholder }) as HTMLInputElement;
  if (onChange) inp.addEventListener('input', () => onChange(inp.value));
  return inp;
}

function makeTextarea(
  value: string | undefined | null,
  placeholder = '',
  onChange: ((v: string) => void) | null = null,
  rows = 3
): HTMLTextAreaElement {
  const ta = el('textarea', {
    rows,
    placeholder,
    style: { fontFamily: 'monospace', width: '100%', boxSizing: 'border-box' },
  }) as HTMLTextAreaElement;
  ta.value = value ?? '';
  if (onChange) ta.addEventListener('input', () => onChange(ta.value));
  return ta;
}

function makeSelect(
  options: readonly string[],
  value: string,
  onChange: (v: string) => void
): HTMLSelectElement {
  const sel = el('select', {}) as HTMLSelectElement;
  for (const opt of options) {
    const o = el('option', { value: opt }, opt) as HTMLOptionElement;
    if (opt === value) o.selected = true;
    sel.appendChild(o);
  }
  sel.addEventListener('change', () => onChange(sel.value));
  return sel;
}

function makeCheckbox(value: boolean, onChange: (v: boolean) => void): HTMLInputElement {
  const cb = el('input', { type: 'checkbox', checked: Boolean(value) }) as HTMLInputElement;
  cb.addEventListener('change', () => onChange(cb.checked));
  return cb;
}

function renderEnumEditor(
  value: unknown[] | undefined,
  onChange: (v: unknown[]) => void
): HTMLElement {
  const wrap = el('div', {
    class: 'schema-editor-enum',
    style: { display: 'flex', flexDirection: 'column', gap: '4px' },
  });
  const list = el('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px' } });
  wrap.appendChild(list);
  const arr: unknown[] = Array.isArray(value) ? [...value] : [];

  function refresh(): void {
    while (list.firstChild) list.removeChild(list.firstChild);
    arr.forEach((v, idx) => {
      const inp = makeTextInput(String(v ?? ''), 'value', (newVal) => {
        arr[idx] = newVal;
        onChange([...arr]);
      });
      const rm = el(
        'button',
        {
          type: 'button',
          class: 'btn btn-secondary',
          onClick: () => {
            arr.splice(idx, 1);
            refresh();
            onChange([...arr]);
          },
        },
        '×'
      );
      list.appendChild(el('div', { style: { display: 'flex', gap: '4px', alignItems: 'center' } }, inp, rm));
    });
  }
  refresh();
  wrap.appendChild(
    el(
      'button',
      {
        type: 'button',
        class: 'btn btn-secondary',
        style: { alignSelf: 'flex-start' },
        onClick: () => {
          arr.push('');
          refresh();
          onChange([...arr]);
        },
      },
      '+ Add value'
    )
  );
  return wrap;
}

function makeObjectPropertiesEditor(
  initialProperties: Record<string, JSONSchema> | undefined,
  initialRequired: string[] | undefined,
  onChange: (props: Record<string, JSONSchema>, required: string[]) => void
): HTMLElement {
  const wrap = el('div', {
    class: 'schema-editor-properties',
    style: { display: 'flex', flexDirection: 'column', gap: '6px' },
  });
  const list = el('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } });
  wrap.appendChild(list);

  const state: {
    props: Record<string, JSONSchema>;
    required: Set<string>;
  } = {
    props: { ...(initialProperties || {}) },
    required: new Set(initialRequired || []),
  };

  function emit(): void {
    onChange({ ...state.props }, [...state.required]);
  }

  function makeRow(name: string, sch: JSONSchema): HTMLElement {
    const propState: JSONSchema = { ...deepClone(sch) };
    const row = el('div', {
      class: 'schema-editor-property-row',
      style: {
        display: 'flex',
        gap: '4px',
        alignItems: 'flex-start',
        border: '1px solid #ddd',
        padding: '6px',
        borderRadius: '4px',
        background: '#fafafa',
      },
    });
    const nameCol = el('div', {
      style: { display: 'flex', flexDirection: 'column', gap: '2px', minWidth: '120px' },
    });
    const nameInp = makeTextInput(name, 'name');
    nameInp.style.width = '120px';
    nameCol.appendChild(nameInp);
    const reqLbl = el('label', {
      style: { display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75em' },
    });
    reqLbl.appendChild(
      makeCheckbox(state.required.has(name), (v) => {
        if (v) state.required.add(name);
        else state.required.delete(name);
        emit();
      })
    );
    reqLbl.appendChild(document.createTextNode('required'));
    nameCol.appendChild(reqLbl);
    row.appendChild(nameCol);

    const propCol = el('div', { style: { flex: '1', minWidth: '0' } });
    function propEmit(): void {
      state.props[name] = deepClone(propState);
      emit();
    }
    const propBody = makeNodeEditor(propState, propEmit);
    propCol.appendChild(propBody);
    row.appendChild(propCol);

    row.appendChild(
      el(
        'button',
        {
          type: 'button',
          class: 'btn btn-secondary',
          style: { flex: '0 0 auto' },
          onClick: () => {
            delete state.props[name];
            state.required.delete(name);
            refresh();
            emit();
          },
        },
        '×'
      )
    );

    nameInp.addEventListener('change', () => {
      const newName = nameInp.value.trim();
      if (newName === '' || newName === name) {
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

  function refresh(): void {
    while (list.firstChild) list.removeChild(list.firstChild);
    for (const [name, sch] of Object.entries(state.props)) {
      list.appendChild(makeRow(name, sch));
    }
  }
  refresh();

  wrap.appendChild(
    el(
      'button',
      {
        type: 'button',
        class: 'btn btn-secondary',
        style: { alignSelf: 'flex-start' },
        onClick: () => {
          let i = 1;
          let n = `property${i}`;
          while (n in state.props) {
            i++;
            n = `property${i}`;
          }
          state.props[n] = { type: 'string' };
          refresh();
          emit();
        },
      },
      '+ Add property'
    )
  );
  return wrap;
}

function makeNodeEditor(state: JSONSchema, onChange: () => void): HTMLElement {
  const wrap = el('div', {
    class: 'schema-editor-node',
    style: { display: 'flex', flexDirection: 'column', gap: '4px' },
  });
  const header = el('div', {
    style: { display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' },
  });
  wrap.appendChild(header);

  const body = el('div', {});
  wrap.appendChild(body);

  const typeSel = makeSelect(TYPE_OPTIONS, state.type as string || 'string', (v) => {
    state.type = v as SchemaType;
    if (v === 'object' && !state.properties) state.properties = {};
    if (v === 'array' && !state.items) state.items = { type: 'string' };
    rebuild();
    onChange();
  });
  header.appendChild(el('span', { style: { fontSize: '0.8em', color: '#666' } }, 'type:'));
  header.appendChild(typeSel);

  header.appendChild(el('span', { style: { fontSize: '0.8em', color: '#666' } }, 'title:'));
  header.appendChild(
    makeTextInput(state.title, 'title', (v) => {
      state.title = v || undefined;
      onChange();
    })
  );
  header.appendChild(el('span', { style: { fontSize: '0.8em', color: '#666' } }, 'desc:'));
  header.appendChild(
    makeTextInput(state.description, 'description', (v) => {
      state.description = v || undefined;
      onChange();
    })
  );

  function rebuild(): void {
    while (body.firstChild) body.removeChild(body.firstChild);
    if (state.type === 'object') {
      const ed = makeObjectPropertiesEditor(state.properties, state.required, (newProps, required) => {
        state.properties = newProps;
        state.required = required;
        onChange();
      });
      body.appendChild(ed);
    } else if (state.type === 'array') {
      body.appendChild(el('div', { style: { fontSize: '0.8em', color: '#666' } }, 'items:'));
      const itemState: JSONSchema = state.items || { type: 'string' };
      state.items = itemState;
      const ed = makeNodeEditor(itemState, onChange);
      body.appendChild(ed);
    } else if (state.type === 'string') {
      const hasEnum = Array.isArray(state.enum);
      const lbl = el('label', {
        style: { display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8em' },
      });
      lbl.appendChild(document.createTextNode('enum:'));
      lbl.appendChild(
        makeCheckbox(hasEnum, (v) => {
          if (v) {
            state.enum = [''];
          } else {
            delete state.enum;
          }
          rebuild();
          onChange();
        })
      );
      body.appendChild(lbl);
      if (hasEnum) {
        body.appendChild(renderEnumEditor(state.enum, (v) => {
          state.enum = v;
          onChange();
        }));
      }
    } else if (state.type === 'number' || state.type === 'integer') {
      const r1 = el('div', { style: { display: 'flex', gap: '4px', alignItems: 'center' } });
      r1.appendChild(el('span', { style: { fontSize: '0.8em', color: '#666' } }, 'min:'));
      r1.appendChild(
        makeTextInput(state.minimum !== undefined ? String(state.minimum) : '', 'min', (v) => {
          if (v === '' || v == null) delete state.minimum;
          else state.minimum = Number(v);
          onChange();
        })
      );
      r1.appendChild(el('span', { style: { fontSize: '0.8em', color: '#666' } }, 'max:'));
      r1.appendChild(
        makeTextInput(state.maximum !== undefined ? String(state.maximum) : '', 'max', (v) => {
          if (v === '' || v == null) delete state.maximum;
          else state.maximum = Number(v);
          onChange();
        })
      );
      body.appendChild(r1);
    }
    const dRow = el('div', { style: { display: 'flex', gap: '4px', alignItems: 'center' } });
    dRow.appendChild(el('span', { style: { fontSize: '0.8em', color: '#666' } }, 'default:'));
    const dInp = makeTextarea(
      state.default !== undefined ? JSON.stringify(state.default) : '',
      'default (JSON)',
      (v) => {
        if (v === '') delete state.default;
        else {
          try {
            state.default = JSON.parse(v);
          } catch {
            /* ignore parse error during typing */
          }
        }
        onChange();
      }
    );
    dInp.style.flex = '1';
    dRow.appendChild(dInp);
    body.appendChild(dRow);
  }
  rebuild();
  return wrap;
}

export interface SchemaEditorNode {
  el: HTMLElement;
  getSchema: () => JSONSchema;
}

export function renderSchemaEditor(
  schema: JSONSchema,
  container?: HTMLElement
): SchemaEditorNode {
  const state: JSONSchema = { type: 'object', ...deepClone(schema || {}) };
  if (!state.properties && state.type === 'object') state.properties = {};
  const wrap = el('div', {
    class: 'schema-editor-root',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      border: '1px solid #aaa',
      padding: '8px',
      borderRadius: '4px',
    },
  });
  const head = el('div', { style: { display: 'flex', gap: '4px', alignItems: 'center' } });
  head.appendChild(el('strong', {}, 'Root type:'));
  head.appendChild(
    makeSelect(TYPE_OPTIONS, state.type as string, (v) => {
      state.type = v as SchemaType;
      if (v === 'object' && !state.properties) state.properties = {};
      if (v === 'array' && !state.items) state.items = { type: 'string' };
      rebuild();
    })
  );
  wrap.appendChild(head);

  const bodyWrap = el('div', {});
  wrap.appendChild(bodyWrap);

  function rebuild(): void {
    while (bodyWrap.firstChild) bodyWrap.removeChild(bodyWrap.firstChild);
    if (state.type === 'object') {
      bodyWrap.appendChild(
        makeObjectPropertiesEditor(state.properties, state.required, (newProps, required) => {
          state.properties = newProps;
          state.required = required;
        })
      );
    } else if (state.type === 'array') {
      bodyWrap.appendChild(el('div', { style: { fontSize: '0.8em', color: '#666' } }, 'items:'));
      const itemState: JSONSchema = state.items || { type: 'string' };
      state.items = itemState;
      bodyWrap.appendChild(makeNodeEditor(itemState, () => { /* noop */ }));
    } else {
      bodyWrap.appendChild(makeNodeEditor(state, () => { /* noop */ }));
    }
  }
  rebuild();
  if (container) container.appendChild(wrap);
  return {
    el: wrap,
    getSchema: () => deepClone(state),
  };
}

// Re-export for convenience
export { renderSchema };
export type { JSONSchema, SchemaNode };