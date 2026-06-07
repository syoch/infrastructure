import { fetchObtainiumExport, fetchApps, fetchSettings } from './js/api.js';
import { parseHash, initRouter } from './js/router.js';
import { initPortal } from './js/portal.js';
import {
  initDashboard,
  updateDashboardState,
  renderDashboardAppsList,
  renderCategoriesBar,
  openQuickAppModal,
  openCategoryModal,
  showDetailedEdit,
  closeAllModals
} from './js/dashboard.js';
import { initControlSubroute, teardownControlSubroute } from './js/control_router.js';
import {
  initOperationsSection, teardownOperationsSection, applyOperationsFilterFromHash,
} from './js/control_operations.js';
import { getToken, fetchMe } from './js/control_api.js';

let allApps = [];
let dashboardApps = [];
let globalSettings = {};
let _currentSection = '';
let _me = null;
let _mePromise = null;

async function getMe() {
  if (_me) return _me;
  if (!_mePromise) {
    _mePromise = (async () => {
      try {
        _me = await fetchMe();
        return _me;
      } catch (e) {
        _me = null;
        throw e;
      } finally {
        _mePromise = null;
      }
    })();
  }
  return _mePromise;
}

async function loadAllData() {
  try {
    const [exportData, appsData, settingsData] = await Promise.all([
      fetchObtainiumExport().catch(err => {
        console.error('Error fetching obtainium-export.json:', err);
        return { apps: [] };
      }),
      fetchApps().catch(err => {
        console.error('Error fetching dashboard apps:', err);
        return { apps: [] };
      }),
      fetchSettings().catch(err => {
        console.error('Error fetching global settings:', err);
        return { categories: {} };
      })
    ]);

    allApps = exportData.apps || [];
    dashboardApps = appsData.apps || [];
    globalSettings = settingsData || {};

    updateDashboardState(dashboardApps, globalSettings);
  } catch (err) {
    console.error('Error loading initialization data:', err);
  }
}

function showSection(sectionId) {
  ['portal-view', 'dashboard-view', 'app-edit-view', 'control-view', 'operations-view'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      if (id === sectionId) {
        el.style.display = '';
        el.classList.add('active');
      } else {
        el.classList.remove('active');
        el.style.display = 'none';
      }
    }
  });
}

function teardownCurrent() {
  if (_currentSection === 'control') teardownControlSubroute();
  else if (_currentSection === 'operations') teardownOperationsSection();
  _currentSection = '';
}

function updateNavForSection(route, sub) {
  const navPortal = document.getElementById('nav-portal');
  const navDashboard = document.getElementById('nav-dashboard');
  const navControl = document.getElementById('nav-control');
  const navOperations = document.getElementById('nav-operations');
  const dropdown = document.getElementById('control-dropdown');
  const allNavBtns = [navPortal, navDashboard, navControl, navOperations].filter(Boolean);

  allNavBtns.forEach((b) => b && b.classList.remove('active'));

  const isControlFamily = route === 'control';
  const isDashboardFamily = ['dashboard', 'list', 'new', 'edit'].includes(route);
  const isOperations = route === 'operations';

  if (isControlFamily) {
    if (dropdown) dropdown.classList.add('active');
    if (navControl) navControl.classList.add('active');
  } else if (isDashboardFamily) {
    if (navDashboard) navDashboard.classList.add('active');
  } else if (isOperations) {
    if (navOperations) navOperations.classList.add('active');
  } else {
    if (navPortal) navPortal.classList.add('active');
  }
}

function applyAdminVisibility() {
  const me = _me;
  if (!me) return;
  document.querySelectorAll('[data-requires-admin="true"]').forEach((el) => {
    el.classList.toggle('hidden', !me.is_first_webui_device);
  });
}

async function handleRouting() {
  const { route, sub, params } = parseHash();
  teardownCurrent();

  const isAdminRoute = ['dashboard', 'list', 'new', 'edit'].includes(route);
  let activeSectionId = 'portal-view';

  if (route === 'control') {
    activeSectionId = 'control-view';
    _currentSection = 'control';
    if (!getToken()) {
      // no token, fall through to bootstrap render
    } else {
      try {
        await getMe();
      } catch (e) { /* handled inside router */ }
    }
    applyAdminVisibility();
    initControlSubroute(sub);
  } else if (route === 'operations') {
    activeSectionId = 'operations-view';
    _currentSection = 'operations';
    if (!getToken()) {
      window.location.hash = '#/control';
      return;
    }
    try {
      await getMe();
      applyAdminVisibility();
      await initOperationsSection(params);
    } catch (e) {
      if (e.status === 401) {
        window.location.hash = '#/control';
        return;
      }
      const view = document.getElementById('operations-view');
      if (view) view.innerHTML = `<div class="control-error">Error: ${e.message}</div>`;
    }
  } else if (isAdminRoute) {
    if (route === 'edit' && params.type === 'app') {
      activeSectionId = 'app-edit-view';
    } else {
      activeSectionId = 'dashboard-view';
    }
  } else {
    activeSectionId = 'portal-view';
  }

  updateNavForSection(route, sub);
  showSection(activeSectionId);
  closeAllModals();

  if (isAdminRoute) {
    if (route === 'new') {
      const type = params.type;
      if (type === 'app') {
        openQuickAppModal(null);
      } else if (type === 'category') {
        openCategoryModal(null);
      }
    } else if (route === 'edit') {
      const type = params.type;
      const id = params.id;
      if (type === 'app' && id) {
        showDetailedEdit(id);
      } else if (type === 'quick-app' && id) {
        openQuickAppModal(id);
      } else if (type === 'category' && id) {
        openCategoryModal(id);
      }
    }
  }
}

async function handleDataChange() {
  await loadAllData();

  initPortal(allApps, globalSettings.categories || {});
  renderDashboardAppsList(dashboardApps, globalSettings.categories || {});
  renderCategoriesBar(globalSettings.categories || {});

  handleRouting();
}

function setupNavDropdown() {
  const dropdown = document.getElementById('control-dropdown');
  const toggle = document.getElementById('nav-control');
  if (!dropdown || !toggle) return;
  toggle.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const open = dropdown.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target)) {
      dropdown.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
  dropdown.querySelectorAll('.nav-dropdown-item').forEach((item) => {
    item.addEventListener('click', () => {
      dropdown.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadAllData();

  initDashboard(handleDataChange);
  initPortal(allApps, globalSettings.categories || {});
  renderDashboardAppsList(dashboardApps, globalSettings.categories || {});
  renderCategoriesBar(globalSettings.categories || {});

  setupNavDropdown();
  initRouter(handleRouting);
});
