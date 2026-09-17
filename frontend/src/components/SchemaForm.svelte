<script lang="ts">
  import { flushSync } from 'svelte';
  import { Listbox, Switch, useListCollection } from '@skeletonlabs/skeleton-svelte';
  import { SchemaNode, type JSONSchema } from '../lib/schema.svelte.ts';
  import SchemaForm from './SchemaForm.svelte';
  import SchemaEditor from './SchemaEditor.svelte';

  let { node }: { node: SchemaNode } = $props();

  const enumOptions = $derived(
    (node.schema.enum ?? []).map((opt) => ({ label: String(opt), value: String(opt) }))
  );
  const enumCollection = $derived(
    useListCollection({
      items: enumOptions,
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    })
  );
  const variantOptions = $derived(
    node.variants.map((variant, index) => ({
      label: variant.schema.title || variant.schema.$ref || `variant ${index}`,
      value: String(index),
    }))
  );
  const variantCollection = $derived(
    useListCollection({
      items: variantOptions,
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    })
  );

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

  function onVariant(value: string): void {
    node.variantIndex = Number(value);
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
    <div style="display: flex; flex-direction: column; gap: 2px;">
      <span style="font-size: 0.85em;">type</span>
      <Listbox
        collection={variantCollection}
        value={[String(node.variantIndex)]}
        onValueChange={(details) => onVariant(details.value[0] ?? '0')}
      >
        <Listbox.Content>
          {#each variantOptions as item (item.value)}
            <Listbox.Item {item}>
              <Listbox.ItemText>{item.label}</Listbox.ItemText>
              <Listbox.ItemIndicator />
            </Listbox.Item>
          {/each}
        </Listbox.Content>
      </Listbox>
    </div>
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
  <div style="display: inline-flex; align-items: center; gap: 6px;">
    <Switch
      data-testid="schema-boolean-switch"
      checked={Boolean(node.value)}
      onCheckedChange={(details) => {
        node.value = details.checked;
      }}
      label={node.schema.title || 'boolean'}
    >
      <Switch.Control><Switch.Thumb /></Switch.Control>
      <Switch.HiddenInput data-testid="schema-boolean-input" />
    </Switch>
    {#if node.schema.title}<span>{node.schema.title}</span>{/if}
  </div>
{:else}
  <div class="schema-field" style="display: flex; flex-direction: column; gap: 2px;">
    {#if node.schema.title}
      <span class="schema-field-title" style="font-size: 0.85em;">
        {node.schema.title}{node.required ? ' *' : ''}
      </span>
    {/if}
    {#if node.kind === 'enum'}
      <Listbox
        collection={enumCollection}
        value={node.value === undefined || node.value === null ? [] : [String(node.value)]}
        onValueChange={(details) => {
          node.value = details.value[0];
        }}
      >
        <Listbox.Content>
          {#each enumOptions as item (item.value)}
            <Listbox.Item {item}>
              <Listbox.ItemText>{item.label}</Listbox.ItemText>
              <Listbox.ItemIndicator />
            </Listbox.Item>
          {/each}
        </Listbox.Content>
      </Listbox>
    {:else if node.kind === 'schema_editor'}
      {#if node.editor}
        <SchemaEditor schema={node.editor} depth={0} />
      {/if}
    {:else if node.kind === 'textarea'}
      <textarea
        class="textarea"
        rows="3"
        placeholder={node.schema.description ?? ''}
        style="font-family: monospace; width: 100%; box-sizing: border-box;"
        value={String(node.value ?? '')}
        oninput={onTextInput}
      ></textarea>
    {:else if node.kind === 'json'}
      <textarea
        class="textarea"
        rows="6"
        placeholder={node.schema.description ?? ''}
        style="font-family: monospace; width: 100%; box-sizing: border-box;"
        value={String(node.value ?? '')}
        oninput={onTextInput}
      ></textarea>
    {:else if node.kind === 'password'}
      <input
        class="input"
        type="password"
        placeholder={node.schema.description ?? ''}
        value={String(node.value ?? '')}
        oninput={onTextInput}
      />
    {:else if node.kind === 'number'}
      <input
        class="input"
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
        class="input"
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
