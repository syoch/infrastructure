<script lang="ts">
  import { flushSync } from 'svelte';
  import { SchemaNode, type JSONSchema } from '../lib/schema.svelte.ts';
  import SchemaForm from './SchemaForm.svelte';
  import SchemaEditor from './SchemaEditor.svelte';

  let { node }: { node: SchemaNode } = $props();

  export function getValue(): unknown {
    return node.getValue();
  }

  export function setValue(v: unknown): void {
    node.setValue(v);
  }

  function onTextInput(e: Event): void {
    node.value = (e.currentTarget as HTMLInputElement | HTMLTextAreaElement).value;
  }

  function onNumberInput(e: Event): void {
    node.value = (e.currentTarget as HTMLInputElement).value;
  }

  function onCheckbox(e: Event): void {
    node.value = (e.currentTarget as HTMLInputElement).checked;
  }

  function onSelect(e: Event): void {
    node.value = (e.currentTarget as HTMLSelectElement).value;
  }

  function onVariant(e: Event): void {
    node.variantIndex = Number((e.currentTarget as HTMLSelectElement).value);
    flushSync();
  }

  function itemSchema(): JSONSchema {
    return node.schema.items || { type: 'string' };
  }

  function addItem(): void {
    node.items.push(new SchemaNode(itemSchema(), node.root));
    flushSync();
  }

  function removeItem(index: number): void {
    node.items.splice(index, 1);
    flushSync();
  }
</script>

{#if node.kind === 'object'}
  <div
    class="schema-object"
    style="display: flex; flex-direction: column; gap: 8px; border-left: 2px solid #eee; padding-left: 8px;"
  >
    {#each Object.entries(node.children) as [name, child] (name)}
      <SchemaForm node={child} />
    {/each}
  </div>
{:else if node.kind === 'array'}
  <div class="schema-array" style="display: flex; flex-direction: column; gap: 6px;">
    <button type="button" class="btn preset-tonal" style="align-self: flex-start;" onclick={addItem}>
      + Add
    </button>
    <div class="schema-array-items" style="display: flex; flex-direction: column; gap: 4px;">
      {#each node.items as item, index (item)}
        <div
          class="schema-array-item"
          style="display: flex; align-items: flex-start; gap: 6px; border: 1px solid #ddd; padding: 4px; border-radius: 4px;"
        >
          <SchemaForm node={item} />
          <button
            type="button"
            class="btn preset-tonal"
            style="flex: 0 0 auto;"
            onclick={() => removeItem(index)}
          >
            ×
          </button>
        </div>
      {/each}
    </div>
  </div>
{:else if node.kind === 'oneOf'}
  <div
    class="schema-oneof"
    style="display: flex; flex-direction: column; gap: 4px; border: 1px dashed #aaa; padding: 6px; border-radius: 4px;"
  >
    <label style="display: flex; flex-direction: column; gap: 2px;">
      <span style="font-size: 0.85em;">type</span>
      <select value={String(node.variantIndex)} onchange={onVariant}>
        {#each node.variants as variant, index (index)}
          <option value={String(index)}>
            {variant.schema.title || variant.schema.$ref || `variant ${index}`}
          </option>
        {/each}
      </select>
    </label>
    <div class="schema-oneof-content">
      {#if node.variants[node.variantIndex]}
        <SchemaForm node={node.variants[node.variantIndex]} />
      {/if}
    </div>
  </div>
{:else if node.kind === 'null'}
  <span style="color: #888;">(null)</span>
{:else if node.kind === 'const'}
  <div style="padding: 4px; color: #666;">(constant: {JSON.stringify(node.schema.const)})</div>
{:else if node.kind === 'boolean'}
  <label style="display: inline-flex; align-items: center; gap: 6px;">
    <input type="checkbox" checked={Boolean(node.value)} onchange={onCheckbox} />
    {node.schema.title || ''}
  </label>
{:else}
  <div class="schema-field" style="display: flex; flex-direction: column; gap: 2px;">
    {#if node.schema.title}
      <span class="schema-field-title" style="font-size: 0.85em;">
        {node.schema.title}{node.required ? ' *' : ''}
      </span>
    {/if}
    {#if node.kind === 'enum'}
      <select value={String(node.value ?? '')} onchange={onSelect}>
        {#each node.schema.enum ?? [] as opt}
          <option value={String(opt)}>{String(opt)}</option>
        {/each}
      </select>
    {:else if node.kind === 'schema_editor'}
      {#if node.editor}
        <SchemaEditor schema={node.editor} depth={0} />
      {/if}
    {:else if node.kind === 'textarea'}
      <textarea
        rows="3"
        placeholder={node.schema.description ?? ''}
        style="font-family: monospace; width: 100%; box-sizing: border-box;"
        value={String(node.value ?? '')}
        oninput={onTextInput}
      ></textarea>
    {:else if node.kind === 'json'}
      <textarea
        rows="6"
        placeholder={node.schema.description ?? ''}
        style="font-family: monospace; width: 100%; box-sizing: border-box;"
        value={String(node.value ?? '')}
        oninput={onTextInput}
      ></textarea>
    {:else if node.kind === 'password'}
      <input
        type="password"
        placeholder={node.schema.description ?? ''}
        value={String(node.value ?? '')}
        oninput={onTextInput}
      />
    {:else if node.kind === 'number'}
      <input
        type="number"
        step={node.schema.type === 'integer' ? '1' : 'any'}
        min={node.schema.minimum !== undefined ? String(node.schema.minimum) : undefined}
        max={node.schema.maximum !== undefined ? String(node.schema.maximum) : undefined}
        placeholder={node.schema.description ?? ''}
        value={String(node.value ?? '')}
        oninput={onNumberInput}
      />
    {:else}
      <input
        type="text"
        pattern={node.schema.pattern}
        minlength={node.schema.minLength}
        maxlength={node.schema.maxLength}
        placeholder={node.schema.description ?? ''}
        value={String(node.value ?? '')}
        oninput={onTextInput}
      />
    {/if}
  </div>
{/if}
