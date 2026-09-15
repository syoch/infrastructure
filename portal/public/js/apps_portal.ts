import { mount, unmount } from 'svelte';
import AppPortal from '../src/apps/AppPortal.svelte';

// The App Portal view is implemented in Svelte (src/apps/AppPortal.svelte) and
// mounted into the legacy #apps-view container. This keeps the existing vanilla
// shell/router working while migrating views one at a time.

let _instance: ReturnType<typeof mount> | null = null;

function mountView(props: { slug?: string }): void {
  const target = document.getElementById('apps-view');
  if (!target) return;
  teardownAppsSection();
  _instance = mount(AppPortal, { target, props });
}

export function initAppsSection(): void {
  mountView({ slug: '' });
}

export function initAppDetailSection(slug: string): void {
  mountView({ slug });
}

export function teardownAppsSection(): void {
  if (_instance) {
    unmount(_instance);
    _instance = null;
  }
}
