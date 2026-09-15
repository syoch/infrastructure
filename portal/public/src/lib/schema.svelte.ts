// Reactive JSON Schema model shared by SchemaForm.svelte, SchemaEditor.svelte
// and the imperative adapter in js/schema_api.ts.

export interface UIHint {
  widget?: 'textarea' | 'password' | 'json' | 'schema_editor';
  kind?: string;
  label?: string;
  timeout_seconds?: number;
  [key: string]: unknown;
}

export interface JSONSchema {
  type?: string | string[];
  title?: string;
  description?: string;
  enum?: unknown[];
  oneOf?: JSONSchema[];
  anyOf?: JSONSchema[];
  $ref?: string;
  default?: unknown;
  const?: unknown;
  properties?: Record<string, JSONSchema>;
  required?: string[];
  items?: JSONSchema;
  pattern?: string;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  ui_hint?: UIHint;
  [key: string]: unknown;
}

export function isPlainObject(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

export function deepClone<T>(v: T): T {
  if (v === null || typeof v !== 'object') return v;
  if (Array.isArray(v)) return v.map((x) => deepClone(x)) as unknown as T;
  const out: Record<string, unknown> = {};
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) out[k] = deepClone(val);
  return out as T;
}

export function resolveRef(ref: string, root: JSONSchema): JSONSchema | null {
  if (!ref.startsWith('#/')) return null;
  const path = ref.slice(2).split('/');
  let node: unknown = root;
  for (const segment of path) {
    if (node == null) return null;
    const key = decodeURIComponent(segment.replace(/~1/g, '/').replace(/~0/g, '~'));
    node = (node as Record<string, unknown>)[key];
  }
  return (node as JSONSchema) || null;
}

export function effectiveType(schema: JSONSchema | null | undefined): string {
  if (!schema) return 'string';
  if (Array.isArray(schema.type)) {
    return schema.type.includes('null') ? 'string' : schema.type[0];
  }
  return schema.type || 'string';
}

export type NodeKind =
  | 'string'
  | 'textarea'
  | 'password'
  | 'json'
  | 'enum'
  | 'number'
  | 'boolean'
  | 'null'
  | 'const'
  | 'array'
  | 'object'
  | 'oneOf'
  | 'schema_editor';

export function nodeKind(schema: JSONSchema, root: JSONSchema, depth = 0): NodeKind {
  if (!schema || typeof schema !== 'object' || depth > 64) return 'string';
  if (schema.$ref) {
    const resolved = resolveRef(schema.$ref, root);
    if (resolved) return nodeKind(resolved, root, depth + 1);
  }
  if (schema.const !== undefined) return 'const';
  if (schema.oneOf || schema.anyOf) return 'oneOf';
  if (schema.enum) return 'enum';
  if (schema.ui_hint?.widget === 'schema_editor') return 'schema_editor';
  const widget = schema.ui_hint?.widget;
  switch (effectiveType(schema)) {
    case 'string':
      if (widget === 'textarea') return 'textarea';
      if (widget === 'password') return 'password';
      if (widget === 'json') return 'json';
      return 'string';
    case 'number':
    case 'integer':
      return 'number';
    case 'boolean':
      return 'boolean';
    case 'null':
      return 'null';
    case 'array':
      return 'array';
    case 'object':
      return 'object';
    default:
      return 'string';
  }
}

export function createEditorState(schema: JSONSchema): JSONSchema {
  const state = $state<JSONSchema>(deepClone(schema || {}));
  if (!state.type) state.type = 'object';
  if (state.type === 'object' && !state.properties) state.properties = {};
  return state;
}

export class SchemaNode {
  schema: JSONSchema;
  root: JSONSchema;
  kind: NodeKind;
  required: Set<string> = new Set();
  editor: JSONSchema | null = null;

  value = $state<unknown>('');
  children = $state<Record<string, SchemaNode>>({});
  items = $state<SchemaNode[]>([]);
  variants = $state<SchemaNode[]>([]);
  variantIndex = $state(0);

  constructor(schema: JSONSchema, root: JSONSchema) {
    this.schema = schema;
    this.root = root;
    this.kind = nodeKind(schema, root);
    this.init();
  }

