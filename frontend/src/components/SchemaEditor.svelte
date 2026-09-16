<script lang="ts">
  import { type JSONSchema } from '../lib/schema.svelte.ts';
  import SchemaEditor from './SchemaEditor.svelte';

  let { schema, depth = 0 }: { schema: JSONSchema; depth?: number } = $props();

  const TYPE_OPTIONS = ['string', 'number', 'integer', 'boolean', 'object', 'array', 'null'];

  const isRoot = $derived(depth === 0);

  export function getSchema(): JSONSchema {
    return JSON.parse(JSON.stringify(schema)) as JSONSchema;
  }

  function setType(value: string): void {
    schema.type = value;
    if (value === 'object' && !schema.properties) schema.properties = {};
    if (value === 'array' && !schema.items) schema.items = { type: 'string' };
  }

  function onTypeChange(e: Event): void {
    setType((e.currentTarget as HTMLSelectElement).value);
  }

  function addProperty(): void {
    if (!schema.properties) schema.properties = {};
    let i = 1;
    let name = `property${i}`;
    while (name in schema.properties) {
      i += 1;
      name = `property${i}`;
    }
    schema.properties[name] = { type: 'string' };
  }

  function removeProperty(name: string): void {
    if (schema.properties) delete schema.properties[name];
    if (schema.required) schema.required = schema.required.filter((r) => r !== name);
  }

  function renameProperty(oldName: string, rawNewName: string, input: HTMLInputElement): void {
    const newName = rawNewName.trim();
    if (newName === '' || newName === oldName || !schema.properties) {
      input.value = oldName;
      return;
    }
    if (newName in schema.properties) {
      input.value = oldName;
      return;
    }
    const wasRequired = (schema.required || []).includes(oldName);
    const value = schema.properties[oldName];
    delete schema.properties[oldName];
    schema.properties[newName] = value;
    if (schema.required) {
      schema.required = schema.required.filter((r) => r !== oldName);
      if (wasRequired) schema.required.push(newName);
    }
    input.value = newName;
  }

  function onNameChange(e: Event, name: string): void {
    renameProperty(name, (e.currentTarget as HTMLInputElement).value, e.currentTarget as HTMLInputElement);
  }

  function isRequired(name: string): boolean {
    return (schema.required || []).includes(name);
  }

  function toggleRequired(name: string, checked: boolean): void {
    const req = new Set(schema.required || []);
    if (checked) req.add(name);
    else req.delete(name);
    schema.required = [...req];
  }

  function onRequiredChange(e: Event, name: string): void {
    toggleRequired(name, (e.currentTarget as HTMLInputElement).checked);
  }

  function toggleEnum(checked: boolean): void {
    if (checked) schema.enum = [''];
    else delete schema.enum;
  }

  function onEnumToggle(e: Event): void {
    toggleEnum((e.currentTarget as HTMLInputElement).checked);
  }

  function setEnumValue(index: number, value: string): void {
    if (!schema.enum) return;
    const next = [...schema.enum];
    next[index] = value;
    schema.enum = next;
  }

  function addEnumValue(): void {
    schema.enum = [...(schema.enum || []), ''];
  }

  function removeEnumValue(index: number): void {
    if (!schema.enum) return;
    const next = [...schema.enum];
    next.splice(index, 1);
    schema.enum = next;
  }

  function onTitleInput(e: Event): void {
    const v = (e.currentTarget as HTMLInputElement).value;
    schema.title = v || undefined;
  }

  function onDescInput(e: Event): void {
    const v = (e.currentTarget as HTMLInputElement).value;
    schema.description = v || undefined;
  }

  function onMinimumInput(e: Event): void {
    const v = (e.currentTarget as HTMLInputElement).value;
    if (v === '') delete schema.minimum;
    else schema.minimum = Number(v);
  }

  function onMaximumInput(e: Event): void {
    const v = (e.currentTarget as HTMLInputElement).value;
    if (v === '') delete schema.maximum;
    else schema.maximum = Number(v);
  }

  function onDefaultInput(e: Event): void {
    const v = (e.currentTarget as HTMLTextAreaElement).value;
    if (v === '') {
      delete schema.default;
      return;
    }
    try {
      schema.default = JSON.parse(v);
    } catch {
      /* ignore parse errors while typing */
    }
  }
</script>

