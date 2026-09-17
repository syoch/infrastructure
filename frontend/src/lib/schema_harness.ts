import { flushSync } from 'svelte';
import { renderSchema, renderSchemaEditor } from './schema_api';
import type { JSONSchema } from './schema.svelte';

export interface HarnessResult {
  pass: boolean;
  name: string;
  extra?: unknown;
  error?: string;
}

function fire(el: Element, type: string): void {
  el.dispatchEvent(new Event(type, { bubbles: true }));
}
function setValue(el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string): void {
  el.value = value;
  fire(el, 'input');
}
function setChange(el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string): void {
  el.value = value;
  fire(el, 'change');
}
/** Select a Skeleton/Zag Listbox option by its underlying value, then flush. */
function selectOption(el: Element, value: string): void {
  const item = el.querySelector(`[data-value="${value}"]`) as HTMLElement | null;
  if (!item) throw new Error(`listbox option not found: ${value}`);
  item.click();
  flushSync();
}
/** Toggle a Skeleton/Zag Switch through its hidden checkbox input. */
function toggleSwitch(el: Element): void {
  const input = el.querySelector('input[type="checkbox"]') as HTMLInputElement | null;
  if (!input) throw new Error('switch input not found');
  input.click();
  flushSync();
}

/** Runs the standalone schema renderer/editor test cases against the DOM. */
export function runSchemaHarness(): HarnessResult[] {
  const results: HarnessResult[] = [];

  function assert(cond: unknown, name: string, extra?: unknown): void {
    results.push({ pass: !!cond, name, extra: extra ?? null });
  }

  function runCase(name: string, fn: () => void): void {
    try {
      fn();
    } catch (err) {
      const e = err as Error;
      results.push({ pass: false, name, error: e.message });
    }
  }

  runCase('string', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getValue } = renderSchema({ type: 'string', title: 'Name' }, root);
    setValue(el.querySelector('input') as HTMLInputElement, 'alice');
    assert(getValue() === 'alice', 'string input roundtrip');
  });

  runCase('integer with min/max', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getValue } = renderSchema({ type: 'integer', minimum: 0, maximum: 10 }, root);
    setValue(el.querySelector('input') as HTMLInputElement, '5');
    assert(getValue() === 5, 'integer parse');
  });

  runCase('boolean', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getValue } = renderSchema({ type: 'boolean' }, root);
    toggleSwitch(el);
    assert(getValue() === true, 'boolean true');
    toggleSwitch(el);
    assert(getValue() === false, 'boolean false');
  });

  runCase('enum', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getValue } = renderSchema({ type: 'string', enum: ['a', 'b', 'c'] }, root);
    selectOption(el, 'b');
    assert(getValue() === 'b', 'enum listbox');
  });

  runCase('object with required', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const schema: JSONSchema = {
      type: 'object',
      required: ['name'],
      properties: {
        name: { type: 'string', title: 'Name' },
        age: { type: 'integer' },
      },
    };
    const { el, getValue } = renderSchema(schema, root);
    const inputs = el.querySelectorAll('input');
    setValue(inputs[0], 'bob');
    setValue(inputs[1], '30');
    const v = getValue() as { name?: string; age?: number };
    assert(v.name === 'bob' && v.age === 30, 'object roundtrip', v);
  });

  runCase('json widget', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getValue } = renderSchema(
      { type: 'string', ui_hint: { widget: 'json' } },
      root
    );
    setValue(el.querySelector('textarea') as HTMLTextAreaElement, '{"x": 1, "y": [2,3]}');
    const v = getValue() as { x?: number; y?: unknown[] };
    assert(v && v.x === 1 && Array.isArray(v.y) && v.y.length === 2, 'json widget parse', v);
  });

  runCase('array of strings', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getValue } = renderSchema({ type: 'array', items: { type: 'string' } }, root);
    const addBtn = el.querySelector('button') as HTMLButtonElement;
    addBtn.click();
    addBtn.click();
    addBtn.click();
    const inputs = el.querySelectorAll('input');
    setValue(inputs[0], 'a');
    setValue(inputs[1], 'b');
    setValue(inputs[2], 'c');
    const v = getValue() as string[];
    assert(Array.isArray(v) && v.length === 3 && v[0] === 'a', 'array of strings', v);
  });

  runCase('nested object in array', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const schema: JSONSchema = {
      type: 'array',
      items: {
        type: 'object',
        required: ['name'],
        properties: {
          name: { type: 'string' },
          value: { type: 'integer' },
        },
      },
    };
    const { el, getValue } = renderSchema(schema, root);
    (el.querySelector('button') as HTMLButtonElement).click();
    (el.querySelector('button') as HTMLButtonElement).click();
    const items = el.querySelectorAll('.schema-array-item');
    const inputs0 = items[0].querySelectorAll('input');
    setValue(inputs0[0], 'first');
    setValue(inputs0[1], '42');
    const inputs1 = items[1].querySelectorAll('input');
    setValue(inputs1[0], 'second');
    const v = getValue() as { name?: string; value?: number }[];
    assert(
      v.length === 2 && v[0].name === 'first' && v[0].value === 42,
      'nested object in array',
      v
    );
  });

  runCase('oneOf selection', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const schema: JSONSchema = {
      oneOf: [
        { type: 'object', title: 'Person', properties: { name: { type: 'string' } } },
        { type: 'object', title: 'Robot', properties: { id: { type: 'integer' } } },
      ],
    };
    const { el, getValue } = renderSchema(schema, root);
    selectOption(el, '1');
    setValue(el.querySelector('input') as HTMLInputElement, '7');
    const v = getValue() as { id?: number };
    assert(v && v.id === 7, 'oneOf variant', v);
  });

  runCase('schema editor add/remove', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getSchema } = renderSchemaEditor(
      { type: 'object', properties: { a: { type: 'string' } } },
      root
    );
    const addBtns = el.querySelectorAll('button');
    const addBtn = Array.from(addBtns).find((b) => (b.textContent ?? '').includes('Add property'));
    if (!addBtn) {
      assert(false, 'schema editor: addBtn not found', Array.from(addBtns).map((b) => b.textContent));
      return;
    }
    addBtn.click();
    const s = getSchema() as { properties?: Record<string, unknown> };
    assert(Object.keys(s.properties ?? {}).length === 2, 'schema editor added property', Object.keys(s.properties ?? {}));
  });

  runCase('schema editor rename', () => {
    const root = document.createElement('div');
    document.body.appendChild(root);
    const { el, getSchema } = renderSchemaEditor(
      { type: 'object', properties: { foo: { type: 'string' } } },
      root
    );
    setChange(
      el.querySelector('.schema-editor-property-name') as HTMLInputElement,
      'bar'
    );
    const s = getSchema() as { properties?: Record<string, unknown> };
    assert('bar' in (s.properties ?? {}), 'schema editor renamed property', Object.keys(s.properties ?? {}));
  });

  return results;
}
