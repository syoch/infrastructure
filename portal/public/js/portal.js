import { getCategoryColorStyle, escapeHTML, safeURL } from './ui.js';

let portalSortDirection = null; // null, 'asc', 'desc'

export function renderPortalApps(apps, categories = {}) {
  const appsTableBody = document.getElementById('apps-table-body');
  if (!appsTableBody) return;
  
  if (apps.length === 0) {
    appsTableBody.innerHTML = `
      <tr class="empty-row">
        <td colspan="5">
          <div class="empty-state">
            <p>該当するアプリが見つかりません。</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  appsTableBody.innerHTML = '';
  
  apps.forEach(app => {
    const isSelfHosted = app.overrideSource === 'HTML' && app.url.includes('/scrape-index.html');
    const badgeClass = isSelfHosted ? 'badge-self-hosted' : 'badge-official';
    const badgeText = isSelfHosted ? 'Self-Hosted' : 'Official';
    
    let resolvedUrl = app.url;
    if (resolvedUrl && resolvedUrl.startsWith('/')) {
      resolvedUrl = window.location.origin + resolvedUrl;
    }
    const appUrlEncoded = encodeURIComponent(resolvedUrl);
    const obtainiumDeepLink = `obtainium://${appUrlEncoded}`;
    
    const versionStr = isSelfHosted && app._version ? escapeHTML(app._version) : 'Tracked on source';
      
    let actionButtons = '';
    if (isSelfHosted) {
      const downloadUrl = app._latest_apk_id ? `/api/apps/download/${app._latest_apk_id}/${encodeURIComponent(app._filename || 'download.apk')}` : `/scrape-index.html`;
      actionButtons = `
        <div class="table-actions">
          <a href="${safeURL(obtainiumDeepLink)}" class="btn btn-primary btn-sm">
            <span>Obtainium に追加</span>
          </a>
          <a href="${safeURL(downloadUrl)}" class="btn btn-secondary btn-sm" title="Direct APK Download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-icon" style="width:14px; height:14px">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
          </a>
        </div>
      `;
    } else {
      actionButtons = `
        <div class="table-actions">
          <a href="${safeURL(obtainiumDeepLink)}" class="btn btn-primary btn-sm" style="width: 100%">
            <span>Obtainium に追加</span>
          </a>
        </div>
      `;
    }

    let categoriesHtml = '';
    if (app.categories && app.categories.length > 0) {
      categoriesHtml = app.categories.map(cat => {
        const colorCode = categories[cat];
        const colorStyle = getCategoryColorStyle(colorCode);
        return `<span class="category-tag" style="${colorStyle}">${escapeHTML(cat)}</span>`;
      }).join(' ');
    } else {
      categoriesHtml = '<span class="category-tag tag-none">未設定</span>';
    }

    const row = document.createElement('tr');
    row.className = 'app-row';
    row.innerHTML = `
      <td class="col-name">
        <div class="app-identity">
          <span class="app-name-text">${escapeHTML(app.name)}</span>
          <span class="app-package-text">${escapeHTML(app.id)}</span>
        </div>
      </td>
      <td class="col-category">
        <div class="category-tags">${categoriesHtml}</div>
      </td>
      <td class="col-source">
        <div class="source-identity">
          <span class="badge ${badgeClass}">${badgeText}</span>
          <span class="source-type">${escapeHTML(app.overrideSource || 'Auto Detect')}</span>
        </div>
      </td>
      <td class="col-version"><span class="version-text">${versionStr}</span></td>
      <td class="col-actions">${actionButtons}</td>
    `;
    
    appsTableBody.appendChild(row);
  });
}

function applyFilterAndSort(allApps, categories) {
  const searchInput = document.getElementById('app-search-input');
  const categoryFilter = document.getElementById('portal-category-filter');
  
  let filtered = [...allApps];
  
  // 1. Search Filter
  if (searchInput) {
    const query = searchInput.value.toLowerCase().trim();
    if (query) {
      filtered = filtered.filter(app => {
        const name = (app.name || '').toLowerCase();
        const id = (app.id || '').toLowerCase();
        return name.includes(query) || id.includes(query);
      });
    }
  }
  
  // 2. Category Filter
  if (categoryFilter) {
    const selectedCategory = categoryFilter.value;
    if (selectedCategory) {
      filtered = filtered.filter(app => (app.categories || []).includes(selectedCategory));
    }
  }
  
  // 3. Sorting by Category
  if (portalSortDirection === 'asc') {
    filtered.sort((a, b) => {
      const catA = (a.categories || []).join(', ');
      const catB = (b.categories || []).join(', ');
      return catA.localeCompare(catB, 'ja');
    });
  } else if (portalSortDirection === 'desc') {
    filtered.sort((a, b) => {
      const catA = (a.categories || []).join(', ');
      const catB = (b.categories || []).join(', ');
      return catB.localeCompare(catA, 'ja');
    });
  }
  
  renderPortalApps(filtered, categories);
}

function updateSortIndicator() {
  const sortIcon = document.getElementById('portal-sort-icon');
  if (!sortIcon) return;
  if (portalSortDirection === 'asc') {
    sortIcon.textContent = '▲';
  } else if (portalSortDirection === 'desc') {
    sortIcon.textContent = '▼';
  } else {
    sortIcon.textContent = '↕';
  }
}

function populateCategoryFilter(allApps) {
  const categoryFilter = document.getElementById('portal-category-filter');
  if (!categoryFilter) return;
  
  const uniqueCategories = new Set();
  allApps.forEach(app => {
    (app.categories || []).forEach(cat => {
      uniqueCategories.add(cat);
    });
  });
  
  categoryFilter.innerHTML = '<option value="">すべてのカテゴリ</option>';
  Array.from(uniqueCategories).sort().forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    categoryFilter.appendChild(opt);
  });
}

export function initPortal(allApps, categories = {}) {
  const searchInput = document.getElementById('app-search-input');
  const categoryFilter = document.getElementById('portal-category-filter');
  const sortCategoryHeader = document.getElementById('portal-sort-category');

  // Reset sorting state on page load/re-init
  portalSortDirection = null;
  updateSortIndicator();

  // Populate category filter dropdown
  populateCategoryFilter(allApps);

  if (searchInput) {
    if (!searchInput.dataset.hasListener) {
      searchInput.value = '';
      searchInput.addEventListener('input', () => {
        applyFilterAndSort(allApps, categories);
      });
      searchInput.dataset.hasListener = 'true';
    }
  }

  if (categoryFilter) {
    categoryFilter.addEventListener('change', () => {
      applyFilterAndSort(allApps, categories);
    });
  }

  if (sortCategoryHeader && !sortCategoryHeader.dataset.hasListener) {
    sortCategoryHeader.addEventListener('click', () => {
      if (portalSortDirection === null) {
        portalSortDirection = 'asc';
      } else if (portalSortDirection === 'asc') {
        portalSortDirection = 'desc';
      } else {
        portalSortDirection = null;
      }
      updateSortIndicator();
      applyFilterAndSort(allApps, categories);
    });
    sortCategoryHeader.dataset.hasListener = 'true';
  }

  applyFilterAndSort(allApps, categories);
}
