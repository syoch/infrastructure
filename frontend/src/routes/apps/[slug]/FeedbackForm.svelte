<script lang="ts">
  import { Combobox, useListCollection } from '@skeletonlabs/skeleton-svelte';
  import { safeURL } from '../../../lib/ui.js';

  let {
    webui_url,
    sending,
    kind = $bindable('feedback'),
    onsubmit,
  }: {
    webui_url?: string | null;
    sending: boolean;
    kind?: string;
    onsubmit: (e: SubmitEvent) => void;
  } = $props();

  const kindOptions = [
    { label: 'フィードバック', value: 'feedback' },
    { label: '不具合', value: 'bug' },
    { label: '要望', value: 'feature' },
    { label: '質問', value: 'question' },
  ];
  const kindCollection = $derived(
    useListCollection({
      items: kindOptions,
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    })
  );
</script>

<section class="card bg-surface-100-900 p-6">
  <header class="mb-4"><h2 class="h4 m-0">フィードバックを送信</h2></header>
  <form id="feedback-form" class="grid gap-4" onsubmit={onsubmit}>
    <div class="label">
      <label class="label-text" for="fb-kind">種別</label>
      <input type="hidden" name="kind" value={kind}>
      <Combobox
        placeholder="フィードバック"
        openOnClick
        collection={kindCollection}
        value={[kind]}
        onValueChange={(details) => {
          kind = details.value[0] ?? 'feedback';
        }}
      >
        <Combobox.Control>
          <Combobox.Input id="fb-kind" readonly class="input" />
          <Combobox.Trigger data-testid="fb-kind-trigger" />
        </Combobox.Control>
        <Combobox.Positioner>
          <Combobox.Content class="z-50">
            {#each kindOptions as item (item.value)}
              <Combobox.Item {item} data-testid={`fb-kind-option-${item.value}`}>
                <Combobox.ItemText>{item.label}</Combobox.ItemText>
                <Combobox.ItemIndicator />
              </Combobox.Item>
            {/each}
          </Combobox.Content>
        </Combobox.Positioner>
      </Combobox>
    </div>
    <label class="label">
      <span class="label-text">内容 *</span>
      <textarea id="fb-body" name="body" class="textarea" rows="5" required placeholder="気づいた点や要望を書いてください"></textarea>
    </label>
    <div class="flex flex-wrap items-center gap-2">
      <button type="submit" class="btn preset-filled-primary-500" disabled={sending}>
        {sending ? '送信中…' : '送信 (エージェントに注入)'}
      </button>
      {#if webui_url}
        <a class="btn preset-tonal" href={safeURL(webui_url)} target="_blank" rel="noopener">セッションを開くだけ</a>
      {/if}
    </div>
  </form>
</section>
