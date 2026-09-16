import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  // Files under public-static/ are copied verbatim into the build output
  // (e.g. the schema renderer test harness).
  publicDir: 'public-static',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: false,
    rollupOptions: {
      preserveEntrySignatures: 'strict',
      // The schema renderer/editor are also exposed as a stable, un-hashed
      // entry point so the standalone test harness
      // (/test_schema_renderer.html) can import them directly.
      input: {
        index: 'index.html',
        'js/schema_api': 'src/entries/schema_api.ts',
      },
      output: {
        entryFileNames: (chunk) =>
          chunk.name === 'index' ? 'assets/[name]-[hash].js' : '[name].js',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/obtainium-export.json': 'http://localhost:8000',
      '/scrape-index.html': 'http://localhost:8000',
    },
  },
});
