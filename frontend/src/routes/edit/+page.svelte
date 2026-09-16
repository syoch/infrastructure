<script lang="ts">
  import { page } from '$app/state';
  import { goto as navigate } from '$app/navigation';
  import { store } from '../../lib/store.svelte.ts';
  import DashboardHeader from '../../components/obtainium/DashboardHeader.svelte';
  import CategoriesBar from '../../components/obtainium/CategoriesBar.svelte';
  import AppsTable from '../../components/obtainium/AppsTable.svelte';
  import GlobalSettingsPanel from '../../components/obtainium/GlobalSettingsPanel.svelte';
  import SystemBackupPanel from '../../components/obtainium/SystemBackupPanel.svelte';
  import AppModal from '../../components/obtainium/AppModal.svelte';
  import CategoryModal from '../../components/obtainium/CategoryModal.svelte';
  import AppEditHeader from '../../components/obtainium/AppEditHeader.svelte';
  import AppDetailedForm from '../../components/obtainium/AppDetailedForm.svelte';
  import SelfHostedApkManager from '../../components/obtainium/SelfHostedApkManager.svelte';

  const type = $derived(page.url.searchParams.get('type') ?? '');
  const id = $derived(page.url.searchParams.get('id') ?? '');
  const isApp = $derived(type === 'app');
  const app = $derived(isApp ? (store.dashboardApps.find(a => a.id === id) ?? null) : null);

  let appSource = $state('');
  let foundOnce = false;

  const appModalActive = $derived(type === 'quick-app');
  const appModalId = $derived(type === 'quick-app' ? id || null : null);
  const categoryModalActive = $derived(type === 'category');
  const categoryModalName = $derived(type === 'category' ? id || null : null);

  $effect(() => {
    if (!isApp) return;
    if (app) {
      foundOnce = true;
      return;
    }
    if (!foundOnce && id && store.dashboardApps.length > 0) navigate('/list');
  });
</script>

{#if isApp}
  <div id="app-edit-view">
    <AppEditHeader />
    {#if app}
      <AppDetailedForm {app} bind:appSource />
      <SelfHostedApkManager {app} isSelfHosted={appSource === 'HTML'} />
    {/if}
    <AppModal active={false} appId={null} />
    <CategoryModal active={false} categoryName={null} />
  </div>
{:else}
  <div id="dashboard-view">
    <DashboardHeader />
    <CategoriesBar />
    <AppsTable />
    <GlobalSettingsPanel />
    <SystemBackupPanel />
    <AppModal active={appModalActive} appId={appModalId} />
    <CategoryModal active={categoryModalActive} categoryName={categoryModalName} />
  </div>
{/if}
