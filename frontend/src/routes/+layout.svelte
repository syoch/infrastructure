<script lang="ts">
  import { onMount } from 'svelte';
  import { Toast } from '@skeletonlabs/skeleton-svelte';
  import { ensureMe } from '$lib/auth.svelte.ts';
  import { loadAllData } from '$lib/store.svelte.ts';
  import { toaster } from '$lib/toast.ts';
  import Hamburger from '@lucide/svelte/icons/menu';
  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import PromptDialog from '$lib/components/PromptDialog.svelte';
  import '../app.css';
  import DashboardIcon from '@lucide/svelte/icons/layout-dashboard';
  import DeviceIcon from '@lucide/svelte/icons/laptop';
  import ACLIcon from '@lucide/svelte/icons/shield';
  import OperationsIcon from '@lucide/svelte/icons/hammer';
  import AppsIcon from '@lucide/svelte/icons/package';
  import HomeIcon from '@lucide/svelte/icons/home';

  import { Navigation } from '@skeletonlabs/skeleton-svelte';

  const linksSidebar = {
    apps: [{ label: 'Dashboard', href: '/dashboard', icon: DashboardIcon }],
    control: [
      { label: 'Devices', href: '/control/devices', icon: DeviceIcon },
      { label: 'ACL', href: '/control/acl', icon: ACLIcon },
      { label: 'Operations', href: '/operations', icon: OperationsIcon },
    ],
    'app portal': [{ label: 'Apps', href: '/apps', icon: AppsIcon }],
  };

  let { children } = $props();

  onMount(() => {
    loadAllData();
    ensureMe();
  });

  let navigationStyle: 'sidebar' | 'bar' | 'rail' = $state('rail');
</script>

<div class="w-full h-[100vh] grid grid-cols-[auto_1fr] items-stretch border border-surface-200-800">
  <Navigation layout={navigationStyle} class="grid grid-rows-[auto_1fr_auto] gap-4">
    <Navigation.Header>
      <Navigation.Trigger
        onclick={() => {
          navigationStyle = navigationStyle === 'sidebar' ? 'rail' : 'sidebar';
        }}
      >
        <Hamburger class="w-5 h-5" />
        <span>Menu</span>
      </Navigation.Trigger>
    </Navigation.Header>
    <Navigation.Content>
      <Navigation.Group>
        <Navigation.Menu>
          <Navigation.TriggerAnchor href="/">
            <HomeIcon class="w-5 h-5" />
            <Navigation.TriggerText>Home</Navigation.TriggerText>
          </Navigation.TriggerAnchor>
        </Navigation.Menu>
      </Navigation.Group>
      {#each Object.entries(linksSidebar) as [category, links]}
        <Navigation.Group>
          <Navigation.Label class="capitalize pl-2">{category}</Navigation.Label>
          <Navigation.Menu>
            {#each links as link (link)}
              {@const Icon = link.icon}
              <Navigation.TriggerAnchor href={link.href} title={link.label} aria-label={link.label}>
                <Icon class="w-5 h-5" />
                <Navigation.TriggerText>{link.label}</Navigation.TriggerText>
              </Navigation.TriggerAnchor>
            {/each}
          </Navigation.Menu>
        </Navigation.Group>
      {/each}
    </Navigation.Content>
    <Navigation.Footer>a</Navigation.Footer>
  </Navigation>
  <div class="overflow-y-auto overflow-x-auto">
    <div class="p-6">
      {@render children()}
    </div>
  </div>
</div>

<Toast.Group {toaster}>
  {#snippet children(toast)}
    <Toast {toast} data-testid="toast">
      <Toast.Message>
        <Toast.Title data-testid="toast-title">{toast.title}</Toast.Title>
        {#if toast.description}
          <Toast.Description>{toast.description}</Toast.Description>
        {/if}
      </Toast.Message>
      <Toast.CloseTrigger />
    </Toast>
  {/snippet}
</Toast.Group>

<ConfirmDialog />
<PromptDialog />

<style></style>
