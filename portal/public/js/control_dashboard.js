import {
  fetchMe, fetchDevices, fetchAcl, fetchOperations, fetchCommands,
  createAcl, updateAcl, deleteAcl, issueCommand, subscribeSse,
  setAdmin, patchDevice, deleteDevice, registerDevice,
  getToken, setToken, clearToken, getDeviceId, refreshSse,
} from "./control_api.js";
import { renderOpButton, renderOpForm, renderOperationStatus } from "./control_op_renderer.js";
import { escapeHTML } from "./ui.js";

let _state = {
  me: null,
  devices: [],
  acls: [],
  ops: [],
  cmds: [],
};

let _sseUnsub = null;
let _refreshTimer = null;

export async function initControlPlane() {
  if (!getToken()) {
    showBootstrap();
    return;
  }
  try {
    _state.me = await fetchMe();
  } catch (e) {
    if (e.status === 401) {
      clearToken();
      showBootstrap();
      return;
    }
    showError(e.message);
    return;
  }
  await refreshAll();
  _sseUnsub = subscribeSse(handleSseEvent);
  startAutoRefresh();
}

function showBootstrap() {
  const view = document.getElementById("control-view");
  if (!view) return;
  view.innerHTML = `
    <section class="bootstrap-section" style="max-width: 480px; margin: 60px auto; padding: 32px; background: var(--bg-card, #1e1e2e); border-radius: 16px;">
      <h2>WebUI セットアップ</h2>
      <p style="color: #888;">この WebUI を使うには、まずサーバー側で bootstrap トークンを発行してください:</p>
      <pre style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; font-size: 0.9em;">portal-manage control issue-bootstrap-token \\
  --device-id webui \\
  --display-name "WebUI"</pre>
      <form id="bootstrap-form" style="display: flex; flex-direction: column; gap: 12px; margin-top: 24px;">
        <label>Device ID <input name="device_id" value="webui" required style="width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #444; background: #1a1a1a; color: inherit;"></label>
        <label>Display name <input name="display_name" value="WebUI" required style="width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #444; background: #1a1a1a; color: inherit;"></label>
        <label>Bootstrap token <input name="bootstrap_token" required style="width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #444; background: #1a1a1a; color: inherit; font-family: monospace;"></label>
        <button type="submit" class="btn btn-primary" style="padding: 10px;">セットアップ</button>
        <div id="bootstrap-error" style="color: #ff5252; font-size: 0.9em;"></div>
      </form>
    </section>
  `;
  document.getElementById("bootstrap-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const result = await registerDevice({
        device_id: fd.get("device_id"),
        display_name: fd.get("display_name"),
        bootstrap_token: fd.get("bootstrap_token"),
      });
      setToken(result.bearer_token, result.id);
      await initControlPlane();
    } catch (err) {
      document.getElementById("bootstrap-error").textContent = err.message;
    }
  });
}

function showError(msg) {
  const view = document.getElementById("control-view");
  view.innerHTML = `<div style="padding: 40px; text-align: center; color: #ff5252;">Error: ${escapeHTML(msg)}</div>`;
}

async function refreshAll() {
  try {
    const [devices, acls, ops, cmds] = await Promise.all([
      fetchDevices(), fetchAcl(), fetchOperations(), fetchCommands(),
    ]);
    _state.devices = devices;
    _state.acls = acls;
    _state.ops = ops;
    _state.cmds = cmds;
    render();
  } catch (e) {
    if (e.status === 401) {
      clearToken();
      showBootstrap();
    } else {
      showError(e.message);
    }
  }
}

function handleSseEvent(ev) {
  if (ev.type !== "command_status") return;
  const idx = _state.cmds.findIndex((c) => c.id === ev.command_id);
  if (idx >= 0) {
    _state.cmds[idx] = { ..._state.cmds[idx], ...ev };
  } else {
    refreshAll();
    return;
  }
  render();
}

function startAutoRefresh() {
  if (_refreshTimer) clearInterval(_refreshTimer);
  _refreshTimer = setInterval(refreshAll, 30000);
}

export function teardownControlPlane() {
  if (_sseUnsub) { _sseUnsub(); _sseUnsub = null; }
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
}

