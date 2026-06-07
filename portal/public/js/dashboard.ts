import {
  saveApp,
  deleteApp,
  saveSettings,
  compileSettings,
  uploadLocalAPK,
  deleteLocalAPK,
  importObtainiumConfig,
  restoreBackup,
  App,
  Settings,
  SaveAppPayload,
} from './api.js';
import {
  showToast,
  applyCategoryStyleToElement,
  getCategoryColorStyle,
  getCategoryModalColorPreview,
  colorIntToHex,
  parseHexToColorInt,
  escapeHTML,
  validateUrlSourceMatch,
  detectSourceFromUrl,
} from './ui.js';

type DashboardApp = App;

type SortDirection = 'asc' | 'desc' | null;

let dashboardApps: DashboardApp[] = [];
let globalSettings: Partial<Settings> = {};
let onDataChangedCallback: (() => Promise<void>) | null = null;
let dashboardSortDirection: SortDirection = null;
let saveConfirmPending = false;

interface CustomToastElement extends HTMLElement {
  timeoutId?: ReturnType<typeof setTimeout>;
}

function showCustomToast(msg: string, type: 'info' | 'success' | 'error' | 'warning' = 'info', duration = 3000): void {
  let toast = document.getElementById('custom-toast') as CustomToastElement | null;
  if (!toast) {
    toast = document.createElement('div') as CustomToastElement;
    toast.id = 'custom-toast';
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.fontWeight = '600';
    toast.style.fontSize = '0.85rem';
    toast.style.padding = '10px 20px';
    toast.style.borderRadius = '50px';
    toast.style.zIndex = '9999';
    toast.style.transition = 'opacity 0.3s ease';
    document.body.appendChild(toast);
  }

  if (type === 'success') {
    toast.style.background = 'var(--accent-success)';
    toast.style.color = '#000';
    toast.style.boxShadow = '0 4px 12px rgba(0, 230, 118, 0.3)';
  } else if (type === 'error') {
    toast.style.background = '#ff5252';
    toast.style.color = '#fff';
    toast.style.boxShadow = '0 4px 12px rgba(255, 82, 82, 0.3)';
  } else {
    toast.style.background = 'var(--accent-secondary)';
    toast.style.color = '#000';
    toast.style.boxShadow = '0 4px 12px rgba(0, 229, 255, 0.3)';
  }

  toast.textContent = msg;
  toast.style.opacity = '1';
  toast.style.pointerEvents = 'auto';

  if (toast.timeoutId) {
    clearTimeout(toast.timeoutId);
  }
  toast.timeoutId = setTimeout(() => {
    toast!.style.opacity = '0';
    toast!.style.pointerEvents = 'none';
  }, duration);
}

export function updateDashboardState(apps: DashboardApp[], settings: Partial<Settings>): void {
  dashboardApps = apps;
  globalSettings = settings;
  loadGlobalSettingsUI();
}

function loadGlobalSettingsUI(): void {
  const themeSelect = document.getElementById('global-setting-theme') as HTMLSelectElement | null;
  const checkIntervalInput = document.getElementById('global-setting-check-interval') as HTMLInputElement | null;
  const checkOnStartupCheckbox = document.getElementById('global-setting-check-on-startup') as HTMLInputElement | null;
  const prereleaseCheckbox = document.getElementById('global-setting-prerelease') as HTMLInputElement | null;
  const allowSourceChangeCheckbox = document.getElementById('global-setting-allow-source-change') as HTMLInputElement | null;
  const restrictNotificationCheckbox = document.getElementById('global-setting-restrict-notification') as HTMLInputElement | null;

  if (themeSelect) themeSelect.value = globalSettings.theme || 'system';
  if (checkIntervalInput)
    checkIntervalInput.value =
      globalSettings.checkInterval !== undefined && globalSettings.checkInterval !== null
        ? String(globalSettings.checkInterval)
        : '';

  if (checkOnStartupCheckbox) checkOnStartupCheckbox.checked = !!globalSettings.checkOnStartup;
  if (prereleaseCheckbox) prereleaseCheckbox.checked = !!globalSettings.includePreReleases;
  if (allowSourceChangeCheckbox) allowSourceChangeCheckbox.checked = !!globalSettings.allowSourceChange;
  if (restrictNotificationCheckbox)
    restrictNotificationCheckbox.checked = !!globalSettings.backgroundRestrictedNotification;
}

function renderCategoryCheckboxes(containerId: string, activeCategories: string[]): void {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const registeredCategories = Object.keys(globalSettings.categories || {});
  if (registeredCategories.length === 0) {
    container.innerHTML =
      '<div style="color: var(--color-text-muted); font-size: 0.8rem; padding: 4px 0;">登録済みのカテゴリがありません。</div>';
    return;
  }

  registeredCategories.forEach((cat) => {
    const label = document.createElement('label');
    label.style.display = 'flex';
    label.style.alignItems = 'center';
    label.style.gap = '8px';
    label.style.cursor = 'pointer';
    label.style.fontSize = '0.85rem';

    const isChecked = activeCategories.includes(cat);
    label.innerHTML = `
      <input type="checkbox" name="app-category-checkbox" value="${escapeHTML(cat)}" ${isChecked ? 'checked' : ''} style="cursor: pointer;">
      <span>${escapeHTML(cat)}</span>
    `;
    container.appendChild(label);
  });
}

