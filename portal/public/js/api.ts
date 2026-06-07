export interface App {
  id: string;
  name: string;
  url?: string;
  overrideSource?: string | null;
  override_source?: string | null;
  preferredApkIndex?: number | null;
  preferred_apk_index?: number | null;
  pinned?: boolean;
  categories?: string[];
  summary?: string;
  description?: string;
  icon?: string;
  version?: string;
  version_code?: number;
  apk_urls?: string[];
  apk_hashes?: string[];
  download_url?: string;
  additionalSettings?: {
    includePrereleases?: boolean;
    fallbackToOlderReleases?: boolean;
    versionDetection?: boolean;
    apkFilterRegEx?: string;
    invertAPKFilter?: boolean;
  };
  apks?: Array<{
    id: number;
    version: string;
    architecture: string;
    file_hash: string;
  }>;
}

export interface Settings {
  theme: 'light' | 'dark' | 'system' | string;
  compact_list: boolean;
  show_version: boolean;
  sort_by: 'name' | 'category' | 'updated';
  sort_order: 'asc' | 'desc';
  categories?: Record<string, number>;
  checkInterval?: number | null;
  checkOnStartup?: boolean;
  includePreReleases?: boolean;
  allowSourceChange?: boolean;
  backgroundRestrictedNotification?: boolean;
}

export interface LocalAPK {
  id: string;
  filename: string;
  sha256: string;
  size: number;
  uploaded_at: string;
}

export interface ObtainiumExport {
  apps: App[];
  categories: string[];
  settings: Settings;
}

export interface SaveAppPayload {
  id: string;
  name: string;
  url?: string;
  overrideSource?: string | null;
  preferredApkIndex?: number | null;
  pinned?: boolean;
  allowIdChange?: boolean;
  categories?: string[];
  additionalSettings?: {
    includePrereleases?: boolean;
    fallbackToOlderReleases?: boolean;
    versionDetection?: boolean;
    apkFilterRegEx?: string;
    invertAPKFilter?: boolean;
  };
}

export interface ImportResult {
  imported: number;
  updated: number;
  skipped: number;
  errors: string[];
  message?: string;
}

export interface RestoreResult {
  devices: number;
  acls: number;
  tokens: number;
  operations: number;
  commands: number;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchObtainiumExport(): Promise<ObtainiumExport> {
  return request('/obtainium-export.json');
}

export async function fetchApps(): Promise<App[]> {
  const data = await request<{ apps: App[] }>('/api/apps');
  return data.apps || [];
}

export async function fetchSettings(): Promise<Settings> {
  return request('/api/settings');
}

export async function saveApp(appData: SaveAppPayload): Promise<App> {
  return request('/api/apps/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(appData),
  });
}

export async function deleteApp(id: string): Promise<{ status: string }> {
  return request('/api/apps/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  });
}

export async function saveSettings(payload: Partial<Settings>): Promise<Settings> {
  return request('/api/settings/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function compileSettings(): Promise<{ status: string }> {
  return request('/api/apps/compile', { method: 'POST' });
}

export async function uploadLocalAPK(formData: FormData): Promise<LocalAPK> {
  const res = await fetch('/api/apps/local-apks', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to upload and register APK');
  }
  return res.json();
}

export async function deleteLocalAPK(id: string): Promise<{ status: string }> {
  const res = await fetch(`/api/apps/local-apks/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to delete APK');
  }
  return res.json();
}

export async function importObtainiumConfig(jsonData: object): Promise<ImportResult> {
  return request('/api/apps/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jsonData),
  });
}

export async function restoreBackup(file: File, strategy: string): Promise<RestoreResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('strategy', strategy);

  return request('/api/restore', {
    method: 'POST',
    body: formData,
  });
}