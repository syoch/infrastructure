import { fetchAcl, createAcl, deleteAcl, ACL } from './control_api.js';
import { escapeHTML } from './ui.js';

let _acls: ACL[] = [];

export async function initAclSection(me: { is_first_webui_device: boolean; id?: string }): Promise<void> {
  if (!me?.is_first_webui_device) {
    const view = document.getElementById('control-view');
    if (!view) return;
    view.innerHTML = `
      <section class="control-section">
        <header class="control-section-header"><h2>ACL</h2></header>
        <div class="control-guard">
          <p>この画面は admin 専用です。現在のデバイス <code>${escapeHTML(me?.id || '(unknown)')}</code> には admin 権限がありません。</p>
          <a href="#/control/devices" class="btn btn-primary">Devices に戻る</a>
        </div>
      </section>
    `;
    return;
  }

  const view = document.getElementById('control-view');
  if (!view) return;
  view.innerHTML = `
    <section class="control-section">
      <header class="control-section-header"><h2>ACL</h2></header>
      <form id="acl-form" class="control-form">
        <input name="source_device" placeholder="device:source-*" required pattern="^device:.+">
        <input name="target_device" placeholder="device:target-*" required pattern="^device:.+">
        <input name="operation" placeholder="op regex (e.g. .*)" required>
        <input name="extra" placeholder="extra (optional)">
        <button type="submit" class="btn btn-primary">追加</button>
      </form>
      <table class="control-table">
        <thead><tr><th>Source</th><th>Target</th><th>Op</th><th>Extra</th><th></th></tr></thead>
        <tbody id="acl-tbody"></tbody>
      </table>
    </section>
  `;
  const form = document.getElementById('acl-form') as HTMLFormElement;
  form.addEventListener('submit', async (e: SubmitEvent) => {
    e.preventDefault();
    const fd = new FormData(form);
    try {
      await createAcl({
        source_device: fd.get('source_device') as string,
        target_device: fd.get('target_device') as string,
        operation: fd.get('operation') as string,
        extra: fd.get('extra') as string || '',
      });
      form.reset();
      await refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  });
  await refresh();
}

export function teardownAclSection(): void {
  const view = document.getElementById('control-view');
  if (view) view.innerHTML = '';
}

async function refresh(): Promise<void> {
  try {
    _acls = await fetchAcl();
    render();
  } catch (e) {
    const tbody = document.getElementById('acl-tbody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="color: #ff5252;">Error: ${escapeHTML(e instanceof Error ? e.message : String(e))}</td></tr>`;
  }
}

function render(): void {
  const tbody = document.getElementById('acl-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  for (const a of _acls) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><code>${escapeHTML(a.source_device)}</code></td>
      <td><code>${escapeHTML(a.target_device)}</code></td>
      <td><code>${escapeHTML(a.operation)}</code></td>
      <td><code>${escapeHTML(a.extra || '')}</code></td>
      <td><button data-acl="${escapeHTML(a.id)}" class="btn btn-secondary" style="color: #ff5252;">削除</button></td>
    `;
    tbody.appendChild(tr);
  }
  tbody.addEventListener('click', async (e: Event) => {
    const target = e.target as HTMLButtonElement;
    if (!target.dataset.acl) return;
    if (!confirm('この ACL を削除しますか?')) return;
    try {
      await deleteAcl(target.dataset.acl);
      await refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  });
}