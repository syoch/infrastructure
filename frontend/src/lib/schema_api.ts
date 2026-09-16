// Stable, imperative entry point for the standalone schema renderer test
// harness (public-static/test_schema_renderer.html) and legacy callers.
// Bundled by Vite to dist/js/schema_api.js. The actual implementation lives
// in the Svelte components under src/components.
import { mount, flushSync } from 'svelte';
import SchemaForm from '../components/SchemaForm.svelte';
import SchemaEditor from '../components/SchemaEditor.svelte';
import {
  SchemaNode,
  createEditorState,
  deepClone,
  isPlainObject,
  type JSONSchema,
} from './schema.svelte.ts';

export interface SchemaRenderHandle {
  el: HTMLElement;
  getValue(): unknown;
  setValue(v: unknown): void;
}

export interface SchemaEditorHandle {
  el: HTMLElement;
  getSchema(): unknown;
}

function mountInto(
  component: typeof SchemaForm | typeof SchemaEditor,
  props: Record<string, unknown>,
  container?: HTMLElement
): { el: HTMLElement; instance: Record<string, unknown> } {
  const wrapper = document.createElement('div');
  const instance = mount(component as never, { target: wrapper, props } as never) as Record<
    string,
    unknown
  >;
  if (container) container.appendChild(wrapper);
  flushSync();
  return { el: wrapper, instance };
}

export function renderSchema(
  schema: JSONSchema,
  container?: HTMLElement
): SchemaRenderHandle {
  const rootSchema: JSONSchema = schema || { type: 'object', properties: {} };
  const node = new SchemaNode(rootSchema, rootSchema);
  const { el } = mountInto(SchemaForm, { node }, container);
  return {
    el,
    getValue: () => {
      const value = node.getValue();
      if (rootSchema.type === 'object' && !isPlainObject(value)) return {};
      return value;
    },
    setValue: (v: unknown) => node.setValue(v),
  };
}

export function renderSchemaEditor(
  schema: JSONSchema,
  container?: HTMLElement
): SchemaEditorHandle {
  const state = createEditorState(schema || { type: 'object', properties: {} });
  const { el } = mountInto(SchemaEditor, { schema: state, depth: 0 }, container);
  return {
    el,
    getSchema: () => deepClone(state),
  };
}
