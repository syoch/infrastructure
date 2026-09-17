<script lang="ts">
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import {
    deleteWebApp,
    fetchWebApp,
    refreshFeedback,
    submitFeedback,
    updateWebApp,
    type WebAppDetail,
  } from '../../../api/app_portal_api.js';
  import { getToken } from '../../../api/control_api.js';
  import { showCustomToast } from '../../../lib/toast.ts';
  import { confirmDialog } from '../../../lib/dialogs.svelte.ts';
  import AppDetailHeader from './AppDetailHeader.svelte';
  import AppEditForm from './AppEditForm.svelte';
  import FeedbackForm from './FeedbackForm.svelte';
  import FeedbackHistory from './FeedbackHistory.svelte';

  const slug = $derived(page.params.slug ?? '');

  let app = $state<WebAppDetail | null>(null);
  let loading = $state(true);
  let error = $state('');
  let message = $state('');
  let saving = $state(false);
  let feedbackSending = $state(false);

  $effect(() => {
    const s = slug;
    untrack(() => {
      if (!getToken()) {
        void goto('/control/devices');
        return;
      }
      void load(s);
    });
  });

  async function load(s: string): Promise<void> {
    loading = true;
    error = '';
    app = null;
    try {
      app = await fetchWebApp(s);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function onSave(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    if (!app) return;
    const current = app;
    const form = e.currentTarget as HTMLFormElement;
    const fd = new FormData(form);
    saving = true;
    try {
      await updateWebApp(current.slug, {
        name: String(fd.get('name') || ''),
        description: String(fd.get('description') || ''),
        url: String(fd.get('url') || ''),
        project_directory: String(fd.get('project_directory') || ''),
        opencode_session_id: String(fd.get('opencode_session_id') || ''),
        bridge_device_id: String(fd.get('bridge_device_id') || ''),
        tags: String(fd.get('tags') || '')
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        status: String(fd.get('status') || 'active'),
      });
      app = await fetchWebApp(current.slug);
      message = '設定を保存しました';
    } catch (err) {
      showCustomToast(err instanceof Error ? err.message : String(err), 'error');
    } finally {
      saving = false;
    }
  }

  async function onDelete(): Promise<void> {
    if (!app) return;
    const confirmed = await confirmDialog({
      title: 'アプリを削除',
      message: `アプリ ${app.slug} を削除しますか?`,
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteWebApp(app.slug);
      void goto('/apps');
    } catch (err) {
      showCustomToast(err instanceof Error ? err.message : String(err), 'error');
    }
  }

  async function onFeedback(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    if (!app) return;
    const current = app;
    const form = e.currentTarget as HTMLFormElement;
    const fd = new FormData(form);
    feedbackSending = true;
    try {
      await submitFeedback(current.slug, {
        body: String(fd.get('body') || ''),
        kind: String(fd.get('kind') || 'feedback'),
      });
      form.reset();
      app = await fetchWebApp(current.slug);
    } catch (err) {
      showCustomToast(err instanceof Error ? err.message : String(err), 'error');
    } finally {
      feedbackSending = false;
    }
  }

  async function onRefreshFeedback(id: string): Promise<void> {
    if (!app) return;
    try {
      await refreshFeedback(id);
      app = await fetchWebApp(app.slug);
    } catch (err) {
      showCustomToast(err instanceof Error ? err.message : String(err), 'error');
    }
  }
</script>

<div id="apps-view">
  {#if loading}
    <section class="card bg-surface-100-900 p-6" aria-busy="true">
      <span class="sr-only">Loading…</span>
      <div class="placeholder mb-4 h-6 w-40"></div>
      <div class="placeholder mb-2 h-4 w-full"></div>
      <div class="placeholder mb-2 h-4 w-5/6"></div>
      <div class="placeholder h-4 w-2/3"></div>
    </section>
  {:else if error}
    <section class="card bg-surface-100-900 p-6">
      <p class="preset-tonal-error rounded-base p-4 text-sm">Error: {error}</p>
    </section>
  {:else if app}
    <div class="flex flex-col gap-6">
      <AppDetailHeader {app} onDelete={onDelete} />
      <AppEditForm {app} {saving} {message} onsubmit={onSave} />
      <FeedbackForm webui_url={app.webui_url} sending={feedbackSending} onsubmit={onFeedback} />
      <FeedbackHistory feedback={app.feedback ?? []} onRefresh={onRefreshFeedback} />
    </div>
  {/if}
</div>
