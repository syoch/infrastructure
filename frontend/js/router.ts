export interface ParsedHash {
  route: string;
  sub: string;
  params: Record<string, string>;
}

export function parseHash(): ParsedHash {
  const hash = window.location.hash || '';
  let normalized = hash;
  if (normalized.startsWith('#')) {
    normalized = normalized.substring(1);
  }
  if (normalized.startsWith('/')) {
    normalized = normalized.substring(1);
  }

  if (!normalized) {
    return { route: '', sub: '', params: {} };
  }

  const parts = normalized.split('?');
  const path = parts[0];
  const queryStr = parts[1] || '';

  const segments = path.split('/').filter((s) => s.length > 0);
  const route = segments[0] || '';
  const sub = segments[1] || '';

  const params: Record<string, string> = {};
  queryStr.split('&').forEach((pair) => {
    const [key, val] = pair.split('=');
    if (key) {
      params[key] = decodeURIComponent(val || '');
    }
  });

  return { route, sub, params };
}

export function buildHash(route: string, sub: string, params: Record<string, string | number | undefined | null> = {}): string {
  let h = '#';
  if (route) h += '/' + route;
  if (sub) h += '/' + sub;
  if (params && Object.keys(params).length > 0) {
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&');
    if (qs) h += '?' + qs;
  }
  return h;
}

export type RouteChangeHandler = (hash: ParsedHash) => void;

export function initRouter(onRouteChanged: RouteChangeHandler): void {
  window.addEventListener('hashchange', () => {
    onRouteChanged(parseHash());
  });
  onRouteChanged(parseHash());
}