  private init(): void {
    const s = this.schema;
    switch (this.kind) {
      case 'object': {
        const next: Record<string, SchemaNode> = {};
        for (const [name, prop] of Object.entries(s.properties || {})) {
          next[name] = new SchemaNode({ ...prop, title: prop.title || name }, this.root);
        }
        this.children = next;
        this.required = new Set(s.required || []);
        break;
      }
      case 'array':
        this.items = [];
        break;
      case 'oneOf': {
        const variants = s.oneOf || s.anyOf || [];
        this.variants = variants.map((v) => {
          let resolved = v;
          if (v.$ref) {
            const r = resolveRef(v.$ref, this.root);
            if (r) resolved = r;
          }
          return new SchemaNode(resolved, this.root);
        });
        break;
      }
      case 'boolean':
        this.value = s.default !== undefined ? s.default : false;
        break;
      case 'null':
        this.value = null;
        break;
      case 'const':
        this.value = s.const ?? null;
        break;
      case 'schema_editor':
        this.editor = createEditorState(
          (s.default as JSONSchema) || { type: 'object', properties: {} }
        );
        break;
      case 'json':
        this.value =
          s.default !== undefined
            ? typeof s.default === 'string'
              ? s.default
              : JSON.stringify(s.default, null, 2)
            : '';
        break;
      case 'number':
        this.value = s.default !== undefined ? String(s.default) : '';
        break;
      default:
        this.value = s.default !== undefined ? s.default : '';
        break;
    }
  }

  getValue(): unknown {
    switch (this.kind) {
      case 'object': {
        const out: Record<string, unknown> = {};
        for (const [name, node] of Object.entries(this.children)) {
          let v: unknown;
          try {
            v = node.getValue();
          } catch (e) {
            throw new Error(`field '${name}': ${e instanceof Error ? e.message : String(e)}`);
          }
          if (v !== undefined && v !== '') {
            out[name] = v;
          } else if (this.required.has(name) && node.kind === 'boolean') {
            out[name] = false;
          }
        }
        const props = this.schema.properties || {};
        for (const req of this.required) {
          if (!(req in out)) {
            const f = props[req];
            if (f && f.default !== undefined) out[req] = f.default;
            else throw new Error(`missing required field: ${req}`);
          }
        }
        return out;
      }
      case 'array':
        return this.items.map((n) => n.getValue());
      case 'oneOf': {
        const n = this.variants[this.variantIndex];
        return n ? n.getValue() : undefined;
      }
      case 'const':
        return this.schema.const ?? null;
      case 'schema_editor':
        return this.editor ? deepClone(this.editor) : {};
      case 'json': {
        const raw = typeof this.value === 'string' ? this.value.trim() : '';
        if (raw === '') return undefined;
        try {
          return JSON.parse(raw);
        } catch (e) {
          throw new Error(`invalid JSON: ${e instanceof Error ? e.message : String(e)}`);
        }
      }
      case 'number': {
        if (this.value === '' || this.value === undefined || this.value === null) return undefined;
        const n = Number(this.value);
        if (Number.isNaN(n)) throw new Error(`not a number: ${String(this.value)}`);
        return this.schema.type === 'integer' ? Math.trunc(n) : n;
      }
      case 'boolean':
        return Boolean(this.value);
      case 'null':
        return null;
      default:
        return this.value;
    }
  }

  setValue(v: unknown): void {
    switch (this.kind) {
      case 'object':
        if (!isPlainObject(v)) return;
        for (const [name, val] of Object.entries(v)) {
          const child = this.children[name];
          if (child) child.setValue(val);
        }
        return;
      case 'array':
        this.items = [];
        if (Array.isArray(v)) {
          for (const val of v) {
            const item = new SchemaNode(this.schema.items || { type: 'string' }, this.root);
            item.setValue(val);
            this.items.push(item);
          }
        }
        return;
      case 'oneOf': {
        const n = this.variants[this.variantIndex];
        if (n) n.setValue(v);
        return;
      }
      case 'schema_editor':
        if (this.editor && isPlainObject(v)) {
          for (const k of Object.keys(this.editor)) delete this.editor[k];
          for (const [k, val] of Object.entries(deepClone(v))) this.editor[k] = val;
        }
        return;
      default:
        this.value = v;
    }
  }
}
