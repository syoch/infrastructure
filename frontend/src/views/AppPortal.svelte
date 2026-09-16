<script lang="ts">
  import { untrack } from 'svelte';
  import {
    fetchWebApps,
    fetchWebApp,
    createWebApp,
    updateWebApp,
    deleteWebApp,
    submitFeedback,
    refreshFeedback,
    type WebApp,
    type WebAppDetail,
    type AppFeedback,
  } from '../api/app_portal_api.js';
  import { getToken } from '../api/control_api.js';
  import { safeURL } from '../lib/ui.js';
  import { showCustomToast } from '../lib/toast.ts';
  import { confirmDialog } from '../lib/dialogs.svelte.ts';
  import { goto } from '$app/navigation';

  let { slug = '' }: { slug?: string } = $props();

  let apps = $state<WebApp[]>([]);
  let app = $state<WebAppDetail | null>(null);
  let loading = $state(true);
  let error = $state('');
  let showRegister = $state(false);
  let message = $state('');
  let saving = $state(false);
  let feedbackSending = $state(false);

  // Re-run when the route's slug changes (the component instance is reused
  // between #/apps and #/apps/{slug}).
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
      if (s) {
        app = await fetchWebApp(s);
      } else {
        apps = await fetchWebApps();
      }
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

  function statusClass(status: string): string {
    return status === 'delivered'
      ? 'preset-filled-success-500'
      : status === 'failed'
        ? 'preset-filled-error-500'
        : 'preset-filled-warning-500';
  }

  function fmt(dt: string | null | undefined): string {
    return (dt || '').replace('T', ' ').substring(0, 19);
  }

  function feedbacks(a: WebAppDetail | null): AppFeedback[] {
    return a?.feedback ?? [];
  }
</script>

