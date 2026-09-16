import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';

// The dev server proxies API calls to a portal backend. Point it at a local
// server (default) or a real deployment:
//   PORTAL_API_BASE=https://portal.syoch.org npm run dev
// Can also be set in frontend/.env (see .env.example).
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env };
  const apiBase = env.PORTAL_API_BASE || 'http://localhost:8000';
  const insecure = env.PORTAL_API_INSECURE === '1' || env.PORTAL_API_INSECURE === 'true';

  // Optional Cloudflare Access service token (needed when the target is a
  // Cloudflare Access protected deployment and the browser has no session
  // cookie for it).
  const accessHeaders: Record<string, string> = {};
  if (env.PORTAL_API_ACCESS_CLIENT_ID && env.PORTAL_API_ACCESS_CLIENT_SECRET) {
    accessHeaders['CF-Access-Client-Id'] = env.PORTAL_API_ACCESS_CLIENT_ID;
    accessHeaders['CF-Access-Client-Secret'] = env.PORTAL_API_ACCESS_CLIENT_SECRET;
  }

  const proxyOptions = () => ({
    target: apiBase,
    changeOrigin: true,
    secure: !insecure,
    headers: accessHeaders,
  });

  return {
    plugins: [tailwindcss(), sveltekit()],
    server: {
      port: 5173,
      proxy: {
        '/api': proxyOptions(),
        '/obtainium-export.json': proxyOptions(),
        '/scrape-index.html': proxyOptions(),
      },
    },
  };
});