{#if isRoot}
  <div
    class="schema-editor-root"
    style="display: flex; flex-direction: column; gap: 8px; border: 1px solid #aaa; padding: 8px; border-radius: 4px;"
  >
    <div style="display: flex; gap: 4px; align-items: center;">
      <strong>Root type:</strong>
      <select value={(schema.type as string) || 'string'} onchange={onTypeChange}>
        {#each TYPE_OPTIONS as opt}
          <option value={opt}>{opt}</option>
        {/each}
      </select>
    </div>

    {#if schema.type === 'object'}
      {@render propertiesEditor()}
    {:else if schema.type === 'array'}
      {@render arrayItems()}
    {:else}
      {@render scalarEditor()}
    {/if}

    {@render defaultEditor()}
  </div>
{:else}
  <div
    class="schema-editor-node"
    style="display: flex; flex-direction: column; gap: 4px;"
  >
    <div style="display: flex; gap: 4px; align-items: center; flex-wrap: wrap;">
      <span style="font-size: 0.8em; color: #666;">type:</span>
      <select value={(schema.type as string) || 'string'} onchange={onTypeChange}>
        {#each TYPE_OPTIONS as opt}
          <option value={opt}>{opt}</option>
        {/each}
      </select>
      <span style="font-size: 0.8em; color: #666;">title:</span>
      <input type="text" value={schema.title ?? ''} placeholder="title" oninput={onTitleInput} />
      <span style="font-size: 0.8em; color: #666;">desc:</span>
      <input
        type="text"
        value={schema.description ?? ''}
        placeholder="description"
        oninput={onDescInput}
      />
    </div>

    {#if schema.type === 'object'}
      {@render propertiesEditor()}
    {:else if schema.type === 'array'}
      {@render arrayItems()}
    {:else}
      {@render scalarEditor()}
    {/if}

    {@render defaultEditor()}
  </div>
{/if}

{#snippet propertiesEditor()}
  <div class="schema-editor-properties" style="display: flex; flex-direction: column; gap: 6px;">
    <div style="display: flex; flex-direction: column; gap: 4px;">
      {#each Object.entries(schema.properties ?? {}) as [name, prop] (name)}
        <div
          class="schema-editor-property-row"
          style="display: flex; gap: 4px; align-items: flex-start; border: 1px solid #ddd; padding: 6px; border-radius: 4px; background: #fafafa;"
        >
          <div style="display: flex; flex-direction: column; gap: 2px; min-width: 120px;">
            <input
              type="text"
              value={name}
              placeholder="name"
              style="width: 120px;"
              onchange={(e) => onNameChange(e, name)}
            />
            <label style="display: flex; align-items: center; gap: 4px; font-size: 0.75em;">
              <input
                type="checkbox"
                checked={isRequired(name)}
                onchange={(e) => onRequiredChange(e, name)}
              />
              required
            </label>
          </div>
          <div style="flex: 1; min-width: 0;">
            <SchemaEditor schema={prop} depth={depth + 1} />
          </div>
          <button
            type="button"
            class="btn preset-tonal"
            style="flex: 0 0 auto;"
            onclick={() => removeProperty(name)}
          >
            ×
          </button>
        </div>
      {/each}
    </div>
    <button
      type="button"
      class="btn preset-tonal"
      style="align-self: flex-start;"
      onclick={addProperty}
    >
      + Add property
    </button>
  </div>
{/snippet}

{#snippet arrayItems()}
  <div>
    <div style="font-size: 0.8em; color: #666;">items:</div>
    {#if schema.items}
      <SchemaEditor schema={schema.items} depth={depth + 1} />
    {/if}
  </div>
{/snippet}

{#snippet scalarEditor()}
  {#if schema.type === 'string'}
    <label style="display: flex; align-items: center; gap: 4px; font-size: 0.8em;">
      <input type="checkbox" checked={Array.isArray(schema.enum)} onchange={onEnumToggle} />
      enum:
    </label>
    {#if Array.isArray(schema.enum)}
      <div class="schema-editor-enum" style="display: flex; flex-direction: column; gap: 4px;">
        <div style="display: flex; flex-direction: column; gap: 2px;">
          {#each schema.enum as value, index (index)}
            <div style="display: flex; gap: 4px; align-items: center;">
              <input
                type="text"
                value={String(value ?? '')}
                placeholder="value"
                oninput={(e) => setEnumValue(index, (e.currentTarget as HTMLInputElement).value)}
              />
              <button
                type="button"
                class="btn preset-tonal"
                onclick={() => removeEnumValue(index)}
              >
                ×
              </button>
            </div>
          {/each}
        </div>
        <button
          type="button"
          class="btn preset-tonal"
          style="align-self: flex-start;"
          onclick={addEnumValue}
        >
          + Add value
        </button>
      </div>
    {/if}
  {:else if schema.type === 'number' || schema.type === 'integer'}
    <div style="display: flex; gap: 4px; align-items: center;">
      <span style="font-size: 0.8em; color: #666;">min:</span>
      <input
        type="text"
        value={schema.minimum !== undefined ? String(schema.minimum) : ''}
        placeholder="min"
        oninput={onMinimumInput}
      />
      <span style="font-size: 0.8em; color: #666;">max:</span>
      <input
        type="text"
        value={schema.maximum !== undefined ? String(schema.maximum) : ''}
        placeholder="max"
        oninput={onMaximumInput}
      />
    </div>
  {/if}
{/snippet}

{#snippet defaultEditor()}
  <div style="display: flex; gap: 4px; align-items: center;">
    <span style="font-size: 0.8em; color: #666;">default:</span>
    <textarea
      rows="3"
      placeholder="default (JSON)"
      style="flex: 1; font-family: monospace; width: 100%; box-sizing: border-box;"
      value={schema.default !== undefined ? JSON.stringify(schema.default) : ''}
      oninput={onDefaultInput}
    ></textarea>
  </div>
{/snippet}
