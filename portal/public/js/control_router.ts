import { fetchMe, getToken, Device } from './control_api.js';
import { initBootstrap, teardownBootstrap } from './control_bootstrap.js';
import { initDevicesSection, teardownDevicesSection } from './control_devices.js';
import { initAclSection, teardownAclSection } from './control_acl.js';
import { escapeHTML } from './ui.js';

type SubRoute = 'bootstrap' | 'devices' | 'acl' | 'error' | null;

let _currentSub: SubRoute = null;
let _me: Device | null = null;

export async function initControlSubroute(sub: string): Promise<void> {
  teardownAll();
  if (!getToken()) {
    await initBootstrap();
    _currentSub = 'bootstrap';
    return;
  }
  try {
    _me = await fetchMe();
  } catch (e) {
    const err = e as Error & { status?: number };
    if (err.status === 401) {
      await initBootstrap();
      _currentSub = 'bootstrap';
      return;
    }
    const view = document.getElementById('control-view');
    if (view) view.innerHTML = `<div class="control-error">Error: ${escapeHTML(err.message)}</div>`;
    _currentSub = 'error';
    return;
  }

  const target = sub || 'devices';
  if (target === 'acl') {
    await initAclSection(_me);
    _currentSub = 'acl';
  } else {
    await initDevicesSection(_me);
    _currentSub = 'devices';
  }
}

export function teardownControlSubroute(): void {
  teardownAll();
}

function teardownAll(): void {
  if (_currentSub === 'bootstrap') teardownBootstrap();
  else if (_currentSub === 'devices') teardownDevicesSection();
  else if (_currentSub === 'acl') teardownAclSection();
  _currentSub = null;
}

export function getCurrentControlSub(): SubRoute {
  return _currentSub;
}