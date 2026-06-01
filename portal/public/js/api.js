export async function fetchObtainiumExport() {
  const res = await fetch('/obtainium-export.json');
  if (!res.ok) throw new Error('Obtainium export not found');
  return res.json();
}

export async function fetchApps() {
  const res = await fetch('/api/apps');
  if (!res.ok) throw new Error('Failed to fetch apps');
  return res.json();
}

export async function fetchSettings() {
  const res = await fetch('/api/settings');
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function saveApp(appData) {
  const res = await fetch('/api/apps/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(appData)
  });
  if (!res.ok) throw new Error('Failed to save app');
  return res.json();
}

export async function deleteApp(id) {
  const res = await fetch('/api/apps/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id })
  });
  if (!res.ok) throw new Error('Failed to delete app');
  return res.json();
}

export async function saveSettings(payload) {
  const res = await fetch('/api/settings/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to save settings');
  return res.json();
}

export async function compileSettings() {
  const res = await fetch('/api/apps/compile', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to compile settings');
  return res.json();
}

export async function uploadLocalAPK(formData) {
  const res = await fetch('/api/apps/local-apks', {
    method: 'POST',
    body: formData
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to upload and register APK');
  }
  return res.json();
}

export async function deleteLocalAPK(id) {
  const res = await fetch(`/api/apps/local-apks/${id}`, {
    method: 'DELETE'
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to delete APK');
  }
  return res.json();
}

export async function importObtainiumConfig(jsonData) {
  const res = await fetch('/api/apps/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jsonData)
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to import configuration');
  }
  return res.json();
}

export async function restoreBackup(file, strategy) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('strategy', strategy);

  const res = await fetch('/api/restore', {
    method: 'POST',
    body: formData
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to restore backup');
  }
  return res.json();
}
