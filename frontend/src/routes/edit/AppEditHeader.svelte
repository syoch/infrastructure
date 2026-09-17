<script lang="ts">
  import { goto as navigate } from '$app/navigation';
</script>

<section class="dashboard-header-section mb-6">
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <h1 id="edit-view-title" class="h2">アプリ詳細設定</h1>
      <p class="mt-1 text-sm text-surface-700-300">
        アプリの詳細なスクレイピング条件やインストール時の挙動をカスタマイズします。
      </p>
    </div>
    <button id="edit-back-btn" class="btn preset-tonal" onclick={() => navigate('/list')}>
      <span>← 一覧に戻る</span>
    </button>
  </div>
</section>
