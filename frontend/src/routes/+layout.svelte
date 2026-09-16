<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { Menu, Portal, Toast } from '@skeletonlabs/skeleton-svelte';
  import { ensureMe, auth } from '$lib/auth.svelte.ts';
  import { loadAllData } from '$lib/store.svelte.ts';
  import { toaster } from '$lib/toast.ts';
  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import PromptDialog from '$lib/components/PromptDialog.svelte';
  import '../app.css';

  let { children } = $props();

  let dropdownOpen = $state(false);

  onMount(() => {
    loadAllData();
    ensureMe();
  });

  const path = $derived(page.url.pathname);
  const type = $derived(page.url.searchParams.get('type') ?? '');

  const isEditApp = $derived(path === '/edit' && type === 'app');
  const isControl = $derived(path.startsWith('/control'));
  const isOperations = $derived(path === '/operations');
  const isApps = $derived(path.startsWith('/apps'));
  const isDashboard = $derived(
    ['/dashboard', '/list', '/new', '/edit'].includes(path) && !isEditApp
  );
  const isPortal = $derived(
    !isControl && !isOperations && !isApps && !isDashboard && !isEditApp
  );
  const isAdmin = $derived(auth.me?.is_first_webui_device === true);

  const navActive = 'btn btn-sm preset-filled-primary-500';
  const navIdle = 'btn btn-sm preset-tonal';
</script>

<!-- Background blobs for premium glassmorphic effect -->
<div class="blob-container">
  <div class="blob blob-1"></div>
  <div class="blob blob-2"></div>
  <div class="blob blob-3"></div>
</div>

<header class="sticky top-0 z-40 border-b border-surface-200-800 bg-surface-50-950/80 backdrop-blur">
  <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3">
    <div class="flex items-center gap-2">
      <svg
        class="size-7 text-primary-500"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
      </svg>
      <span class="text-sm font-bold sm:text-base">Android Provisioning Portal</span>
    </div>

    <nav class="flex flex-wrap items-center gap-2">
      <a href="/" class={isPortal ? navActive : navIdle} id="nav-portal">ポータル</a>
      <a
        href="/dashboard"
        class={isDashboard ? navActive : navIdle}
        id="nav-dashboard">ダッシュボード</a
      >

      <Menu
        open={dropdownOpen}
        onOpenChange={(details) => {
          dropdownOpen = details.open;
        }}
      >
        <div id="control-dropdown" data-testid="control-dropdown">
          <Menu.Trigger
            class={isControl ? navActive : navIdle}
            data-testid="control-menu-trigger"
          >
            {#snippet element(attributes)}
              <button {...attributes} id="nav-control">
                コントロール
                <svg
                  viewBox="0 0 24 24"
                  width="14"
                  height="14"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
            {/snippet}
          </Menu.Trigger>
        </div>
        <Portal>
          <Menu.Positioner class="z-50">
            <Menu.Content
              class="card bg-surface-100-900 min-w-40 p-1 shadow-xl"
              data-testid="control-menu"
            >
              <Menu.Item
                value="devices"
                class="cursor-pointer rounded px-3 py-2 text-sm hover:preset-tonal"
                data-testid="control-menu-devices"
                onclick={() => {
                  dropdownOpen = false;
                  void goto('/control/devices');
                }}
              >
                Devices
              </Menu.Item>
              {#if isAdmin}
                <Menu.Item
                  value="acl"
                  class="cursor-pointer rounded px-3 py-2 text-sm hover:preset-tonal"
                  data-testid="control-menu-acl"
                  data-requires-admin="true"
                  onclick={() => {
                    dropdownOpen = false;
                    void goto('/control/acl');
                  }}
                >
                  ACL
                </Menu.Item>
              {/if}
            </Menu.Content>
          </Menu.Positioner>
        </Portal>
      </Menu>

      <a
        href="/operations"
        class={isOperations ? navActive : navIdle}
        id="nav-operations">オペレーション</a
      >
      <a href="/apps" class={isApps ? navActive : navIdle} id="nav-apps">アプリ</a>
    </nav>

    <div class="flex items-center gap-2">
      <span class="size-2 rounded-full bg-success-500"></span>
      <span class="text-xs text-surface-700-300">Repository Online</span>
    </div>
  </div>
</header>

<main class="mx-auto w-full max-w-7xl px-4 py-6">
  {@render children()}
</main>

<footer class="mt-12 border-t border-surface-200-800">
  <div
    class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-6 text-xs text-surface-700-300"
  >
    <p>Android Provisioning Repo &copy; 2026</p>
    <p>Workspace: <code id="root-path">/mnt/NAS/Android Root</code></p>
  </div>
</footer>

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

<style>
  .blob-container {
    position: fixed;
    inset: 0;
    z-index: -1;
    overflow: hidden;
    pointer-events: none;
  }
  .blob {
    position: absolute;
    border-radius: 50%;
    filter: blur(120px);
    opacity: 0.15;
    mix-blend-mode: screen;
    animation: float 25s infinite alternate;
  }
  .blob-1 {
    width: 500px;
    height: 500px;
    background: #7c4dff;
    top: -10%;
    right: -5%;
    animation-duration: 20s;
  }
  .blob-2 {
    width: 400px;
    height: 400px;
    background: #00e5ff;
    bottom: 10%;
    left: -5%;
    animation-duration: 25s;
  }
  .blob-3 {
    width: 300px;
    height: 300px;
    background: #ff4081;
    top: 40%;
    left: 50%;
    transform: translate(-50%, -50%);
    animation-duration: 30s;
  }
  @keyframes float {
    0% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(5%, 10%) scale(1.1); }
    100% { transform: translate(-5%, -5%) scale(0.9); }
  }
</style>