export function renderDashboardAppsList(apps: DashboardApp[], categories: Record<string, number> = {}): void {
  const dashboardAppsList = document.getElementById('dashboard-apps-list');
  if (!dashboardAppsList) return;
  dashboardAppsList.innerHTML = '';

  if (apps.length === 0) {
    dashboardAppsList.innerHTML = `
      <tr>
        <td colspan="4" style="text-align:center; padding: 32px; color: var(--color-text-muted);">
          登録されているアプリがありません。新規アプリ登録から追加してください。
        </td>
      </tr>
    `;
    return;
  }

  let sortedApps = [...apps];
  if (dashboardSortDirection === 'asc') {
    sortedApps.sort((a, b) => {
      const catA = (a.categories || []).join(', ');
      const catB = (b.categories || []).join(', ');
      return catA.localeCompare(catB, 'ja');
    });
  } else if (dashboardSortDirection === 'desc') {
    sortedApps.sort((a, b) => {
      const catA = (a.categories || []).join(', ');
      const catB = (b.categories || []).join(', ');
      return catB.localeCompare(catA, 'ja');
    });
  }

  sortedApps.forEach((app) => {
    const row = document.createElement('tr');
    row.className = 'app-row';

    const categoriesHtml =
      (app.categories || [])
        .map((cat) => {
          const colorCode = categories[cat];
          const colorStyle = getCategoryColorStyle(colorCode);
          return `<span class="category-tag" data-cat="${escapeHTML(cat)}" style="${colorStyle}">${escapeHTML(cat)}</span>`;
        })
        .join(' ') || '<span class="color-text-muted">-</span>';

    // URL/source mismatch warning
    const { valid, warning } = validateUrlSourceMatch(app.url, app.overrideSource);
    let sourceLabel = app.overrideSource || 'Auto';
    let warningHtml = '';
    if (!valid && warning) {
      sourceLabel = `⚠️ ${app.overrideSource}`;
      warningHtml = `<div class="app-warning-text" title="${escapeHTML(warning)}">${escapeHTML(warning)}</div>`;
    }

    row.innerHTML = `
      <td>
        <div class="app-identity">
          <span class="app-name-text">${escapeHTML(app.name)}</span>
          <span class="app-package-text">${escapeHTML(app.id)}</span>
        </div>
      </td>
      <td><div class="category-tags">${categoriesHtml}</div></td>
      <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
        <span style="color: var(--accent-secondary); font-size: 0.85rem;">${escapeHTML(app.url)}</span>
        ${warningHtml}
      </td>
      <td style="text-align: right;">
        <div class="table-actions" style="justify-content: flex-end; gap: 8px;">
          <span class="app-source-badge">${escapeHTML(sourceLabel)}</span>
          <button class="btn btn-secondary btn-sm quick-edit-btn" data-id="${escapeHTML(app.id)}">簡易編集</button>
          <button class="btn btn-secondary btn-sm delete-app-btn" data-id="${escapeHTML(app.id)}" style="color: #ff5252; border-color: rgba(255, 82, 82, 0.2);">削除</button>
        </div>
      </td>
    `;

    row.addEventListener('click', (e: Event) => {
      const target = e.target as HTMLElement;
      if (target.closest('button') || target.closest('.category-tag')) return;
      window.location.hash = `#edit?type=quick-app&id=${encodeURIComponent(app.id)}`;
    });

    dashboardAppsList.appendChild(row);
  });

  dashboardAppsList.querySelectorAll('.category-tag').forEach((tag) => {
    tag.addEventListener('click', (e: Event) => {
      e.stopPropagation();
      const cat = (e.currentTarget as HTMLElement).getAttribute('data-cat');
      window.location.hash = `#edit?type=category&id=${encodeURIComponent(cat || '')}`;
    });
  });

  dashboardAppsList.querySelectorAll('.quick-edit-btn').forEach((btn) => {
    btn.addEventListener('click', (e: Event) => {
      e.stopPropagation();
      const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
      window.location.hash = `#edit?type=quick-app&id=${encodeURIComponent(id || '')}`;
    });
  });

  dashboardAppsList.querySelectorAll('.delete-app-btn').forEach((btn) => {
    btn.addEventListener('click', (e: Event) => {
      e.stopPropagation();
      const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
      if (id) handleDeleteApp(id);
    });
  });
}

export function renderCategoriesBar(categories: Record<string, number>): void {
  const dashboardCategoriesBar = document.getElementById('dashboard-categories-bar');
  if (!dashboardCategoriesBar) return;

  const addButton = document.getElementById('add-category-btn');
  dashboardCategoriesBar.innerHTML = '';

  Object.entries(categories).forEach(([name, color]) => {
    const chip = document.createElement('span');
    chip.className = 'category-tag interactive-tag';
    chip.textContent = name;
    chip.setAttribute('data-name', name);

    applyCategoryStyleToElement(chip, color);

    chip.addEventListener('click', () => {
      window.location.hash = `#edit?type=category&id=${encodeURIComponent(name)}`;
    });

    dashboardCategoriesBar.appendChild(chip);
  });

  if (addButton) dashboardCategoriesBar.appendChild(addButton);
}

