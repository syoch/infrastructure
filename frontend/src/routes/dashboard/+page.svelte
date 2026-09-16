<script lang="ts">
  import DashboardHeader from '../../components/obtainium/DashboardHeader.svelte';
  import CategoriesBar from '../../components/obtainium/CategoriesBar.svelte';
  import AppsTable from '../../components/obtainium/AppsTable.svelte';
  import GlobalSettingsPanel from '../../components/obtainium/GlobalSettingsPanel.svelte';
  import SystemBackupPanel from '../../components/obtainium/SystemBackupPanel.svelte';
  import AppModal from '../../components/obtainium/AppModal.svelte';
  import CategoryModal from '../../components/obtainium/CategoryModal.svelte';
</script>

<div id="dashboard-view">
  <DashboardHeader />
  <CategoriesBar />
  <AppsTable />
  <GlobalSettingsPanel />
  <SystemBackupPanel />
  <AppModal active={false} appId={null} />
  <CategoryModal active={false} categoryName={null} />
</div>
