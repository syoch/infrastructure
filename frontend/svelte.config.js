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
    // SvelteKit injects a small inline bootstrap script; emit a Content-Security
    // -Policy with the hash it needs so a strict `script-src 'self'` works.
    // The nginx vhost must NOT also set a CSP header (two policies intersect).
    csp: {
      mode: 'hash',
      directives: {
        'default-src': ['self'],
        'script-src': ['self'],
        'style-src': ['self', 'unsafe-inline', 'https://fonts.googleapis.com'],
        'img-src': ['self', 'data:'],
        'font-src': ['self', 'data:', 'https://fonts.gstatic.com'],
        'connect-src': ['self'],
        'base-uri': ['self'],
        'form-action': ['self'],
        'object-src': ['none'],
      },
    },
  },
};

export default config;
