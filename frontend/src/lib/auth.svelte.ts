import { fetchMe, getToken, type Device } from '../api/control_api.js';

export const auth = $state({
  me: null as Device | null,
  loaded: false,
});

let _promise: Promise<Device | null> | null = null;

export async function ensureMe(force = false): Promise<Device | null> {
  if (force) {
    auth.loaded = false;
    auth.me = null;
  }
  if (auth.loaded) return auth.me;
  if (!getToken()) {
    auth.me = null;
    auth.loaded = true;
    return null;
  }
  if (!_promise) {
    _promise = fetchMe()
      .then((m) => {
        auth.me = m;
        return m;
      })
      .catch(() => {
        auth.me = null;
        return null;
      })
      .finally(() => {
        auth.loaded = true;
        _promise = null;
      });
  }
  return _promise;
}

export function clearAuth(): void {
  auth.me = null;
  auth.loaded = true;
}
