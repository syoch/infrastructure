import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    // Static SPA served by the FastAPI backend (which returns index.html for
    // unknown non-API paths). Output stays in dist/ so PUBLIC_DIR and the
    // portal packaging are unchanged.
    adapter: adapter({
      pages: 'dist',
      assets: 'dist',
      fallback: 'index.html',
      strict: false,
    }),
    alias: {
      $lib: './src/lib',
    },
  },
};

export default config;
