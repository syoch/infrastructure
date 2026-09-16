<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { ensureMe, auth } from '$lib/auth.svelte.ts';
  import { loadAllData } from '$lib/store.svelte.ts';
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

  function closeDropdown(): void {
    dropdownOpen = false;
  }
</script>

<svelte:window onclick={() => closeDropdown()} />

<!-- Background blobs for premium glassmorphic effect -->
<div class="blob-container">
  <div class="blob blob-1"></div>
  <div class="blob blob-2"></div>
  <div class="blob blob-3"></div>
</div>

<header>
  <div class="header-content container">
    <div class="logo">
      <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
      </svg>
      <span class="logo-text">Android Provisioning Portal</span>
    </div>

    <nav class="header-nav">
      <a href="/" class="nav-btn" id="nav-portal" class:active={isPortal}>ポータル</a>
      <a href="/dashboard" class="nav-btn" id="nav-dashboard" class:active={isDashboard}>ダッシュボード</a>
      <div class="nav-dropdown" id="control-dropdown" class:active={isControl} class:open={dropdownOpen}>
        <button
          class="nav-btn nav-dropdown-toggle"
          id="nav-control"
          aria-haspopup="true"
          aria-expanded={dropdownOpen}
          class:active={isControl}
          onclick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            dropdownOpen = !dropdownOpen;
          }}
        >
          コントロール
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="nav-dropdown-caret">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
        <div class="nav-dropdown-menu" role="menu">
          <a href="/control/devices" class="nav-dropdown-item" role="menuitem">Devices</a>
          <a
            href="/control/acl"
            class="nav-dropdown-item"
            class:hidden={!isAdmin}
            role="menuitem"
            data-requires-admin="true"
          >ACL</a>
        </div>
      </div>
      <a href="/operations" class="nav-btn" id="nav-operations" class:active={isOperations}>オペレーション</a>
      <a href="/apps" class="nav-btn" id="nav-apps" class:active={isApps}>アプリ</a>
    </nav>

    <div class="server-status">
      <span class="status-indicator online"></span>
      <span class="status-text">Repository Online</span>
    </div>
  </div>
</header>

<main class="container">
  {@render children()}
</main>

<footer>
  <div class="footer-content container">
    <p>Android Provisioning Repo &copy; 2026</p>
    <p class="footer-path">Workspace: <code id="root-path">/mnt/NAS/Android Root</code></p>
  </div>
</footer>
