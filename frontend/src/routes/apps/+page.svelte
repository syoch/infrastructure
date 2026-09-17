<script lang="ts">
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { createWebApp, fetchWebApps, type WebApp } from '../../api/app_portal_api.js';
  import { getToken } from '../../api/control_api.js';
  import { showCustomToast } from '../../lib/toast.ts';
  import AppRegisterForm from './AppRegisterForm.svelte';
  import AppList from './AppList.svelte';

  let apps = $state<WebApp[]>([]);
  let loading = $state(true);
  let error = $state('');
  let showRegister = $state(false);

  $effect(() => {
    untrack(() => {
      if (!getToken()) {
        void goto('/control/devices');
        return;
      }
      void load();
    });
  });

  async function load(): Promise<void> {
    loading = true;
    error = '';
    try {
      apps = await fetchWebApps();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  function openApp(a: WebApp): void {
    void goto(`/apps/${encodeURIComponent(a.slug)}`);
  }

  async function onCreate(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    const form = e.currentTarget as HTMLFormElement;
    const fd = new FormData(form);
    try {
      await createWebApp({
        name: String(fd.get('name') || ''),
        description: String(fd.get('description') || '') || undefined,
        url: String(fd.get('url') || '') || undefined,
        project_directory: String(fd.get('project_directory') || ''),
        opencode_session_id: String(fd.get('opencode_session_id') || ''),
        tags: String(fd.get('tags') || '')
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
      });
      form.reset();
      showRegister = false;
      apps = await fetchWebApps();
    } catch (err) {
      showCustomToast(err instanceof Error ? err.message : String(err), 'error');
    }
  }
</script>

<div id="apps-view">
  {#if loading}
    <section class="card bg-surface-100-900 p-6">
      <p class="text-surface-700-300">Loading…</p>
    </section>
  {:else if error}
    <section class="card bg-surface-100-900 p-6">
      <p class="text-error-500">Error: {error}</p>
    </section>
  {:else}
    <section class="card bg-surface-100-900 p-6">
      <header class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 class="h3 m-0">アプリ</h2>
        <button class="btn preset-filled-primary-500" id="app-register-toggle" onclick={() => (showRegister = !showRegister)}>アプリを登録</button>
      </header>
      <div id="app-register-form-container">
        {#if showRegister}
          <AppRegisterForm onsubmit={onCreate} />
        {/if}
      </div>
      <AppList {apps} onOpen={openApp} />
    </section>
  {/if}
</div>
