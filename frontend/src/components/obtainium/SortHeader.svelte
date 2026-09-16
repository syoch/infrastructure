<script lang="ts">
  type SortDirection = 'asc' | 'desc' | null;

  let {
    id,
    iconId,
    direction,
    onclick,
    label = 'カテゴリ',
  }: {
    id: string;
    iconId: string;
    direction: SortDirection;
    onclick: () => void;
    label?: string;
  } = $props();
</script>

<button type="button" {id} class="flex cursor-pointer items-center gap-1" {onclick}>
  {label} <span id={iconId} class="opacity-60"
    >{direction === 'asc' ? '▲' : direction === 'desc' ? '▼' : '↕'}</span
  >
</button>
