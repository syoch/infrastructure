import {
  fetchWebApps,
  fetchWebApp,
  createWebApp,
  deleteWebApp,
  submitFeedback,
  refreshFeedback,
  WebApp,
  WebAppDetail,
  AppFeedback,
} from './app_portal_api.js';
import { getToken } from './control_api.js';
import { escapeHTML, safeURL } from './ui.js';

let _sseUnsub: (() => void) | null = null;

function requireToken(): boolean {
  if (getToken()) return true;
  window.location.hash = '#/control';
  return false;
}

export async function initAppsSection(): Promise<void> {
  const view = document.getElementById('apps-view');
  if (!view) return;
  if (!requireToken()) return;

  view.innerHTML = `
    <section class="control-section">
      <header class="control-section-header">
        <h2>アプリ</h2>
        <button class="btn btn-primary" id="app-register-toggle">アプリを登録</button>
      </header>
      <div id="app-register-form-container"></div>
      <div id="apps-list"></div>
    </section>
  `;
  const toggle = document.getElementById('app-register-toggle');
  if (toggle) toggle.addEventListener('click', () => toggleRegisterForm());
  await refreshApps();
}

export async function initAppDetailSection(slug: string): Promise<void> {
  const view = document.getElementById('apps-view');
  if (!view) return;
  if (!requireToken()) return;

  view.innerHTML = `<section class="control-section"><p>Loading…</p></section>`;
  try {
    const app = await fetchWebApp(slug);
    renderAppDetail(view, app);
  } catch (e) {
    view.innerHTML = `<section class="control-section"><a href="#/apps">&larr; アプリ一覧</a>
      <p style="color:#ff5252;">Error: ${escapeHTML(e instanceof Error ? e.message : String(e))}</p></section>`;
  }
}

export function teardownAppsSection(): void {
  if (_sseUnsub) {
    _sseUnsub();
    _sseUnsub = null;
  }
  const view = document.getElementById('apps-view');
  if (view) view.innerHTML = '';
}

async function refreshApps(): Promise<void> {
  const el = document.getElementById('apps-list');
  if (!el) return;
  try {
    const apps = await fetchWebApps();
    renderAppsList(el, apps);
  } catch (e) {
    el.innerHTML = `<p style="color: #ff5252;">Error: ${escapeHTML(e instanceof Error ? e.message : String(e))}</p>`;
  }
}

function renderAppsList(el: HTMLElement, apps: WebApp[]): void {
  el.innerHTML = '';
  if (!apps.length) {
    el.innerHTML = `<p style="color: #888;">登録されたアプリはありません。</p>`;
    return;
  }
  const grid = document.createElement('div');
  grid.style.display = 'grid';
  grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(300px, 1fr))';
  grid.style.gap = '16px';
  for (const app of apps) {
    const card = document.createElement('div');
    card.className = 'provider-card';
    card.style.cursor = 'pointer';
    const tags = (app.tags || []).map((t) => `<span class="category-tag tag-none">${escapeHTML(t)}</span>`).join(' ');
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
        <h3 style="margin:0;">${escapeHTML(app.name)}</h3>
        <span style="font-size:0.75em; color:#888;">${escapeHTML(app.status)}</span>
      </div>
      <p style="color:#aaa; font-size:0.85em; margin:8px 0;">${escapeHTML(app.description || '')}</p>
      <div style="display:flex; flex-wrap:wrap; gap:4px; margin-bottom:8px;">${tags}</div>
      <div style="font-size:0.75em; color:#888; word-break:break-all;">${escapeHTML(app.project_directory)}</div>
    `;
    card.addEventListener('click', () => {
      window.location.hash = `#/apps/${encodeURIComponent(app.slug)}`;
    });
    grid.appendChild(card);
  }
  el.appendChild(grid);
}

