<div id="portal-view">
  <section class="mb-8 pt-16 pb-10 text-center">
    <div class="card mt-6 bg-surface-100-900 border border-surface-200-800 p-6 backdrop-blur">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="size-8 shrink-0 text-primary-500"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
        <div>
          <h3 class="h4">Obtainium 一括インポート用 JSON</h3>
          <p class="mt-1 text-sm text-surface-700-300">
            ダウンロードした JSON を Obtainium の <strong>Import / Export → Obtainium Import</strong
            > で選択すると、全アプリを一発で登録できます。
          </p>
        </div>
      </div>
      <div class="mt-4">
        <a
          href="/obtainium-export.json"
          download="obtainium-export.json"
          class="btn preset-filled-primary-500"
          id="obtainium-download-btn"
        >
          <span class="btn-text">Obtainium 用 JSON をダウンロード</span>
        </a>
      </div>
    </div>
  </section>
</div>
