import {
  fetchObtainiumExport,
  fetchApps,
  fetchSettings,
  type App,
  type Settings,
} from '../../js/api.js';

export const store = $state({
  allApps: [] as App[],
  dashboardApps: [] as App[],
  settings: { categories: {} } as Partial<Settings> & { categories?: Record<string, number> },
});

export async function loadAllData(): Promise<void> {
  const [exportData, appsData, settingsData] = await Promise.all([
    fetchObtainiumExport().catch(() => ({ apps: [] as App[] })),
    fetchApps().catch(() => [] as App[]),
    fetchSettings().catch(() => ({ categories: {} })),
  ]);
  store.allApps = exportData.apps || [];
  store.dashboardApps = appsData || [];
  store.settings = settingsData || {};
}