export function openQuickAppModal(id: string | null): void {
  const appModal = document.getElementById('app-modal');
  const quickAppTitle = document.getElementById('app-modal-title');
  const quickAppSubtitle = document.getElementById('app-modal-subtitle');
  const quickAppEditMode = document.getElementById('quick-app-edit-mode') as HTMLInputElement | null;
  const quickAppId = document.getElementById('quick-app-id') as HTMLInputElement | null;
  const quickAppName = document.getElementById('quick-app-name') as HTMLInputElement | null;
  const quickAppUrl = document.getElementById('quick-app-url') as HTMLInputElement | null;
  const quickAppSource = document.getElementById('quick-app-source') as HTMLSelectElement | null;
  const quickAppCategories = document.getElementById('quick-app-categories');
  const quickDetailBtn = document.getElementById('quick-detail-btn') as HTMLButtonElement | null;

  if (appModal) appModal.classList.add('active');

  if (!id) {
    if (quickAppTitle) quickAppTitle.textContent = 'アプリを登録する';
    if (quickAppSubtitle) quickAppSubtitle.textContent = 'アプリの基本情報を入力してください。';
    if (quickAppEditMode) quickAppEditMode.value = 'false';

    if (quickAppId) {
      quickAppId.value = '';
      quickAppId.disabled = false;
    }
    if (quickAppName) quickAppName.value = '';
    if (quickAppUrl) quickAppUrl.value = '';
    if (quickAppSource) quickAppSource.value = 'GitHub';
    renderCategoryCheckboxes('quick-categories-checkboxes', []);
    if (quickAppCategories) (quickAppCategories as HTMLInputElement).value = '';
    if (quickDetailBtn) quickDetailBtn.style.display = 'none';
  } else {
    const app = dashboardApps.find((a) => a.id === id);
    if (!app) return;

    if (quickAppTitle) quickAppTitle.textContent = 'アプリ簡易編集';
    if (quickAppSubtitle) quickAppSubtitle.textContent = `パッケージ ID: ${app.id}`;
    if (quickAppEditMode) quickAppEditMode.value = 'true';

    if (quickAppId) {
      quickAppId.value = app.id;
      quickAppId.disabled = true;
    }
    if (quickAppName) quickAppName.value = app.name;
    if (quickAppUrl) quickAppUrl.value = app.url || '';
    if (quickAppSource) quickAppSource.value = app.overrideSource || 'GitHub';
    renderCategoryCheckboxes('quick-categories-checkboxes', app.categories || []);
    if (quickAppCategories) (quickAppCategories as HTMLInputElement).value = '';

    if (quickDetailBtn) {
      quickDetailBtn.style.display = 'inline-flex';
      quickDetailBtn.onclick = () => {
        closeAllModals();
        window.location.hash = `#edit?type=app&id=${encodeURIComponent(app.id)}`;
      };
    }
  }

  if (quickAppSource && quickAppUrl) {
    if (quickAppSource.value === 'HTML') {
      quickAppUrl.value = '/scrape-index.html';
      quickAppUrl.disabled = true;
    } else {
      quickAppUrl.disabled = false;
    }
  }
}