function toggleRegisterForm(): void {
  const container = document.getElementById('app-register-form-container');
  if (!container) return;
  if (container.childElementCount) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = `
    <form id="app-register-form" class="control-form" style="margin-bottom:24px;">
      <div class="form-group"><label>アプリ名 *</label><input name="name" required></div>
      <div class="form-group"><label>説明</label><input name="description"></div>
      <div class="form-group"><label>公開 URL</label><input name="url" placeholder="http://..."></div>
      <div class="form-group"><label>プロジェクトディレクトリ *</label><input name="project_directory" placeholder="/home/syoch/work/..." required></div>
      <div class="form-group"><label>OpenCode セッション ID *</label><input name="opencode_session_id" placeholder="ses_..." required></div>
      <div class="form-group"><label>タグ (カンマ区切り)</label><input name="tags"></div>
      <div class="form-actions"><button type="submit" class="btn btn-primary">登録</button></div>
    </form>
  `;
  const form = document.getElementById('app-register-form') as HTMLFormElement | null;
  if (!form) return;
  form.addEventListener('submit', async (e: Event) => {
    e.preventDefault();
    const fd = new FormData(form);
    const tags = String(fd.get('tags') || '')
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    try {
      await createWebApp({
        name: String(fd.get('name') || ''),
        description: String(fd.get('description') || '') || undefined,
        url: String(fd.get('url') || '') || undefined,
        project_directory: String(fd.get('project_directory') || ''),
        opencode_session_id: String(fd.get('opencode_session_id') || ''),
        tags,
      });
      form.reset();
      container.innerHTML = '';
      await refreshApps();
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  });
}

function renderAppDetail(view: HTMLElement, app: WebAppDetail): void {
  const webuiLink = app.webui_url
    ? `<a class="btn btn-secondary" href="${safeURL(app.webui_url)}" target="_blank" rel="noopener">セッションを開く</a>`
    : `<span style="color:#888; font-size:0.85em;">セッションリンク未登録 (bridge 未接続)</span>`;

  view.innerHTML = `
    <section class="control-section">
      <a href="#/apps" style="font-size:0.85em;">&larr; アプリ一覧</a>
      <header class="control-section-header" style="margin-top:8px;">
        <h2>${escapeHTML(app.name)}</h2>
        <div style="display:flex; gap:8px;">
          ${webuiLink}
          <button class="btn btn-secondary" id="app-delete-btn" style="color:#ff5252;">削除</button>
        </div>
      </header>
      <div style="display:flex; flex-direction:column; gap:4px; font-size:0.85em; color:#aaa;">
        <div>slug: <code>${escapeHTML(app.slug)}</code></div>
        ${app.url ? `<div>URL: <a href="${safeURL(app.url)}" target="_blank" rel="noopener">${escapeHTML(app.url)}</a></div>` : ''}
        <div>directory: <code>${escapeHTML(app.project_directory)}</code></div>
        <div>session: <code>${escapeHTML(app.opencode_session_id)}</code></div>
        <div>bridge: <code>${escapeHTML(app.bridge_device_id)}</code></div>
      </div>
    </section>

    <section class="control-section" style="margin-top:32px;">
      <header class="control-section-header"><h2>フィードバックを送信</h2></header>
      <form id="feedback-form" class="control-form">
        <div class="form-group">
          <label>種別</label>
          <select name="kind">
            <option value="feedback">フィードバック</option>
            <option value="bug">不具合</option>
            <option value="feature">要望</option>
            <option value="question">質問</option>
          </select>
        </div>
        <div class="form-group">
          <label>内容 *</label>
          <textarea name="body" rows="5" required placeholder="気づいた点や要望を書いてください"></textarea>
        </div>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary">送信 (エージェントに注入)</button>
          ${app.webui_url ? `<a class="btn btn-secondary" href="${safeURL(app.webui_url)}" target="_blank" rel="noopener">セッションを開くだけ</a>` : ''}
        </div>
      </form>
    </section>

    <section class="control-section" style="margin-top:32px;">
      <header class="control-section-header"><h2>フィードバック履歴</h2></header>
      <div id="feedback-history"></div>
    </section>
  `;

  const delBtn = document.getElementById('app-delete-btn');
  if (delBtn) {
    delBtn.addEventListener('click', async () => {
      if (!confirm(`アプリ ${app.slug} を削除しますか?`)) return;
      try {
        await deleteWebApp(app.slug);
        window.location.hash = '#/apps';
      } catch (err) {
        alert(err instanceof Error ? err.message : String(err));
      }
    });
  }

  const form = document.getElementById('feedback-form') as HTMLFormElement | null;
  if (form) {
    form.addEventListener('submit', async (e: Event) => {
      e.preventDefault();
      const fd = new FormData(form);
      const submitBtn = form.querySelector('button[type="submit"]') as HTMLButtonElement | null;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = '送信中…';
      }
      try {
        await submitFeedback(app.slug, {
          body: String(fd.get('body') || ''),
          kind: String(fd.get('kind') || 'feedback'),
        });
        form.reset();
        const refreshed = await fetchWebApp(app.slug);
        renderFeedbackHistory(refreshed.feedback);
      } catch (err) {
        alert(err instanceof Error ? err.message : String(err));
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = '送信 (エージェントに注入)';
        }
      }
    });
  }

  renderFeedbackHistory(app.feedback);
}

function renderFeedbackHistory(items: AppFeedback[]): void {
  const el = document.getElementById('feedback-history');
  if (!el) return;
  el.innerHTML = '';
  if (!items.length) {
    el.innerHTML = `<p style="color:#888;">まだフィードバックはありません。</p>`;
    return;
  }
  const table = document.createElement('table');
  table.className = 'control-table';
  table.innerHTML = `<thead><tr><th>日時</th><th>種別</th><th>状態</th><th>内容</th><th></th></tr></thead><tbody></tbody>`;
  const tbody = table.querySelector('tbody')!;
  for (const fb of items) {
    const tr = document.createElement('tr');
    const color = fb.status === 'delivered' ? '#20a020' : fb.status === 'failed' ? '#ff5252' : '#f0a020';
    tr.innerHTML = `
      <td>${escapeHTML((fb.created_at || '').replace('T', ' ').substring(0, 19))}</td>
      <td>${escapeHTML(fb.kind)}</td>
      <td><span style="color:${color};">${escapeHTML(fb.status)}</span></td>
      <td>${escapeHTML(fb.body.substring(0, 80))}</td>
      <td>${fb.webui_url ? `<a href="${safeURL(fb.webui_url)}" target="_blank" rel="noopener">開く</a>` : ''}
          ${fb.status === 'pending' ? `<button class="btn btn-secondary" data-refresh="${escapeHTML(fb.id)}">更新</button>` : ''}</td>
    `;
    tbody.appendChild(tr);
  }
  tbody.addEventListener('click', async (e: Event) => {
    const target = e.target as HTMLButtonElement;
    const id = target.dataset.refresh;
    if (!id) return;
    try {
      await refreshFeedback(id);
      const slug = window.location.hash.split('/').pop() || '';
      const app = await fetchWebApp(decodeURIComponent(slug));
      renderFeedbackHistory(app.feedback);
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  });
  el.appendChild(table);
}
