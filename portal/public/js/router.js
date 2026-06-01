export function parseHash() {
  const hash = window.location.hash || '';
  let normalized = hash;
  if (normalized.startsWith('#')) {
    normalized = normalized.substring(1);
  }
  if (normalized.startsWith('/')) {
    normalized = normalized.substring(1);
  }
  
  if (!normalized) {
    return { route: '', params: {} };
  }

  const parts = normalized.split('?');
  const route = parts[0]; // '', 'dashboard', 'new', 'edit'
  const queryStr = parts[1] || '';
  
  const params = {};
  queryStr.split('&').forEach(pair => {
    const [key, val] = pair.split('=');
    if (key) {
      params[key] = decodeURIComponent(val || '');
    }
  });

  return { route, params };
}

export function initRouter(onRouteChanged) {
  window.addEventListener('hashchange', () => {
    onRouteChanged(parseHash());
  });
  // Trigger initial routing
  onRouteChanged(parseHash());
}