export function showDetailedEdit(id: string): void {
  const dashboardView = document.getElementById('dashboard-view');
  const appEditView = document.getElementById('app-edit-view');

  const editAppIdHidden = document.getElementById('edit-app-id-hidden') as HTMLInputElement | null;
  const editAppName = document.getElementById('edit-app-name') as HTMLInputElement | null;
  const editAppId = document.getElementById('edit-app-id') as HTMLInputElement | null;
  const editAppUrl = document.getElementById('edit-app-url') as HTMLInputElement | null;
  const editAppSource = document.getElementById('edit-app-source') as HTMLSelectElement | null;
  const editAppCategories = document.getElementById('edit-app-categories');
  const editSettingPrerelease = document.getElementById('edit-setting-prerelease') as HTMLInputElement | null;
  const editSettingFallback = document.getElementById('edit-setting-fallback') as HTMLInputElement | null;
  const editSettingVersionDetect = document.getElementById('edit-setting-version-detect') as HTMLInputElement | null;
  const editDeleteBtn = document.getElementById('edit-delete-btn') as HTMLButtonElement | null;

  const app = dashboardApps.find((a) => a.id === id);
  if (!app) {
    window.location.hash = '#list';
    return;
  }

  saveConfirmPending = false;

  if (dashboardView) dashboardView.style.display = 'none';
  if (appEditView) appEditView.style.display = 'block';

  if (editAppIdHidden) editAppIdHidden.value = app.id;
  if (editAppName) editAppName.value = app.name;
  if (editAppId) editAppId.value = app.id;
  if (editAppUrl) editAppUrl.value = app.url || '';
  if (editAppSource) editAppSource.value = app.overrideSource || '';

  if (editAppSource && editAppUrl) {
    if (editAppSource.value === 'HTML') {
      editAppUrl.value = '/scrape-index.html';
      editAppUrl.disabled = true;
    } else {
      editAppUrl.disabled = false;
    }
  }

  function updateSourceRecommendation(): void {
    const rec = document.getElementById('source-recommendation');
    if (!rec || !editAppUrl || !editAppSource) return;
    const url = editAppUrl.value.trim();
    const source = editAppSource.value;
    if (!source) {
      const detected = detectSourceFromUrl(url);
      if (detected) {
        rec.textContent = `💡 この URL は ${detected} として自動検出されます`;
        (rec as HTMLElement).style.display = 'block';
      } else {
        (rec as HTMLElement).style.display = 'none';
      }
    } else {
      const { valid, warning } = validateUrlSourceMatch(url, source);
      if (!valid && warning) {
        rec.textContent = `⚠️ ${warning}`;
        (rec as HTMLElement).style.display = 'block';
      } else {
        (rec as HTMLElement).style.display = 'none';
      }
    }
  }

  updateSourceRecommendation();
  if (editAppUrl) editAppUrl.addEventListener('input', updateSourceRecommendation);
  if (editAppSource) editAppSource.addEventListener('change', updateSourceRecommendation);

  renderCategoryCheckboxes('detailed-categories-checkboxes', app.categories || []);
  if (editAppCategories) (editAppCategories as HTMLInputElement).value = '';

  const addSettings = app.additionalSettings || {};
  if (editSettingPrerelease) editSettingPrerelease.checked = addSettings.includePrereleases || false;
  if (editSettingFallback) editSettingFallback.checked = addSettings.fallbackToOlderReleases !== false;
  if (editSettingVersionDetect) editSettingVersionDetect.checked = addSettings.versionDetection !== false;

  const apkFilterInput = document.getElementById('edit-setting-apk-filter') as HTMLInputElement | null;
  const invertFilterInput = document.getElementById('edit-setting-invert-filter') as HTMLInputElement | null;
  if (apkFilterInput) apkFilterInput.value = addSettings.apkFilterRegEx || '';
  if (invertFilterInput) invertFilterInput.checked = addSettings.invertAPKFilter || false;

  if (editDeleteBtn) editDeleteBtn.onclick = () => handleDeleteApp(app.id);

  const selfHostedApkCard = document.getElementById('self-hosted-apk-card');
  const apkDropzone = document.getElementById('apk-dropzone');
  const apkFileInput = document.getElementById('apk-file-input') as HTMLInputElement | null;
  const apkDropzoneText = document.getElementById('apk-dropzone-text');
  const apkVersionInput = document.getElementById('apk-version-input') as HTMLInputElement | null;
  const apkArchSelect = document.getElementById('apk-arch-select') as HTMLSelectElement | null;
  const apkUploadBtn = document.getElementById('apk-upload-btn') as HTMLButtonElement | null;

  const toggleSelfHostedCard = (source: string): void => {
    if (selfHostedApkCard) {
      (selfHostedApkCard as HTMLElement).style.display = source === 'HTML' ? 'block' : 'none';
    }
  };

  toggleSelfHostedCard(app.overrideSource || 'GitHub');

  if (editAppSource) {
    editAppSource.onchange = (e: Event) => {
      toggleSelfHostedCard((e.target as HTMLSelectElement).value);
    };
  }

  if (apkFileInput) apkFileInput.value = '';
  if (apkDropzoneText) {
    apkDropzoneText.textContent =
      'ここに APK ファイルをドラッグ＆ドロップするか、クリックしてファイルを選択';
  }
  if (apkVersionInput) {
    const latestApk = app.apks && app.apks.length > 0 ? app.apks[app.apks.length - 1] : null;
    apkVersionInput.value = latestApk ? latestApk.version : '';
  }
  if (apkArchSelect) apkArchSelect.value = 'none';

  const renderApkList = (): void => {
    const tbody = document.getElementById('apk-list-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!app.apks || app.apks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; color: var(--color-text-muted); padding: 16px;">
            登録されているセルフホスト APK がありません。
          </td>
        </tr>
      `;
      return;
    }

    app.apks.forEach((apk) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${escapeHTML(apk.version)}</td>
        <td>${escapeHTML(apk.architecture || '指定なし/自動')}</td>
        <td class="apk-hash-text" title="${escapeHTML(apk.file_hash)}">${escapeHTML(apk.file_hash.substring(0, 16))}...</td>
        <td style="text-align: right;">
          <button class="delete-apk-btn" data-apk-id="${apk.id}" data-file-hash="${apk.file_hash}">削除</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll('.delete-apk-btn').forEach((btn) => {
      btn.addEventListener('click', async (e: Event) => {
        const target = e.currentTarget as HTMLButtonElement;
        const apkId = parseInt(target.getAttribute('data-apk-id') || '0', 10);
        const fileHash = target.getAttribute('data-file-hash');
        if (confirm('この APK を削除しますか？')) {
          try {
            await deleteLocalAPK(String(apkId));
            showCustomToast('APK を削除しました。', 'success');
            if (onDataChangedCallback) {
              await onDataChangedCallback();
            }
          } catch (err) {
            console.error(err);
            showCustomToast(err instanceof Error ? err.message : 'APK の削除に失敗しました。', 'error');
          }
        }
      });
    });
  };

  renderApkList();

  if (apkDropzone && apkFileInput) {
    apkDropzone.addEventListener('click', (e: Event) => {
      if (e.target !== apkFileInput) {
        apkFileInput.click();
      }
    });

    apkDropzone.addEventListener('dragover', (e: DragEvent) => {
      e.preventDefault();
      apkDropzone.classList.add('dragover');
    });

    apkDropzone.addEventListener('dragleave', () => {
      apkDropzone.classList.remove('dragover');
    });

    apkDropzone.addEventListener('drop', (e: DragEvent) => {
      e.preventDefault();
      apkDropzone.classList.remove('dragover');
      if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        if (file.name.endsWith('.apk')) {
          apkFileInput.files = e.dataTransfer.files;
          updateFileInputDisplay(file);
        } else {
          showCustomToast('APK ファイルのみアップロード可能です。', 'error');
        }
      }
    });

    apkFileInput.addEventListener('change', () => {
      if (apkFileInput.files && apkFileInput.files.length > 0) {
        updateFileInputDisplay(apkFileInput.files[0]);
      }
    });
  }

  function updateFileInputDisplay(file: File): void {
    if (apkDropzoneText) {
      apkDropzoneText.innerHTML = `選択されたファイル: <span class="upload-dropzone-filename">${escapeHTML(file.name)}</span> (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
    }
    const name = file.name;
    const versionMatch = name.match(/v?(\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?)/i);
    if (versionMatch && apkVersionInput && !apkVersionInput.value) {
      apkVersionInput.value = versionMatch[1];
    }
    if (apkArchSelect) {
      if (name.includes('arm64-v8a')) apkArchSelect.value = 'arm64-v8a';
      else if (name.includes('armeabi-v7a')) apkArchSelect.value = 'armeabi-v7a';
      else if (name.includes('x86_64')) apkArchSelect.value = 'x86_64';
      else if (name.includes('x86')) apkArchSelect.value = 'x86';
      else if (name.includes('universal')) apkArchSelect.value = 'universal';
    }
  }

  if (apkUploadBtn) {
    apkUploadBtn.onclick = async () => {
      const file = apkFileInput?.files ? apkFileInput.files[0] : null;
      if (!file) {
        showCustomToast('アップロードする APK ファイルを選択してください。', 'error');
        return;
      }

      if (!apkVersionInput) return;
      const version = apkVersionInput.value.trim();
      if (!version) {
        showCustomToast('バージョンを入力してください。', 'error');
        return;
      }

      const architecture = apkArchSelect?.value || 'none';
      const formData = new FormData();
      formData.append('app_id', app.id);
      formData.append('version', version);
      formData.append('architecture', architecture);
      formData.append('file', file);

      try {
        apkUploadBtn.disabled = true;
        apkUploadBtn.textContent = 'アップロード中...';
        showCustomToast('APK のアップロードを開始しました...', 'info');

        await uploadLocalAPK(formData);
        showCustomToast('APK を正常にアップロード・登録しました。', 'success');

        if (apkFileInput) apkFileInput.value = '';
        if (apkDropzoneText) {
          apkDropzoneText.textContent =
            'ここに APK ファイルをドラッグ＆ドロップするか、クリックしてファイルを選択';
        }
        if (onDataChangedCallback) {
          await onDataChangedCallback();
        }
      } catch (err) {
        console.error(err);
        showCustomToast(err instanceof Error ? err.message : 'APK のアップロードに失敗しました。', 'error');
      } finally {
        apkUploadBtn.disabled = false;
        apkUploadBtn.textContent = 'APK をアップロードして登録する';
      }
    };
  }
}

export function openCategoryModal(name: string | null): void {
  const categoryModal = document.getElementById('category-modal');
  const categoryModalTitle = document.getElementById('category-modal-title');
  const catModalName = document.getElementById('cat-modal-name') as HTMLInputElement | null;
  const catModalColor = document.getElementById('cat-modal-color') as HTMLInputElement | null;
  const catModalColorPreview = document.getElementById('cat-modal-color-preview');
  const categoryAppsList = document.getElementById('category-apps-list');
  const catModalDelete = document.getElementById('cat-modal-delete') as HTMLButtonElement | null;

  const isEdit = !!name;
  if (categoryModal) {
    categoryModal.classList.add('active');
    categoryModal.dataset.mode = isEdit ? 'edit' : 'new';
    categoryModal.dataset.originalName = name || '';
  }

  if (!isEdit) {
    if (categoryModalTitle) categoryModalTitle.textContent = 'カテゴリを作成';
    if (catModalName) catModalName.value = '';
    if (catModalColor) catModalColor.value = '#ff7c4dff';
    if (catModalColorPreview) catModalColorPreview.style.backgroundColor = '#7c4dff';
    if (categoryAppsList) {
      categoryAppsList.innerHTML = `<div style="color: var(--color-text-muted); font-size: 0.8rem; padding: 12px 0;">新しいカテゴリです。保存後、アプリに割り当ててください。</div>`;
    }
    if (catModalDelete) catModalDelete.style.display = 'none';
  } else {
    if (!name) return;
    const color = (globalSettings.categories || {})[name] || 0;
    if (categoryModalTitle) categoryModalTitle.textContent = `カテゴリ "${name}" を編集`;
    if (catModalName) catModalName.value = name;
    if (catModalColor) catModalColor.value = colorIntToHex(color);

    if (catModalColorPreview) catModalColorPreview.style.backgroundColor = getCategoryModalColorPreview(color);

    if (categoryAppsList) {
      categoryAppsList.innerHTML = '';
      if (dashboardApps.length === 0) {
        categoryAppsList.innerHTML = `<div style="color: var(--color-text-muted); font-size: 0.8rem; padding: 12px 0;">登録されているアプリがありません。</div>`;
      } else {
        dashboardApps.forEach((app) => {
          const label = document.createElement('label');
          label.className = 'modal-app-item';
          label.style.display = 'flex';
          label.style.alignItems = 'center';
          label.style.gap = '10px';
          label.style.cursor = 'pointer';
          label.style.padding = '6px 8px';
          label.style.borderRadius = '4px';
          label.style.transition = 'background-color 0.2s';

          const isChecked = (app.categories || []).includes(name);
          label.innerHTML = `
            <input type="checkbox" name="cat-app-checkbox" data-app-id="${escapeHTML(app.id)}" ${isChecked ? 'checked' : ''} style="cursor: pointer;">
            <div style="display: flex; flex-direction: column; cursor: pointer; flex: 1;">
              <span class="app-name-display" style="font-weight: 500; font-size: 0.85rem;">${escapeHTML(app.name)}</span>
              <span class="app-pkg-display" style="font-size: 0.7rem; color: var(--color-text-muted);">${escapeHTML(app.id)}</span>
            </div>
          `;
          label.onmouseover = () => {
            label.style.backgroundColor = 'rgba(255,255,255,0.05)';
          };
          label.onmouseout = () => {
            label.style.backgroundColor = '';
          };
          categoryAppsList.appendChild(label);
        });
      }
    }

    if (catModalDelete) {
      catModalDelete.style.display = 'inline-flex';
      catModalDelete.onclick = () => handleDeleteCategory(name);
    }
  }
}

export function closeAllModals(): void {
  const appModal = document.getElementById('app-modal');
  const categoryModal = document.getElementById('category-modal');
  if (appModal) appModal.classList.remove('active');
  if (categoryModal) categoryModal.classList.remove('active');
}

async function handleDeleteApp(id: string): Promise<void> {
  if (!confirm(`アプリ '${id}' を削除してもよろしいですか？`)) return;
  try {
    await deleteApp(id);
    window.location.hash = '#list';
    if (onDataChangedCallback) {
      await onDataChangedCallback();
    }
  } catch (err) {
    console.error(err);
    alert('アプリの削除に失敗しました。');
  }
}

async function handleDeleteCategory(name: string): Promise<void> {
  if (
    !confirm(
      `カテゴリ "${name}" を削除してもよろしいですか？ (登録アプリ自体のカテゴリ割り当ては別途変更が必要です)`
    )
  )
    return;
  try {
    const updatedCategories = { ...(globalSettings.categories || {}) };
    delete updatedCategories[name];
    await saveSettings({ categories: updatedCategories });
    window.location.hash = '#list';
    if (onDataChangedCallback) {
      await onDataChangedCallback();
    }
  } catch (err) {
    console.error(err);
    alert('カテゴリの削除に失敗しました。');
  }
}

function updateDashboardSortIndicator(): void {
  const sortIcon = document.getElementById('dashboard-sort-icon');
  if (!sortIcon) return;
  if (dashboardSortDirection === 'asc') sortIcon.textContent = '▲';
  else if (dashboardSortDirection === 'desc') sortIcon.textContent = '▼';
  else sortIcon.textContent = '↕';
}

export function initDashboard(onDataChanged: () => Promise<void>): void {
  onDataChangedCallback = onDataChanged;

  const quickAppForm = document.getElementById('quick-app-form');
  const quickAppId = document.getElementById('quick-app-id') as HTMLInputElement | null;
  const quickAppName = document.getElementById('quick-app-name') as HTMLInputElement | null;
  const quickAppUrl = document.getElementById('quick-app-url') as HTMLInputElement | null;
  const quickAppSource = document.getElementById('quick-app-source') as HTMLSelectElement | null;
  const quickAppCategories = document.getElementById('quick-app-categories') as HTMLInputElement | null;
  const quickCancelBtn = document.getElementById('quick-cancel-btn') as HTMLButtonElement | null;

  const detailedAppForm = document.getElementById('detailed-app-form');
  const editAppIdHiddenReal = document.getElementById('edit-app-id-hidden') as HTMLInputElement | null;
  const editAppName = document.getElementById('edit-app-name') as HTMLInputElement | null;
  const editAppUrl = document.getElementById('edit-app-url') as HTMLInputElement | null;
  const editAppSource = document.getElementById('edit-app-source') as HTMLSelectElement | null;
  const editAppCategories = document.getElementById('edit-app-categories') as HTMLInputElement | null;
  const editSettingPrerelease = document.getElementById('edit-setting-prerelease') as HTMLInputElement | null;
  const editSettingFallback = document.getElementById('edit-setting-fallback') as HTMLInputElement | null;
  const editSettingVersionDetect = document.getElementById('edit-setting-version-detect') as HTMLInputElement | null;
  const editBackBtn = document.getElementById('edit-back-btn') as HTMLButtonElement | null;

  const categoryModalForm = document.getElementById('category-modal-form');
  const catModalName = document.getElementById('cat-modal-name') as HTMLInputElement | null;
  const catModalColor = document.getElementById('cat-modal-color') as HTMLInputElement | null;
  const catModalColorPreview = document.getElementById('cat-modal-color-preview') as HTMLElement | null;

  const compileBtn = document.getElementById('compile-btn') as HTMLButtonElement | null;
  const compileToast = document.getElementById('compile-toast');

  const addAppBtn = document.getElementById('add-app-btn') as HTMLButtonElement | null;
  const addCategoryBtn = document.getElementById('add-category-btn') as HTMLButtonElement | null;

  const appModalClose = document.getElementById('app-modal-close') as HTMLButtonElement | null;
  const categoryModalClose = document.getElementById('category-modal-close') as HTMLButtonElement | null;
  const appModal = document.getElementById('app-modal');
  const categoryModal = document.getElementById('category-modal');

  if (quickAppSource && quickAppUrl) {
    quickAppSource.addEventListener('change', () => {
      if (quickAppSource.value === 'HTML') {
        quickAppUrl.value = '/scrape-index.html';
        quickAppUrl.disabled = true;
      } else {
        if (quickAppUrl.value === '/scrape-index.html') {
          quickAppUrl.value = '';
        }
        quickAppUrl.disabled = false;
      }
    });
  }

  if (editAppSource && editAppUrl) {
    editAppSource.addEventListener('change', () => {
      if (editAppSource.value === 'HTML') {
        editAppUrl.value = '/scrape-index.html';
        editAppUrl.disabled = true;
      } else {
        if (editAppUrl.value === '/scrape-index.html') {
          editAppUrl.value = '';
        }
        editAppUrl.disabled = false;
      }
    });
  }

  if (quickAppForm) {
    quickAppForm.addEventListener('submit', async (e: Event) => {
      e.preventDefault();
      if (!quickAppId || !quickAppName || !quickAppUrl || !quickAppSource) return;

      const appId = quickAppId.value.trim();

      const checkedCategories = Array.from(
        document.querySelectorAll(
          '#quick-categories-checkboxes input[name="app-category-checkbox"]:checked'
        )
      ).map((cb) => (cb as HTMLInputElement).value);

      const customCats = quickAppCategories
        ? quickAppCategories.value
            .split(',')
            .map((c) => c.trim())
            .filter((c) => c.length > 0)
        : [];

      const categories = Array.from(new Set([...checkedCategories, ...customCats]));

      const existingApp: Partial<DashboardApp> = dashboardApps.find((a) => a.id === appId) || {};
      const originalAdditionalSettings = existingApp.additionalSettings || {
        includePrereleases: false,
        fallbackToOlderReleases: true,
        versionDetection: true,
      };

      const appData: SaveAppPayload = {
        id: appId,
        name: quickAppName.value.trim(),
        url: quickAppUrl.value.trim(),
        overrideSource: quickAppSource.value,
        categories: categories,
        additionalSettings: originalAdditionalSettings,
      };

      try {
        await saveApp(appData);
        window.location.hash = '#list';
        if (onDataChangedCallback) {
          await onDataChangedCallback();
        }
      } catch (err) {
        console.error(err);
        alert('保存に失敗しました。');
      }
    });
  }

  if (detailedAppForm) {
    detailedAppForm.addEventListener('submit', async (e: Event) => {
      e.preventDefault();
      if (!editAppIdHiddenReal || !editAppName || !editAppUrl || !editAppSource) return;

      const appId = editAppIdHiddenReal.value;

      const checkedCategories = Array.from(
        document.querySelectorAll(
          '#detailed-categories-checkboxes input[name="app-category-checkbox"]:checked'
        )
      ).map((cb) => (cb as HTMLInputElement).value);

      const customCats = editAppCategories
        ? editAppCategories.value
            .split(',')
            .map((c) => c.trim())
            .filter((c) => c.length > 0)
        : [];

      const categories = Array.from(new Set([...checkedCategories, ...customCats]));

      const currentApp = dashboardApps.find((a) => a.id === appId);
      const appData: SaveAppPayload = {
        id: appId,
        name: editAppName.value,
        url: editAppUrl.value.trim(),
        overrideSource: editAppSource.value || undefined,
        categories: categories,
        additionalSettings: {
          ...(currentApp?.additionalSettings || {}),
          includePrereleases: editSettingPrerelease?.checked || false,
          fallbackToOlderReleases: editSettingFallback?.checked !== false,
          versionDetection: editSettingVersionDetect?.checked !== false,
          apkFilterRegEx:
            (document.getElementById('edit-setting-apk-filter') as HTMLInputElement | null)?.value || '',
          invertAPKFilter:
            (document.getElementById('edit-setting-invert-filter') as HTMLInputElement | null)?.checked || false,
        },
      };

      const { valid } = validateUrlSourceMatch(appData.url, appData.overrideSource);
      if (!valid && !saveConfirmPending) {
        saveConfirmPending = true;
        showCustomToast(
          '⚠️ URL とソース元の組み合わせに問題がある可能性があります。もう一度「保存」を押して確認してください。',
          'warning',
          5000
        );
        return;
      }
      saveConfirmPending = false;

      try {
        await saveApp(appData);
        window.location.hash = '#list';
        if (onDataChangedCallback) {
          await onDataChangedCallback();
        }
      } catch (err) {
        console.error(err);
        alert('詳細設定の保存に失敗しました。');
      }
    });
  }

  if (categoryModalForm) {
    categoryModalForm.addEventListener('submit', async (e: Event) => {
      e.preventDefault();
      if (!catModalName || !catModalColor) return;

      const name = catModalName.value.trim();
      const color = parseHexToColorInt(catModalColor.value);
      if (!name || isNaN(color)) return;

      const categoryModal = document.getElementById('category-modal');
      const isEdit = categoryModal ? categoryModal.dataset.mode === 'edit' : false;
      const originalName = categoryModal ? categoryModal.dataset.originalName : '';
      const isNameChanged = isEdit && originalName && originalName !== name;

      if (isNameChanged) {
        if (globalSettings.categories && globalSettings.categories[name] !== undefined) {
          alert('既に存在するカテゴリ名です。');
          return;
        }
      }

      const updatedCategories = { ...(globalSettings.categories || {}) };
      if (isNameChanged && originalName) {
        delete updatedCategories[originalName];
      }
      updatedCategories[name] = color;

      try {
        await saveSettings({ categories: updatedCategories });

        if (isEdit) {
          const checkboxes = Array.from(
            document.querySelectorAll(
              '#category-apps-list input[name="cat-app-checkbox"]'
            )
          );
          const savePromises: Promise<unknown>[] = [];

          checkboxes.forEach((cb) => {
            const appId = (cb as HTMLInputElement).getAttribute('data-app-id');
            const isChecked = (cb as HTMLInputElement).checked;
            if (!appId) return;
            const app = dashboardApps.find((a) => a.id === appId);
            if (app) {
              let newCats = [...(app.categories || [])];
              let changed = false;

              if (isNameChanged && originalName && newCats.includes(originalName)) {
                newCats = newCats.filter((c) => c !== originalName);
                changed = true;
              }

              const hasNewCat = newCats.includes(name);

              if (isChecked) {
                if (!hasNewCat) {
                  newCats.push(name);
                  changed = true;
                }
              } else {
                if (hasNewCat) {
                  newCats = newCats.filter((c) => c !== name);
                  changed = true;
                }
              }

              if (changed) {
                const updatePayload: Partial<SaveAppPayload> & { id: string; categories: string[] } = {
                  id: app.id,
                  categories: newCats,
                };
                savePromises.push(
                  saveApp({
                    ...app,
                    categories: newCats,
                    additionalSettings: app.additionalSettings,
                  } as SaveAppPayload)
                );
              }
            }
          });

          if (savePromises.length > 0) {
            await Promise.all(savePromises);
          }
        }

        window.location.hash = '#list';
        if (onDataChangedCallback) {
          await onDataChangedCallback();
        }
      } catch (err) {
        console.error(err);
        alert('カテゴリ設定または所属アプリの保存に失敗しました。');
      }
    });
  }

  if (catModalColor && catModalColorPreview) {
    catModalColor.addEventListener('input', (e: Event) => {
      const val = parseHexToColorInt((e.target as HTMLInputElement).value);
      if (!isNaN(val)) {
        catModalColorPreview.style.backgroundColor = getCategoryModalColorPreview(val);
      } else {
        catModalColorPreview.style.backgroundColor = 'transparent';
      }
    });
  }

  if (compileBtn) {
    compileBtn.addEventListener('click', async () => {
      compileBtn.disabled = true;
      compileBtn.style.opacity = '0.6';

      try {
        await compileSettings();
        showToast(compileToast);
        if (onDataChangedCallback) {
          await onDataChangedCallback();
        }
      } catch (err) {
        console.error(err);
        alert('設定のコンパイルに失敗しました。');
      } finally {
        compileBtn.disabled = false;
        compileBtn.style.opacity = '1';
      }
    });
  }

  const importJsonBtn = document.getElementById('import-json-btn') as HTMLButtonElement | null;
  const importJsonFile = document.getElementById('import-json-file') as HTMLInputElement | null;

  if (importJsonBtn && importJsonFile) {
    importJsonBtn.addEventListener('click', () => {
      importJsonFile.click();
    });

    importJsonFile.addEventListener('change', async (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = async (evt) => {
        try {
          const json = JSON.parse(evt.target?.result as string);

          importJsonBtn.disabled = true;
          importJsonBtn.style.opacity = '0.6';
          const span = importJsonBtn.querySelector('span');
          if (span) span.innerText = 'インポート中...';

          const res = await importObtainiumConfig(json);
          alert(res.message || 'インポートが完了しました。');

          importJsonFile.value = '';

          if (onDataChangedCallback) {
            await onDataChangedCallback();
          }
        } catch (err) {
          console.error(err);
          alert('インポートに失敗しました。JSONファイルが壊れているか、内容が正しくありません。');
        } finally {
          importJsonBtn.disabled = false;
          importJsonBtn.style.opacity = '1';
          const span = importJsonBtn.querySelector('span');
          if (span) span.innerText = '📥 JSONインポート';
        }
      };
      reader.readAsText(file);
    });
  }

  if (addAppBtn) {
    addAppBtn.onclick = () => {
      window.location.hash = '#new?type=app';
    };
  }

  if (addCategoryBtn) {
    addCategoryBtn.onclick = () => {
      window.location.hash = '#new?type=category';
    };
  }

  const closeTriggerList: { btn: HTMLElement | null; backdrop: HTMLElement | null }[] = [
    { btn: appModalClose, backdrop: appModal },
    { btn: categoryModalClose, backdrop: categoryModal },
  ];

  closeTriggerList.forEach(({ btn, backdrop }) => {
    if (btn) {
      btn.onclick = () => {
        window.location.hash = '#list';
      };
    }
    if (backdrop) {
      backdrop.onclick = (e: Event) => {
        if (e.target === backdrop) {
          window.location.hash = '#list';
        }
      };
    }
  });

  if (quickCancelBtn) {
    quickCancelBtn.onclick = () => {
      window.location.hash = '#list';
    };
  }

  if (editBackBtn) {
    editBackBtn.onclick = () => {
      window.location.hash = '#list';
    };
  }

  dashboardSortDirection = null;
  updateDashboardSortIndicator();

  const sortCategoryHeader = document.getElementById('dashboard-sort-category');
  if (sortCategoryHeader) {
    sortCategoryHeader.onclick = () => {
      if (dashboardSortDirection === null) dashboardSortDirection = 'asc';
      else if (dashboardSortDirection === 'asc') dashboardSortDirection = 'desc';
      else dashboardSortDirection = null;
      updateDashboardSortIndicator();
      renderDashboardAppsList(dashboardApps, globalSettings.categories || {});
    };
  }

  const escHandler = (e: KeyboardEvent): void => {
    if (e.key === 'Escape') {
      const activeModal = document.querySelector('.modal-backdrop.active');
      if (activeModal) {
        window.location.hash = '#list';
      }
    }
  };
  window.addEventListener('keydown', escHandler);

  const restoreBtn = document.getElementById('restore-btn') as HTMLButtonElement | null;
  const restoreFileInput = document.getElementById('restore-file-input') as HTMLInputElement | null;
  const restoreStrategy = document.getElementById('restore-strategy') as HTMLSelectElement | null;

  if (restoreBtn && restoreFileInput && restoreStrategy) {
    restoreBtn.onclick = () => {
      restoreFileInput.click();
    };

    restoreFileInput.addEventListener('change', async (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      const strategy = restoreStrategy.value;
      const strategyText =
        strategy === 'overwrite'
          ? '【上書き】（既存データがすべて削除され、バックアップの内容に置き換わります）'
          : '【マージ】（既存のデータにバックアップの内容が追加・統合されます）';

      const confirmed = confirm(
        `バックアップファイルの復元を実行します。\n` +
          `選択したファイル: ${file.name}\n` +
          `復元モード: ${strategyText}\n\n` +
          `本当によろしいですか？`
      );

      if (!confirmed) {
        restoreFileInput.value = '';
        return;
      }

      try {
        restoreBtn.disabled = true;
        restoreBtn.style.opacity = '0.6';
        const span = restoreBtn.querySelector('span');
        if (span) span.innerText = 'リストア中...';

        showCustomToast('リストアを実行しています。ページをリロードしないでください...', 'info', 5000);

        await restoreBackup(file, strategy);

        showCustomToast('リストアが完了しました！データを再読み込みします。', 'success', 3000);

        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } catch (err) {
        console.error(err);
        alert(`リストアに失敗しました: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        restoreBtn.disabled = false;
        restoreBtn.style.opacity = '1';
        const span = restoreBtn.querySelector('span');
        if (span) span.innerText = '📥 バックアップからリストア';
        restoreFileInput.value = '';
      }
    });
  }

  const globalSettingsForm = document.getElementById('global-settings-form') as HTMLFormElement | null;
  if (globalSettingsForm) {
    globalSettingsForm.onsubmit = async (e: Event) => {
      e.preventDefault();

      const theme = (document.getElementById('global-setting-theme') as HTMLSelectElement | null)?.value || 'system';
      const checkIntervalVal = (document.getElementById('global-setting-check-interval') as HTMLInputElement | null)?.value || '';
      const checkInterval = checkIntervalVal !== '' ? parseInt(checkIntervalVal, 10) : null;

      const checkOnStartup = (document.getElementById('global-setting-check-on-startup') as HTMLInputElement | null)?.checked || false;
      const includePreReleases = (document.getElementById('global-setting-prerelease') as HTMLInputElement | null)?.checked || false;
      const allowSourceChange = (document.getElementById('global-setting-allow-source-change') as HTMLInputElement | null)?.checked || false;
      const backgroundRestrictedNotification =
        (document.getElementById('global-setting-restrict-notification') as HTMLInputElement | null)?.checked || false;

      const payload = {
        theme,
        checkInterval,
        checkOnStartup,
        includePreReleases,
        allowSourceChange,
        backgroundRestrictedNotification,
      };

      try {
        const submitBtn = globalSettingsForm.querySelector('button[type="submit"]') as HTMLButtonElement | null;
        if (submitBtn) {
          submitBtn.disabled = true;
          const spanText = submitBtn.querySelector('span');
          if (spanText) spanText.innerText = '保存中...';
        }

        await saveSettings(payload);
        showCustomToast('グローバル設定を保存しました。', 'success');

        if (onDataChangedCallback) {
          await onDataChangedCallback();
        }
      } catch (err) {
        console.error(err);
        showCustomToast(err instanceof Error ? err.message : 'グローバル設定の保存に失敗しました。', 'error');
      } finally {
        const submitBtn = globalSettingsForm.querySelector('button[type="submit"]') as HTMLButtonElement | null;
        if (submitBtn) {
          submitBtn.disabled = false;
          const spanText = submitBtn.querySelector('span');
          if (spanText) spanText.innerText = 'グローバル設定を保存';
        }
      }
    };
  }
}