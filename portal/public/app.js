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
import { initControlPlane, teardownControlPlane } from './js/control_dashboard.js';

let allApps = [];
let dashboardApps = [];
let globalSettings = {};

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
  ['portal-view', 'dashboard-view', 'app-edit-view', 'control-view'].forEach(id => {
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

function handleRouting() {
  const { route, params } = parseHash();

  const navPortal = document.getElementById('nav-portal');
  const navDashboard = document.getElementById('nav-dashboard');
  const navControl = document.getElementById('nav-control');

  let activeSectionId = 'portal-view';
  const isAdminRoute = ['dashboard', 'list', 'new', 'edit'].includes(route);

  if (route === 'control') {
    activeSectionId = 'control-view';
    if (navPortal) navPortal.classList.remove('active');
    if (navDashboard) navDashboard.classList.remove('active');
    if (navControl) navControl.classList.add('active');
    teardownControlPlane();
    initControlPlane();
  } else if (isAdminRoute) {
    if (route === 'edit' && params.type === 'app') {
      activeSectionId = 'app-edit-view';
    } else {
      activeSectionId = 'dashboard-view';
    }
    if (navPortal) navPortal.classList.remove('active');
    if (navDashboard) navDashboard.classList.add('active');
    if (navControl) navControl.classList.remove('active');
  } else {
    activeSectionId = 'portal-view';
    if (navPortal) navPortal.classList.add('active');
    if (navDashboard) navDashboard.classList.remove('active');
    if (navControl) navControl.classList.remove('active');
  }

  showSection(activeSectionId);
  closeAllModals();

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

async function handleDataChange() {
  await loadAllData();
  
  initPortal(allApps, globalSettings.categories || {});
  renderDashboardAppsList(dashboardApps, globalSettings.categories || {});
  renderCategoriesBar(globalSettings.categories || {});
  
  handleRouting();
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadAllData();

  initDashboard(handleDataChange);
  initPortal(allApps, globalSettings.categories || {});
  renderDashboardAppsList(dashboardApps, globalSettings.categories || {});
  renderCategoriesBar(globalSettings.categories || {});

  initRouter(handleRouting);
});
