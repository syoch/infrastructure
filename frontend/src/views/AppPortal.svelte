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
  import { goto } from '$app/navigation';

  let { slug = '' }: { slug?: string } = $props();

  let apps = $state<WebApp[]>([]);
  let app = $state<WebAppDetail | null>(null);
  let loading = $state(true);
  let error = $state('');
  let showRegister = $state(false);
  let message = $state('');

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
      alert(err instanceof Error ? err.message : String(err));
    }
  }

  async function onSave(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    if (!app) return;
    const form = e.currentTarget as HTMLFormElement;
    const fd = new FormData(form);
    const btn = form.querySelector('button[type="submit"]') as HTMLButtonElement | null;
    if (btn) {
      btn.disabled = true;
      btn.textContent = '保存中…';
    }
    try {
      await updateWebApp(app.slug, {
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
      app = await fetchWebApp(app.slug);
      message = '設定を保存しました';
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '設定を保存';
      }
    }
  }

  async function onDelete(): Promise<void> {
    if (!app) return;
    if (!confirm(`アプリ ${app.slug} を削除しますか?`)) return;
    try {
      await deleteWebApp(app.slug);
      void goto('/apps');
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  }

  async function onFeedback(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    if (!app) return;
    const form = e.currentTarget as HTMLFormElement;
    const fd = new FormData(form);
    const btn = form.querySelector('button[type="submit"]') as HTMLButtonElement | null;
    if (btn) {
      btn.disabled = true;
      btn.textContent = '送信中…';
    }
    try {
      await submitFeedback(app.slug, {
        body: String(fd.get('body') || ''),
        kind: String(fd.get('kind') || 'feedback'),
      });
      form.reset();
      app = await fetchWebApp(app.slug);
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '送信 (エージェントに注入)';
      }
    }
  }

  async function onRefreshFeedback(id: string): Promise<void> {
    if (!app) return;
    try {
      await refreshFeedback(id);
      app = await fetchWebApp(app.slug);
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  }

  function statusColor(status: string): string {
    return status === 'delivered' ? '#20a020' : status === 'failed' ? '#ff5252' : '#f0a020';
  }

  function fmt(dt: string | null | undefined): string {
    return (dt || '').replace('T', ' ').substring(0, 19);
  }

  function feedbacks(a: WebAppDetail | null): AppFeedback[] {
    return a?.feedback ?? [];
  }
</script>

{#if loading}
  <section class="control-section"><p>Loading…</p></section>
{:else if error}
  <section class="control-section"><p style="color:#ff5252;">Error: {error}</p></section>
{:else if slug}
  {#if app}
    <section class="control-section">
      <a href="#/apps" style="font-size:0.85em;">&larr; アプリ一覧</a>
      <header class="control-section-header" style="margin-top:8px;">
        <h2>{app.name}</h2>
        <div style="display:flex; gap:8px;">
          {#if app.webui_url}
            <a class="btn btn-secondary" href={safeURL(app.webui_url)} target="_blank" rel="noopener">セッションを開く</a>
          {:else}
            <span style="color:#888; font-size:0.85em;">セッションリンク未登録 (bridge 未接続)</span>
          {/if}
          <button class="btn btn-secondary" id="app-delete-btn" style="color:#ff5252;" onclick={onDelete}>削除</button>
        </div>
      </header>
      <div style="display:flex; flex-direction:column; gap:4px; font-size:0.85em; color:#aaa;">
        <div>slug: <code>{app.slug}</code></div>
        {#if app.url}
          <div>URL: <a href={safeURL(app.url)} target="_blank" rel="noopener">{app.url}</a></div>
        {/if}
        <div>directory: <code>{app.project_directory}</code></div>
        <div>session: <code>{app.opencode_session_id}</code></div>
        <div>bridge: <code>{app.bridge_device_id}</code></div>
      </div>
    </section>

    <section class="control-section" style="margin-top:32px;">
      <header class="control-section-header"><h2>設定</h2></header>
      {#if message}<p style="color:#20a020; font-size:0.85em;">{message}</p>{/if}
      <form id="app-edit-form" class="control-form" onsubmit={onSave}>
        <div class="form-group"><label for="ef-name">アプリ名 *</label><input id="ef-name" name="name" required value={app.name}></div>
        <div class="form-group"><label for="ef-description">説明</label><input id="ef-description" name="description" value={app.description || ''}></div>
        <div class="form-group"><label for="ef-url">公開 URL</label><input id="ef-url" name="url" value={app.url || ''}></div>
        <div class="form-group"><label for="ef-dir">プロジェクトディレクトリ *</label><input id="ef-dir" name="project_directory" required value={app.project_directory}></div>
        <div class="form-group"><label for="ef-session">OpenCode セッション ID *</label><input id="ef-session" name="opencode_session_id" required value={app.opencode_session_id}></div>
        <div class="form-group"><label for="ef-bridge">bridge device id *</label><input id="ef-bridge" name="bridge_device_id" required value={app.bridge_device_id}></div>
        <div class="form-group"><label for="ef-tags">タグ (カンマ区切り)</label><input id="ef-tags" name="tags" value={(app.tags || []).join(', ')}></div>
        <div class="form-group">
          <label for="ef-status">ステータス</label>
          <select id="ef-status" name="status">
            <option value="active" selected={app.status === 'active'}>active</option>
            <option value="archived" selected={app.status === 'archived'}>archived</option>
          </select>
        </div>
        <div class="form-actions"><button type="submit" class="btn btn-primary">設定を保存</button></div>
      </form>
    </section>

    <section class="control-section" style="margin-top:32px;">
      <header class="control-section-header"><h2>フィードバックを送信</h2></header>
      <form id="feedback-form" class="control-form" onsubmit={onFeedback}>
        <div class="form-group">
          <label for="fb-kind">種別</label>
          <select id="fb-kind" name="kind">
            <option value="feedback">フィードバック</option>
            <option value="bug">不具合</option>
            <option value="feature">要望</option>
            <option value="question">質問</option>
          </select>
        </div>
        <div class="form-group">
          <label for="fb-body">内容 *</label>
          <textarea id="fb-body" name="body" rows="5" required placeholder="気づいた点や要望を書いてください"></textarea>
        </div>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary">送信 (エージェントに注入)</button>
          {#if app.webui_url}
            <a class="btn btn-secondary" href={safeURL(app.webui_url)} target="_blank" rel="noopener">セッションを開くだけ</a>
          {/if}
        </div>
      </form>
    </section>

    <section class="control-section" style="margin-top:32px;">
      <header class="control-section-header"><h2>フィードバック履歴</h2></header>
      <div id="feedback-history">
        {#if feedbacks(app).length === 0}
          <p style="color:#888;">まだフィードバックはありません。</p>
        {:else}
          <table class="control-table">
            <thead><tr><th>日時</th><th>種別</th><th>状態</th><th>内容</th><th></th></tr></thead>
            <tbody>
              {#each feedbacks(app) as fb (fb.id)}
                <tr>
                  <td>{fmt(fb.created_at)}</td>
                  <td>{fb.kind}</td>
                  <td><span style="color:{statusColor(fb.status)};">{fb.status}</span></td>
                  <td>{fb.body.substring(0, 80)}</td>
                  <td>
                    {#if fb.webui_url}
                      <a href={safeURL(fb.webui_url)} target="_blank" rel="noopener">開く</a>
                    {/if}
                    {#if fb.status === 'pending'}
                      <button class="btn btn-secondary" onclick={() => onRefreshFeedback(fb.id)}>更新</button>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </section>
  {/if}
{:else}
  <section class="control-section">
    <header class="control-section-header">
      <h2>アプリ</h2>
      <button class="btn btn-primary" id="app-register-toggle" onclick={() => (showRegister = !showRegister)}>アプリを登録</button>
    </header>
    <div id="app-register-form-container">
      {#if showRegister}
        <form id="app-register-form" class="control-form" style="margin-bottom:24px;" onsubmit={onCreate}>
          <div class="form-group"><label for="rg-name">アプリ名 *</label><input id="rg-name" name="name" required></div>
          <div class="form-group"><label for="rg-description">説明</label><input id="rg-description" name="description"></div>
          <div class="form-group"><label for="rg-url">公開 URL</label><input id="rg-url" name="url" placeholder="http://..."></div>
          <div class="form-group"><label for="rg-dir">プロジェクトディレクトリ *</label><input id="rg-dir" name="project_directory" placeholder="/home/syoch/work/..." required></div>
          <div class="form-group"><label for="rg-session">OpenCode セッション ID *</label><input id="rg-session" name="opencode_session_id" placeholder="ses_..." required></div>
          <div class="form-group"><label for="rg-tags">タグ (カンマ区切り)</label><input id="rg-tags" name="tags"></div>
          <div class="form-actions"><button type="submit" class="btn btn-primary">登録</button></div>
        </form>
      {/if}
    </div>
    <div id="apps-list">
      {#if apps.length === 0}
        <p style="color:#888;">登録されたアプリはありません。</p>
      {:else}
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:16px;">
          {#each apps as a (a.id)}
            <div class="provider-card" style="cursor:pointer;" role="button" tabindex="0"
                 onclick={() => openApp(a)} onkeydown={(e) => e.key === 'Enter' && openApp(a)}>
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <h3 style="margin:0;">{a.name}</h3>
                <span style="font-size:0.75em; color:#888;">{a.status}</span>
              </div>
              <p style="color:#aaa; font-size:0.85em; margin:8px 0;">{a.description || ''}</p>
              <div style="display:flex; flex-wrap:wrap; gap:4px; margin-bottom:8px;">
                {#each a.tags || [] as t}<span class="category-tag tag-none">{t}</span>{/each}
              </div>
              <div style="font-size:0.75em; color:#888; word-break:break-all;">{a.project_directory}</div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </section>
{/if}
