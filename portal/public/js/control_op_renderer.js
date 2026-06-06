import { escapeHTML } from "./ui.js";
import { renderSchema } from "./schema_renderer.js";

export function renderOpButton(op, onClick) {
  const label = op.ui_hint?.label || op.name;
  const btn = document.createElement("button");
  btn.className = "btn btn-primary";
  btn.textContent = label;
  btn.title = op.description || op.name;
  btn.addEventListener("click", () => onClick(op));
  return btn;
}

export function renderOpForm(op, sourceDeviceId, targetDeviceId, onSubmit) {
  const overlay = document.createElement("div");
  overlay.className = "modal-backdrop";
  overlay.style.display = "flex";

  const modal = document.createElement("div");
  modal.className = "modal-content";
  modal.style.maxWidth = "560px";

  const h = document.createElement("h2");
  h.textContent = op.ui_hint?.label || op.name;
  modal.appendChild(h);

  const desc = document.createElement("p");
  desc.style.color = "var(--text-secondary, #888)";
  desc.textContent = op.description || `Operation: ${op.name}`;
  modal.appendChild(desc);

  const form = document.createElement("form");
  form.style.display = "flex";
  form.style.flexDirection = "column";
  form.style.gap = "12px";

  const formBody = document.createElement("div");
  formBody.className = "schema-form-body";
  form.appendChild(formBody);

  const schema = op.params_schema && Object.keys(op.params_schema).length > 0
    ? op.params_schema
    : { type: "object", properties: {} };
  let node;
  try {
    node = renderSchema(schema, formBody);
  } catch (e) {
    formBody.appendChild(document.createTextNode(`Schema render error: ${e.message}`));
    node = { getValue: () => ({}) };
  }

  const actions = document.createElement("div");
  actions.className = "form-actions";
  actions.style.marginTop = "16px";

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.className = "btn btn-primary";
  submitBtn.textContent = "実行";
  submitBtn.style.flex = "2";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn btn-secondary";
  cancelBtn.textContent = "キャンセル";
  cancelBtn.style.flex = "1";
  cancelBtn.addEventListener("click", () => document.body.removeChild(overlay));

  actions.appendChild(submitBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(actions);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    let params = {};
    try {
      params = node.getValue() || {};
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = "実行";
      const errBox = document.createElement("div");
      errBox.style.color = "#ff5252";
      errBox.style.fontSize = "0.9em";
      errBox.textContent = `Error: ${err.message}`;
      form.appendChild(errBox);
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "送信中…";
    try {
      await onSubmit({ operation: op.id, source_device_id: sourceDeviceId, target_device_id: targetDeviceId, params });
      document.body.removeChild(overlay);
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = "実行";
      const errBox = document.createElement("div");
      errBox.style.color = "#ff5252";
      errBox.style.fontSize = "0.9em";
      errBox.textContent = `Error: ${err.message}`;
      form.appendChild(errBox);
    }
  });

  modal.appendChild(form);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

export function renderOperationStatus(cmd) {
  const status = cmd.status;
  const color = {
    pending: "#f0a020",
    claimed: "#2080f0",
    succeeded: "#20a020",
    failed: "#ff5252",
    timeout: "#888",
    cancelled: "#888",
  }[status] || "#888";
  return `<span style="color: ${color}; font-weight: 600;">${escapeHTML(status)}</span>`;
}
