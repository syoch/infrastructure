import { parseHash, buildHash } from './router.js';

export interface RouteState {
  route: string;
  sub: string;
  params: Record<string, string>;
}

export const route = $state<RouteState>({ route: '', sub: '', params: {} });

export function syncFromHash(): void {
  const p = parseHash();
  route.route = p.route;
  route.sub = p.sub;
  route.params = p.params;
}

export function navigate(hash: string): void {
  if (window.location.hash !== hash) {
    window.location.hash = hash;
  } else {
    syncFromHash();
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', syncFromHash);
  syncFromHash();
}

export { buildHash };