function render() {
  const view = document.getElementById("control-view");
  if (!view) return;
  const isAdmin = _state.me?.is_first_webui_device === true;
  view.innerHTML = `
    <div class="control-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
      <section>
        <h2 style="display: flex; justify-content: space-between; align-items: center;">
          <span>Devices</span>
          <span style="font-size: 0.6em; color: #888;">${escapeHTML(_state.me?.id || "")} ${isAdmin ? "(admin)" : ""}</span>
        </h2>
        <div id="devices-list"></div>
      </section>
      <section>
        <h2>Operations</h2>
        <div id="ops-list"></div>
      </section>
      <section style="grid-column: 1 / -1;">
        <h2>Commands</h2>
        <div id="cmds-list"></div>
      </section>
      ${isAdmin ? `
      <section style="grid-column: 1 / -1;">
        <h2>ACL</h2>
        <div id="acl-section"></div>
      </section>
      ` : ""}
    </div>
  `;
  renderDevices(isAdmin);
  renderOps();
  renderCmds();
  if (isAdmin) renderAcl();
}

function renderDevices(isAdmin) {
  const el = document.getElementById("devices-list");
  el.innerHTML = "";
  if (!_state.devices.length) {
    el.innerHTML = `<p style="color: #888;">No devices registered.</p>`;
    return;
  }
  const table = document.createElement("table");
  table.className = "control-table";
  table.innerHTML = `
    <thead><tr>
      <th>ID</th><th>Display</th><th>WS</th><th>Last seen</th>
      ${isAdmin ? "<th>Admin</th><th></th>" : ""}
    </tr></thead><tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  for (const d of _state.devices) {
    const tr = document.createElement("tr");
    const wsColor = d.ws_state === "online" ? "#20a020" : d.ws_state === "offline" ? "#888" : "#f0a020";
    tr.innerHTML = `
      <td><code>${escapeHTML(d.id)}</code></td>
      <td>${escapeHTML(d.display_name || "")}</td>
      <td><span style="color: ${wsColor};">${escapeHTML(d.ws_state || "never_connected")}</span></td>
      <td>${escapeHTML((d.last_seen || "—").toString().replace("T", " ").substring(0, 19))}</td>
      ${isAdmin ? `
        <td><input type="checkbox" data-device="${escapeHTML(d.id)}" data-action="admin" ${d.is_first_webui_device ? "checked" : ""}></td>
        <td><button class="btn btn-secondary" data-device="${escapeHTML(d.id)}" data-action="delete" style="color: #ff5252;">Delete</button></td>
      ` : ""}
    `;
    tbody.appendChild(tr);
  }
  if (isAdmin) {
    tbody.addEventListener("change", async (e) => {
      if (e.target.dataset.action === "admin") {
        const id = e.target.dataset.device;
        const value = e.target.checked;
        if (!confirm(value ? `${id} を admin に昇格しますか?` : `${id} から admin を剥奪しますか?`)) {
          e.target.checked = !value;
          return;
        }
        try {
          await setAdmin(id, value);
          await refreshAll();
        } catch (err) {
          alert(err.message);
          e.target.checked = !value;
        }
      }
    });
    tbody.addEventListener("click", async (e) => {
      if (e.target.dataset.action === "delete") {
        const id = e.target.dataset.device;
        if (!confirm(`Device ${id} を削除しますか?`)) return;
        try {
          await deleteDevice(id);
          await refreshAll();
        } catch (err) {
          alert(err.message);
        }
      }
    });
  }
  el.appendChild(table);
}

function renderOps() {
  const el = document.getElementById("ops-list");
  el.innerHTML = "";
  if (!_state.ops.length) {
    el.innerHTML = `<p style="color: #888;">No operations available.</p>`;
    return;
  }
  const onlineProviders = new Set(
    _state.devices.filter((d) => d.ws_state === "online").map((d) => `device:${d.id}`)
  );

  const byProvider = new Map();
  for (const op of _state.ops) {
    if (!byProvider.has(op.provider)) byProvider.set(op.provider, []);
    byProvider.get(op.provider).push(op);
  }

  for (const [provider, ops] of byProvider) {
    const card = document.createElement("div");
    card.className = "provider-card";
    card.style.marginBottom = "16px";
    card.style.padding = "12px";
    card.style.background = "var(--bg-card, #1e1e2e)";
    card.style.borderRadius = "10px";
    const isOnline = onlineProviders.has(provider);
    const statusColor = isOnline ? "#20a020" : "#888";
    card.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 8px;">
        ${escapeHTML(provider)}
        <span style="color: ${statusColor}; font-size: 0.85em; margin-left: 8px;">${isOnline ? "online" : "offline"}</span>
      </div>
    `;
    const btnRow = document.createElement("div");
    btnRow.style.display = "flex";
    btnRow.style.flexWrap = "wrap";
    btnRow.style.gap = "8px";
    for (const op of ops) {
      const btn = renderOpButton(op, (op) => openOpForm(op, provider));
      if (!isOnline) {
        btn.disabled = true;
        btn.title = "Provider is offline";
      }
      btnRow.appendChild(btn);
    }
    card.appendChild(btnRow);
    el.appendChild(card);
  }
}