{#if loading}
  <section class="card bg-surface-100-900 p-6">
    <p class="text-surface-700-300">Loading…</p>
  </section>
{:else if error}
  <section class="card bg-surface-100-900 p-6">
    <p class="text-error-500">Error: {error}</p>
  </section>
{:else if slug}
  {#if app}
    <div class="flex flex-col gap-6">
      <section class="card bg-surface-100-900 p-6">
        <a class="anchor text-sm" href="#/apps">&larr; アプリ一覧</a>
        <header class="mt-2 flex flex-wrap items-center justify-between gap-3">
          <h2 class="h3 m-0">{app.name}</h2>
          <div class="flex flex-wrap items-center gap-2">
            {#if app.webui_url}
              <a class="btn preset-tonal" href={safeURL(app.webui_url)} target="_blank" rel="noopener">セッションを開く</a>
            {:else}
              <span class="text-xs text-surface-600-400">セッションリンク未登録 (bridge 未接続)</span>
            {/if}
            <button class="btn preset-tonal text-error-500" id="app-delete-btn" onclick={onDelete}>削除</button>
          </div>
        </header>
        <div class="mt-4 flex flex-col gap-1 text-xs text-surface-600-400">
          <div>slug: <code>{app.slug}</code></div>
          {#if app.url}
            <div>URL: <a class="anchor" href={safeURL(app.url)} target="_blank" rel="noopener">{app.url}</a></div>
          {/if}
          <div>directory: <code>{app.project_directory}</code></div>
          <div>session: <code>{app.opencode_session_id}</code></div>
          <div>bridge: <code>{app.bridge_device_id}</code></div>
        </div>
      </section>

      <section class="card bg-surface-100-900 p-6">
        <header class="mb-4"><h2 class="h4 m-0">設定</h2></header>
        {#if message}<p class="mb-2 text-sm text-success-500">{message}</p>{/if}
        <form id="app-edit-form" class="grid gap-4 sm:grid-cols-2" onsubmit={onSave}>
          <label class="label">
            <span class="label-text">アプリ名 *</span>
            <input id="ef-name" name="name" class="input" required value={app.name}>
          </label>
          <label class="label">
            <span class="label-text">説明</span>
            <input id="ef-description" name="description" class="input" value={app.description || ''}>
          </label>
          <label class="label">
            <span class="label-text">公開 URL</span>
            <input id="ef-url" name="url" class="input" value={app.url || ''}>
          </label>
          <label class="label">
            <span class="label-text">プロジェクトディレクトリ *</span>
            <input id="ef-dir" name="project_directory" class="input" required value={app.project_directory}>
          </label>
          <label class="label">
            <span class="label-text">OpenCode セッション ID *</span>
            <input id="ef-session" name="opencode_session_id" class="input" required value={app.opencode_session_id}>
          </label>
          <label class="label">
            <span class="label-text">bridge device id *</span>
            <input id="ef-bridge" name="bridge_device_id" class="input" required value={app.bridge_device_id}>
          </label>
          <label class="label">
            <span class="label-text">タグ (カンマ区切り)</span>
            <input id="ef-tags" name="tags" class="input" value={(app.tags || []).join(', ')}>
          </label>
          <label class="label">
            <span class="label-text">ステータス</span>
            <select id="ef-status" name="status" class="select">
              <option value="active" selected={app.status === 'active'}>active</option>
              <option value="archived" selected={app.status === 'archived'}>archived</option>
            </select>
          </label>
          <div class="sm:col-span-2">
            <button type="submit" class="btn preset-filled-primary-500" disabled={saving}>
              {saving ? '保存中…' : '設定を保存'}
            </button>
          </div>
        </form>
      </section>

      <section class="card bg-surface-100-900 p-6">
        <header class="mb-4"><h2 class="h4 m-0">フィードバックを送信</h2></header>
        <form id="feedback-form" class="grid gap-4" onsubmit={onFeedback}>
          <label class="label">
            <span class="label-text">種別</span>
            <select id="fb-kind" name="kind" class="select">
              <option value="feedback">フィードバック</option>
              <option value="bug">不具合</option>
              <option value="feature">要望</option>
              <option value="question">質問</option>
            </select>
          </label>
          <label class="label">
            <span class="label-text">内容 *</span>
            <textarea id="fb-body" name="body" class="textarea" rows="5" required placeholder="気づいた点や要望を書いてください"></textarea>
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <button type="submit" class="btn preset-filled-primary-500" disabled={feedbackSending}>
              {feedbackSending ? '送信中…' : '送信 (エージェントに注入)'}
            </button>
            {#if app.webui_url}
              <a class="btn preset-tonal" href={safeURL(app.webui_url)} target="_blank" rel="noopener">セッションを開くだけ</a>
            {/if}
          </div>
        </form>
      </section>

      <section class="card bg-surface-100-900 p-6">
        <header class="mb-4"><h2 class="h4 m-0">フィードバック履歴</h2></header>
        <div id="feedback-history" class="table-wrap">
          {#if feedbacks(app).length === 0}
            <p class="text-surface-600-400">まだフィードバックはありません。</p>
          {:else}
            <table class="table">
              <thead><tr><th>日時</th><th>種別</th><th>状態</th><th>内容</th><th></th></tr></thead>
              <tbody>
                {#each feedbacks(app) as fb (fb.id)}
                  <tr>
                    <td>{fmt(fb.created_at)}</td>
                    <td>{fb.kind}</td>
                    <td><span class="badge {statusClass(fb.status)}">{fb.status}</span></td>
                    <td>{fb.body.substring(0, 80)}</td>
                    <td class="whitespace-nowrap">
                      {#if fb.webui_url}
                        <a class="anchor" href={safeURL(fb.webui_url)} target="_blank" rel="noopener">開く</a>
                      {/if}
                      {#if fb.status === 'pending'}
                        <button class="btn btn-sm preset-tonal" onclick={() => onRefreshFeedback(fb.id)}>更新</button>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
      </section>
    </div>
  {/if}
{:else}
  <section class="card bg-surface-100-900 p-6">
    <header class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h2 class="h3 m-0">アプリ</h2>
      <button class="btn preset-filled-primary-500" id="app-register-toggle" onclick={() => (showRegister = !showRegister)}>アプリを登録</button>
    </header>
    <div id="app-register-form-container">
      {#if showRegister}
        <form id="app-register-form" class="card mb-6 grid gap-4 bg-surface-50-950 p-4 sm:grid-cols-2" onsubmit={onCreate}>
          <label class="label">
            <span class="label-text">アプリ名 *</span>
            <input id="rg-name" name="name" class="input" required>
          </label>
          <label class="label">
            <span class="label-text">説明</span>
            <input id="rg-description" name="description" class="input">
          </label>
          <label class="label">
            <span class="label-text">公開 URL</span>
            <input id="rg-url" name="url" class="input" placeholder="http://...">
          </label>
          <label class="label">
            <span class="label-text">プロジェクトディレクトリ *</span>
            <input id="rg-dir" name="project_directory" class="input" placeholder="/home/syoch/work/..." required>
          </label>
          <label class="label">
            <span class="label-text">OpenCode セッション ID *</span>
            <input id="rg-session" name="opencode_session_id" class="input" placeholder="ses_..." required>
          </label>
          <label class="label">
            <span class="label-text">タグ (カンマ区切り)</span>
            <input id="rg-tags" name="tags" class="input">
          </label>
          <div class="sm:col-span-2">
            <button type="submit" class="btn preset-filled-primary-500">登録</button>
          </div>
        </form>
      {/if}
    </div>
    <div id="apps-list">
      {#if apps.length === 0}
        <p class="text-surface-600-400">登録されたアプリはありません。</p>
      {:else}
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {#each apps as a (a.id)}
            <div
              class="card cursor-pointer bg-surface-50-950 p-4 transition hover:brightness-105"
              role="button"
              tabindex="0"
              data-testid="app-card"
              onclick={() => openApp(a)}
              onkeydown={(e) => e.key === 'Enter' && openApp(a)}
            >
              <div class="flex items-start justify-between gap-2">
                <h3 class="h5 m-0">{a.name}</h3>
                <span class="badge preset-tonal-surface">{a.status}</span>
              </div>
              <p class="my-2 text-sm text-surface-700-300">{a.description || ''}</p>
              <div class="mb-2 flex flex-wrap gap-1">
                {#each a.tags || [] as t}<span class="chip preset-tonal">{t}</span>{/each}
              </div>
              <div class="text-xs break-all text-surface-600-400">{a.project_directory}</div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </section>
{/if}
