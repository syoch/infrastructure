<script lang="ts">
  import { page } from '$app/state';
  import DashboardHeader from '../../components/obtainium/DashboardHeader.svelte';
  import CategoriesBar from '../../components/obtainium/CategoriesBar.svelte';
  import AppsTable from '../../components/obtainium/AppsTable.svelte';
  import GlobalSettingsPanel from '../../components/obtainium/GlobalSettingsPanel.svelte';
  import SystemBackupPanel from '../../components/obtainium/SystemBackupPanel.svelte';
  import AppModal from '../../components/obtainium/AppModal.svelte';
  import CategoryModal from '../../components/obtainium/CategoryModal.svelte';

  const type = $derived(page.url.searchParams.get('type') ?? '');
  const appModalActive = $derived(type === 'app');
  const categoryModalActive = $derived(type === 'category');
</script>

<div id="dashboard-view">
  <DashboardHeader />
  <CategoriesBar />
  <AppsTable />
  <GlobalSettingsPanel />
  <SystemBackupPanel />
  <AppModal active={appModalActive} appId={null} />
  <CategoryModal active={categoryModalActive} categoryName={null} />
</div>