function openOpForm(op, provider) {
  const targetId = provider.replace(/^device:/, "");
  renderOpForm(op, _state.me.id, targetId, async (body) => {
    const timeout = op.ui_hint?.timeout_seconds || 60;
    await issueCommand({ ...body, timeout_seconds: timeout });
    await refreshAll();
  });
}

function renderCmds() {
  const el = document.getElementById("cmds-list");
  el.innerHTML = "";
  const recent = _state.cmds.slice(0, 20);
  if (!recent.length) {
    el.innerHTML = `<p style="color: #888;">No commands yet.</p>`;
    return;
  }
  const table = document.createElement("table");
  table.className = "control-table";
  table.innerHTML = `
    <thead><tr>
      <th>ID</th><th>Op</th><th>Source</th><th>Target</th>
      <th>Status</th><th>Created</th><th>Completed</th><th>Result</th>
    </tr></thead><tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  for (const c of recent) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code style="font-size: 0.8em;">${escapeHTML(c.id.substring(0, 8))}</code></td>
      <td>${escapeHTML(c.operation)}</td>
      <td>${escapeHTML(c.source_device_id)}</td>
      <td>${escapeHTML(c.target_device_id)}</td>
      <td>${renderOperationStatus(c)}</td>
      <td>${escapeHTML((c.created_at || "").toString().substring(0, 19))}</td>
      <td>${escapeHTML((c.completed_at || "").toString().substring(0, 19))}</td>
      <td><code style="font-size: 0.8em;">${escapeHTML(JSON.stringify(c.result || c.error || "").substring(0, 60))}</code></td>
    `;
    tbody.appendChild(tr);
  }
  el.appendChild(table);
}

function renderAcl() {
  const el = document.getElementById("acl-section");
  el.innerHTML = `
    <form id="acl-form" style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr auto; gap: 8px; margin-bottom: 16px;">
      <input name="source_device" placeholder="device:source-*" required pattern="^device:.+" style="padding: 6px;">
      <input name="target_device" placeholder="device:target-*" required pattern="^device:.+" style="padding: 6px;">
      <input name="operation" placeholder="op regex (e.g. .*)" required style="padding: 6px;">
      <input name="extra" placeholder="extra (optional)" style="padding: 6px;">
      <button type="submit" class="btn btn-primary">追加</button>
    </form>
    <table class="control-table">
      <thead><tr><th>Source</th><th>Target</th><th>Op</th><th>Extra</th><th></th></tr></thead>
      <tbody id="acl-tbody"></tbody>
    </table>
  `;
  document.getElementById("acl-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await createAcl({
        source_device: fd.get("source_device"),
        target_device: fd.get("target_device"),
        operation: fd.get("operation"),
        extra: fd.get("extra") || "",
      });
      e.target.reset();
      await refreshAll();
    } catch (err) {
      alert(err.message);
    }
  });
  const tbody = document.getElementById("acl-tbody");
  for (const a of _state.acls) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${escapeHTML(a.source_device)}</code></td>
      <td><code>${escapeHTML(a.target_device)}</code></td>
      <td><code>${escapeHTML(a.operation)}</code></td>
      <td><code>${escapeHTML(a.extra || "")}</code></td>
      <td><button data-acl="${escapeHTML(a.id)}" class="btn btn-secondary" style="color: #ff5252;">削除</button></td>
    `;
    tbody.appendChild(tr);
  }
  tbody.addEventListener("click", async (e) => {
    if (!e.target.dataset.acl) return;
    if (!confirm("この ACL を削除しますか?")) return;
    try {
      await deleteAcl(e.target.dataset.acl);
      await refreshAll();
    } catch (err) {
      alert(err.message);
    }
  });
}
