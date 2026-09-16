<script lang="ts">
  import { Pagination } from '@skeletonlabs/skeleton-svelte';

  let {
    total,
    limit,
    page,
    pageFrom,
    pageTo,
    onPageChange,
  }: {
    total: number;
    limit: number;
    page: number;
    pageFrom: number;
    pageTo: number;
    onPageChange: (details: { page: number }) => void;
  } = $props();
</script>

<div class="mt-4 flex flex-wrap items-center gap-4">
  <span class="text-sm text-surface-600-400">Showing {pageFrom}-{pageTo} of {total}</span>
  <Pagination
    count={total}
    pageSize={limit}
    page={page}
    onPageChange={(details) => onPageChange(details)}
  >
    <Pagination.PrevTrigger id="cmds-page-prev">前へ</Pagination.PrevTrigger>
    <Pagination.NextTrigger id="cmds-page-next">次へ</Pagination.NextTrigger>
  </Pagination>
</div>
