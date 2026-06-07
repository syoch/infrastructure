import { registerDevice, setToken, getToken } from "./control_api.js";

export async function initBootstrap() {
  const view = document.getElementById("control-view");
  if (!view) return;
  view.innerHTML = `
    <section class="bootstrap-section">
      <h2>WebUI セットアップ</h2>
      <p class="bootstrap-hint">この WebUI を使うには、まずサーバー側で bootstrap トークンを発行してください:</p>
      <pre class="bootstrap-pre">portal-manage control issue-bootstrap-token \\
  --device-id webui \\
  --display-name "WebUI"</pre>
      <form id="bootstrap-form" class="bootstrap-form">
        <label>Device ID <input name="device_id" value="webui" required></label>
        <label>Display name <input name="display_name" value="WebUI" required></label>
        <label>Bootstrap token <input name="bootstrap_token" required class="mono"></label>
        <button type="submit" class="btn btn-primary">セットアップ</button>
        <div id="bootstrap-error" class="bootstrap-error"></div>
      </form>
    </section>
  `;
  document.getElementById("bootstrap-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const errEl = document.getElementById("bootstrap-error");
    errEl.textContent = "";
    try {
      const result = await registerDevice({
        device_id: fd.get("device_id"),
        display_name: fd.get("display_name"),
        bootstrap_token: fd.get("bootstrap_token"),
      });
      setToken(result.bearer_token, result.id);
      window.location.hash = "#/control/devices";
    } catch (err) {
      errEl.textContent = err.message;
    }
  });
}

export function teardownBootstrap() {
  const view = document.getElementById("control-view");
  if (view) view.innerHTML = "";
}
