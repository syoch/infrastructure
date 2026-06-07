import { escapeHTML } from './ui.js';
import { renderSchema } from './schema_renderer.js';
import { OperationSpec } from './control_api.js';

export function renderOpButton(op: OperationSpec, onClick: (op: OperationSpec) => void): HTMLButtonElement {
  const label = op.ui_hint?.label || op.name;
  const btn = document.createElement('button');
  btn.className = 'btn btn-primary';
  btn.textContent = label;
  btn.title = op.description || op.name;
  btn.addEventListener('click', () => onClick(op));
  return btn;
}

export interface OpFormSubmitBody {
  operation: string;
  source_device_id: string;
  target_device_id: string;
  params: object;
}

export function renderOpForm(
  op: OperationSpec,
  sourceDeviceId: string,
  targetDeviceId: string,
  onSubmit: (body: OpFormSubmitBody) => Promise<void>
): void {
  const overlay = document.createElement('div');
  overlay.className = 'modal-backdrop active';
  overlay.style.display = 'flex';

  const modal = document.createElement('div');
  modal.className = 'modal-content';
  modal.style.maxWidth = '560px';

  const h = document.createElement('h2');
  h.textContent = op.ui_hint?.label || op.name;
  modal.appendChild(h);

  const desc = document.createElement('p');
  desc.style.color = 'var(--text-secondary, #888)';
  desc.textContent = op.description || `Operation: ${op.name}`;
  modal.appendChild(desc);

  const form = document.createElement('form');
  form.style.display = 'flex';
  form.style.flexDirection = 'column';
  form.style.gap = '12px';

  const formBody = document.createElement('div');
  formBody.className = 'schema-form-body';
  form.appendChild(formBody);

  const schema = op.params_schema && Object.keys(op.params_schema).length > 0
    ? op.params_schema
    : { type: 'object', properties: {} };
  let node: { getValue: () => unknown };
  try {
    node = renderSchema(schema, formBody);
  } catch (e) {
    formBody.appendChild(document.createTextNode(`Schema render error: ${e instanceof Error ? e.message : String(e)}`));
    node = { getValue: () => ({}) };
  }

  const actions = document.createElement('div');
  actions.className = 'form-actions';
  actions.style.marginTop = '16px';

  const submitBtn = document.createElement('button');
  submitBtn.type = 'submit';
  submitBtn.className = 'btn btn-primary';
  submitBtn.textContent = '実行';
  submitBtn.style.flex = '2';

  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.className = 'btn btn-secondary';
  cancelBtn.textContent = 'キャンセル';
  cancelBtn.style.flex = '1';
  cancelBtn.addEventListener('click', () => document.body.removeChild(overlay));

  actions.appendChild(submitBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(actions);

  form.addEventListener('submit', async (e: SubmitEvent) => {
    e.preventDefault();
    let params: object = {};
    try {
      params = (node.getValue() as object) || {};
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = '実行';
      const errBox = document.createElement('div');
      errBox.style.color = '#ff5252';
      errBox.style.fontSize = '0.9em';
      errBox.textContent = `Error: ${err instanceof Error ? err.message : String(err)}`;
      form.appendChild(errBox);
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = '送信中…';
    try {
      await onSubmit({ operation: op.id, source_device_id: sourceDeviceId, target_device_id: targetDeviceId, params });
      document.body.removeChild(overlay);
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = '実行';
      const errBox = document.createElement('div');
      errBox.style.color = '#ff5252';
      errBox.style.fontSize = '0.9em';
      errBox.textContent = `Error: ${err instanceof Error ? err.message : String(err)}`;
      form.appendChild(errBox);
    }
  });

  modal.appendChild(form);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

export function renderOperationStatus(cmd: { status: string }): string {
  const status = cmd.status;
  const color: Record<string, string> = {
    pending: '#f0a020',
    claimed: '#2080f0',
    succeeded: '#20a020',
    failed: '#ff5252',
    timeout: '#888',
    cancelled: '#888',
  };
  return `<span style="color: ${color[status] || '#888'}; font-weight: 600;">${escapeHTML(status)}</span>`;
}