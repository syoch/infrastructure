const { test, expect, chromium } = require('@playwright/test');

test.describe('Dashboard Refactored UI E2E Tests', () => {
  let browser;
  let context;
  let page;

  test.beforeAll(async () => {
    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH || '/nix/store/9fjg59mab9j8c5r61dx2k5gcbd2f5mpm-chromium-148.0.7778.96/bin/chromium',
      headless: true
    });
  });

  test.afterAll(async () => {
    if (browser) {
      await browser.close();
    }
  });

  test.beforeEach(async () => {
    context = await browser.newContext({
      baseURL: 'http://localhost:8000'
    });
    page = await context.newPage();
    
    // Capture browser console logs and errors
    page.on('pageerror', exception => {
      console.log(`[BROWSER EXCEPTION] ${exception.stack || exception}`);
    });
    page.on('console', msg => {
      console.log(`[BROWSER LOG] [${msg.type()}] ${msg.text()}`);
    });

    // ページロードして一覧が準備できるのを待つ
    await page.goto('/#/dashboard');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('#dashboard-apps-list');
  });

  test.afterEach(async () => {
    if (context) {
      await context.close();
    }
  });

  test('1. Initial layout check', async () => {
    // 1カラムのテーブルが存在することを確認
    const listSection = page.locator('.dashboard-list-section');
    await expect(listSection).toBeVisible();

    // 2カラムだった時の古いフォームや設定カードが存在しないこと
    const oldForm = page.locator('.form-card');
    const oldSettings = page.locator('.settings-card');
    await expect(oldForm).not.toBeVisible();
    await expect(oldSettings).not.toBeVisible();

    // ボタンが存在すること
    const addAppBtn = page.locator('#add-app-btn');
    await expect(addAppBtn).toBeVisible();
    await expect(addAppBtn).toContainText('新規アプリ登録');
  });

  test('2. Add and Edit and Delete App (Modal & Hash Router)', async () => {
    // ---- 2-1. アプリ新規登録モーダルの起動 ----
    const addAppBtn = page.locator('#add-app-btn');
    await addAppBtn.click();

    // ハッシュが #new?type=app になっていること
    await expect(page).toHaveURL(/#new\?type=app/);

    // モーダルが表示されていること
    const appModal = page.locator('#app-modal');
    await expect(appModal).toHaveClass(/active/);

    // フォームへの入力
    const pkgId = 'com.playwright.test';
    await page.fill('#quick-app-id', pkgId);
    await page.fill('#quick-app-name', 'Playwright Test App');
    await page.fill('#quick-app-url', 'https://github.com/microsoft/playwright');
    await page.selectOption('#quick-app-source', 'GitHub');
    await page.fill('#quick-app-categories', 'test, automatic');

    // 保存ボタンのクリック
    const saveBtn = page.locator('#quick-save-btn');
    await saveBtn.click();

    // モーダルが閉じ、ハッシュが一覧に戻ること
    await expect(appModal).not.toHaveClass(/active/);
    await expect(page).toHaveURL(/#list|#$/);

    // テーブルにアプリが追加されていることを確認
    const newAppRow = page.locator(`#dashboard-apps-list tr:has-text("${pkgId}")`);
    await expect(newAppRow).toBeVisible();
    await expect(newAppRow.locator('.app-name-text')).toContainText('Playwright Test App');

    // ---- 2-2. アプリ名クリックで簡易編集モーダル起動 ----
    // 行をクリック
    await newAppRow.click();
    await expect(appModal).toHaveClass(/active/);
    await expect(page.locator('#app-modal-title')).toContainText('アプリ簡易編集');
    
    // パッケージIDが読み取り専用（disabled）になっていること
    await expect(page.locator('#quick-app-id')).toBeDisabled();

    // ---- 2-3. 詳細設定へ遷移 ----
    const detailBtn = page.locator('#quick-detail-btn');
    await expect(detailBtn).toBeVisible();
    
    await detailBtn.click();

    // モーダルが閉じ、詳細設定画面に遷移し、ハッシュが #edit?type=app&id=... になること
    await expect(appModal).not.toHaveClass(/active/);
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=app&id=${pkgId}`));

    const editView = page.locator('#app-edit-view');
    await expect(editView).toBeVisible();
    await expect(page.locator('#edit-app-name')).toHaveValue('Playwright Test App');

    // 追加設定のチェックボックス変更と保存
    await page.check('#edit-setting-prerelease');
    const detailedSaveBtn = page.locator('#detailed-app-form button[type="submit"]');
    await detailedSaveBtn.click();

    // 保存されて一覧に戻ること
    await expect(editView).not.toBeVisible();
    await expect(page).toHaveURL(/#list|#$/);

    // ---- 2-4. アプリの削除 ----
    // 削除処理時の confirm ダイアログを自動受託する
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(pkgId);
      await dialog.accept();
    });

    // 再度簡易編集モーダルを開き、詳細設定から削除する
    const row = page.locator(`#dashboard-apps-list tr:has-text("${pkgId}")`);
    await row.click();
    await page.locator('#quick-detail-btn').click();
    
    // 削除ボタンを押す
    const deleteBtn = page.locator('#edit-delete-btn');
    await deleteBtn.click();

    // 一覧に戻り、行が削除されていること
    await expect(editView).not.toBeVisible();
    await expect(page).toHaveURL(/#list|#$/);
    await expect(page.locator(`#dashboard-apps-list tr:has-text("${pkgId}")`)).not.toBeVisible();
  });

  test('3. Add and Delete Category', async () => {
    // ---- 3-1. カテゴリ新規登録 ----
    const addCatBtn = page.locator('#add-category-btn');
    await addCatBtn.click();

    await expect(page).toHaveURL(/#new\?type=category/);

    const catModal = page.locator('#category-modal');
    await expect(catModal).toHaveClass(/active/);

    const catName = 'E2ECat';
    await page.fill('#cat-modal-name', catName);
    await page.fill('#cat-modal-color', '4284857472'); // ARGB
    
    // カラープレビューが更新されることを確認
    const colorPreview = page.locator('#cat-modal-color-preview');
    await expect(colorPreview).toHaveCSS('background-color', 'rgb(101, 188, 128)'); // ARGB: 4284857472 is hex FF65BC80 -> rgb(101,188,128)

    const catSaveBtn = page.locator('#category-modal-form button[type="submit"]');
    await catSaveBtn.click();

    // モーダルが閉じ、ハッシュが戻り、カテゴリバーにチップが追加されること
    await expect(catModal).not.toHaveClass(/active/);
    await expect(page).toHaveURL(/#list|#$/);

    const newCatChip = page.locator(`#dashboard-categories-bar .category-tag:has-text("${catName}")`);
    await expect(newCatChip).toBeVisible();

    // ---- 3-2. カテゴリチップクリックで編集モーダル起動 & 削除 ----
    // 削除確認ダイアログの自動受託
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(catName);
      await dialog.accept();
    });

    await newCatChip.click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=category&id=${catName}`));
    await expect(catModal).toHaveClass(/active/);
    await expect(page.locator('#cat-modal-name')).toBeEnabled();

    // 削除ボタンの表示確認とクリック
    const deleteCatBtn = page.locator('#cat-modal-delete');
    await expect(deleteCatBtn).toBeVisible();
    await deleteCatBtn.click();

    // モーダルが閉じ、チップが消えること
    await expect(catModal).not.toHaveClass(/active/);
    await expect(page.locator(`#dashboard-categories-bar .category-tag:has-text("${catName}")`)).not.toBeVisible();
  });

  test('4. Self-hosted APK upload, auto-fill, list check, scrape index and delete', async () => {
    // ---- 4-1. Create an HTML-sourced app ----
    const addAppBtn = page.locator('#add-app-btn');
    await addAppBtn.click();

    // Wait for route and modal to be ready
    await expect(page).toHaveURL(/#new\?type=app/);
    const appModal = page.locator('#app-modal');
    await expect(appModal).toHaveClass(/active/);

    const pkgId = 'com.selfhosted.test';
    await page.fill('#quick-app-id', pkgId);
    await page.fill('#quick-app-name', 'SelfHosted Test App');
    await page.fill('#quick-app-url', 'http://localhost:8000/scrape-index.html');
    await page.selectOption('#quick-app-source', 'HTML');

    const saveBtn = page.locator('#quick-save-btn');
    await saveBtn.click();

    // Verify row added
    const appRow = page.locator(`#dashboard-apps-list tr:has-text("${pkgId}")`);
    await expect(appRow).toBeVisible();

    // ---- 4-2. Go to Detailed Edit ----
    await appRow.click();
    await page.locator('#quick-detail-btn').click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=app&id=${pkgId}`));

    // Verify Self-Hosted APK card is visible
    const selfHostedCard = page.locator('#self-hosted-apk-card');
    await expect(selfHostedCard).toBeVisible();

    // ---- 4-3. Upload a mock APK ----
    const mockApk = {
      name: 'TestApp_com.selfhosted.test_v1.0.0_arm64-v8a.apk',
      mimeType: 'application/vnd.android.package-archive',
      buffer: Buffer.from('mock-apk-binary-content')
    };

    await page.setInputFiles('#apk-file-input', mockApk);

    // Verify filename preview, version autofill, and architecture autofill
    const dropzoneText = page.locator('#apk-dropzone-text');
    await expect(dropzoneText).toContainText('TestApp_com.selfhosted.test_v1.0.0_arm64-v8a.apk');

    const versionInput = page.locator('#apk-version-input');
    await expect(versionInput).toHaveValue('1.0.0');

    const archSelect = page.locator('#apk-arch-select');
    await expect(archSelect).toHaveValue('arm64-v8a');

    // Click upload and wait for success (toast and table row)
    const uploadBtn = page.locator('#apk-upload-btn');
    await uploadBtn.click();

    // Wait for the table to contain the new APK entry
    const apkRow = page.locator('#apk-list-tbody tr');
    await expect(apkRow).toContainText('1.0.0');
    await expect(apkRow).toContainText('arm64-v8a');

    // ---- 4-4. Verify /scrape-index.html contains download link ----
    await page.goto('/scrape-index.html');
    const link = page.locator('a[href*="/api/apps/download/"]').filter({ hasText: 'SelfHosted_Test_App' });
    await expect(link).toBeVisible();
    await expect(link).toContainText('SelfHosted_Test_App_com.selfhosted.test_v1.0.0_arm64-v8a.apk');

    // ---- 4-5. Back to Edit View and Delete APK & App ----
    await page.goto(`/#edit?type=app&id=${pkgId}`);
    await expect(selfHostedCard).toBeVisible();

    // Setup delete confirm handling
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain('削除');
      await dialog.accept();
    });

    const deleteApkBtn = page.locator('#apk-list-tbody .delete-apk-btn');
    await deleteApkBtn.click();

    // Verify APK row is gone (table shows "no APKs" text)
    await expect(page.locator('#apk-list-tbody')).toContainText('登録されているセルフホスト APK がありません');

    // Cleanup the app
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(pkgId);
      await dialog.accept();
    });
    const deleteAppBtn = page.locator('#edit-delete-btn');
    await deleteAppBtn.click();

    // Verify app row is gone
    await expect(page.locator(`#dashboard-apps-list tr:has-text("${pkgId}")`)).not.toBeVisible();
  });

  test('5. Import Obtainium export JSON config', async () => {
    // Navigate to dashboard
    await page.goto('/#/dashboard');

    const importBtn = page.locator('#import-json-btn');
    await expect(importBtn).toBeVisible();

    // Prepare a mock obtainium-export.json data
    const mockExportData = {
      apps: [
        {
          id: 'com.mockimport.test',
          name: 'Mock Imported App',
          url: 'https://github.com/mock/imported-app',
          overrideSource: 'GitHub',
          categories: ['imported'],
          additionalSettings: {
            includePrereleases: false,
            fallbackToOlderReleases: true,
            versionDetection: true
          }
        }
      ],
      settings: {
        categories: {
          imported: 4284857472
        }
      }
    };

    // Setup input files on hidden file input
    const filePayload = {
      name: 'obtainium-export.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(mockExportData))
    };

    // Setup window alert dialog mock to accept
    const dialogPromise = page.waitForEvent('dialog');
    await page.setInputFiles('#import-json-file', filePayload);
    const dialog = await dialogPromise;
    expect(dialog.message()).toContain('Successfully imported');
    await dialog.accept();

    // Confirm that the imported app is listed in the dashboard apps list
    const importedRow = page.locator('#dashboard-apps-list tr:has-text("com.mockimport.test")');
    await expect(importedRow).toBeVisible();
    await expect(importedRow).toContainText('Mock Imported App');

    // Confirm category chip is added
    const categoryChip = page.locator('#dashboard-categories-bar .category-tag:has-text("imported")');
    await expect(categoryChip).toBeVisible();

    // Clean up: delete the imported app
    await importedRow.click();
    await page.locator('#quick-detail-btn').click();
    
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain('com.mockimport.test');
      await dialog.accept();
    });
    await page.locator('#edit-delete-btn').click();
    await expect(page.locator('#dashboard-apps-list tr:has-text("com.mockimport.test")')).not.toBeVisible();
  });

  test('6. Category sorting in dashboard list', async () => {
    const sortHeader = page.locator('#dashboard-sort-category');
    const sortIcon = page.locator('#dashboard-sort-icon');

    // Initial state is "↕"
    await expect(sortIcon).toHaveText('↕');

    // First click: Ascending "▲"
    await sortHeader.click();
    await expect(sortIcon).toHaveText('▲');

    // Second click: Descending "▼"
    await sortHeader.click();
    await expect(sortIcon).toHaveText('▼');

    // Third click: Normal "↕"
    await sortHeader.click();
    await expect(sortIcon).toHaveText('↕');
  });

  test('7. Category-App association via checkboxes in Category Edit Modal', async () => {
    // ---- 7-1. Create temporary App for association ----
    const addAppBtn = page.locator('#add-app-btn');
    await addAppBtn.click();

    // モーダルがアクティブになるのを待つ（クリア処理との競合を避ける）
    await expect(page).toHaveURL(/#new\?type=app/);
    const appModal = page.locator('#app-modal');
    await expect(appModal).toHaveClass(/active/);

    const pkgId = 'com.association.test';
    await page.fill('#quick-app-id', pkgId);
    await page.fill('#quick-app-name', 'Association Test App');
    await page.fill('#quick-app-url', 'https://github.com/test/association');
    await page.locator('#quick-save-btn').click();
    await page.waitForSelector(`#dashboard-apps-list tr:has-text("${pkgId}")`);

    // ---- 7-2. Create temporary Category ----
    const addCatBtn = page.locator('#add-category-btn');
    await addCatBtn.click();

    // カテゴリモーダルが開くのを待つ
    await expect(page).toHaveURL(/#new\?type=category/);
    const catModal = page.locator('#category-modal');
    await expect(catModal).toHaveClass(/active/);

    const catName = 'AssocCat';
    await page.fill('#cat-modal-name', catName);
    await page.fill('#cat-modal-color', '#ff55aa11');
    await page.locator('#category-modal-form button[type="submit"]').click();
    await page.waitForSelector(`#dashboard-categories-bar .category-tag:has-text("${catName}")`);

    // ---- 7-3. Edit Category to bind the App ----
    const catChip = page.locator(`#dashboard-categories-bar .category-tag:has-text("${catName}")`);
    await catChip.click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=category&id=${catName}`));

    // Find checkbox for the app and check it
    const appCheckbox = page.locator(`#category-apps-list input[data-app-id="${pkgId}"]`);
    await expect(appCheckbox).toBeVisible();
    await expect(appCheckbox).not.toBeChecked();
    await appCheckbox.check();

    // Save category changes
    await page.locator('#category-modal-form button[type="submit"]').click();
    await expect(page.locator('#category-modal')).not.toHaveClass(/active/);

    // Verify category tag is shown in the app row on the dashboard list
    const appRow = page.locator(`#dashboard-apps-list tr:has-text("${pkgId}")`);
    await expect(appRow.locator(`.category-tag:has-text("${catName}")`)).toBeVisible();

    // ---- 7-4. Edit Category to unbind the App ----
    await catChip.click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=category&id=${catName}`));
    await expect(appCheckbox).toBeChecked();
    await appCheckbox.uncheck();
    await page.locator('#category-modal-form button[type="submit"]').click();
    await expect(page.locator('#category-modal')).not.toHaveClass(/active/);

    // Verify category tag is removed from the app row
    await expect(appRow.locator(`.category-tag:has-text("${catName}")`)).not.toBeVisible();

    // ---- 7-5. Cleanup (Delete App & Delete Category) ----
    // Delete App
    await appRow.click();
    await page.locator('#quick-detail-btn').click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(pkgId);
      await dialog.accept();
    });
    await page.locator('#edit-delete-btn').click();
    await expect(page.locator(`#dashboard-apps-list tr:has-text("${pkgId}")`)).not.toBeVisible();

    // Delete Category
    await catChip.click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(catName);
      await dialog.accept();
    });
    await page.locator('#cat-modal-delete').click();
    await expect(page.locator(`#dashboard-categories-bar .category-tag:has-text("${catName}")`)).not.toBeVisible();
  });

  test('8. Category auto-creation on app edit, then declare category and bind another app', async () => {
    // ---- 8-1. Create App A and App B ----
    // App A
    const addAppBtn = page.locator('#add-app-btn');
    await addAppBtn.click();
    await expect(page).toHaveURL(/#new\?type=app/);
    const appModal = page.locator('#app-modal');
    await expect(appModal).toHaveClass(/active/);
    const pkgIdA = 'com.dynamic.appa';
    await page.fill('#quick-app-id', pkgIdA);
    await page.fill('#quick-app-name', 'Dynamic App A');
    await page.fill('#quick-app-url', 'https://github.com/test/appa');
    await page.locator('#quick-save-btn').click();
    await expect(appModal).not.toHaveClass(/active/);
    await expect(page).toHaveURL(/#list|#$/);
    await page.waitForSelector(`#dashboard-apps-list tr:has-text("${pkgIdA}")`);

    // App B
    await addAppBtn.click();
    await expect(page).toHaveURL(/#new\?type=app/);
    await expect(appModal).toHaveClass(/active/);
    const pkgIdB = 'com.dynamic.appb';
    await page.fill('#quick-app-id', pkgIdB);
    await page.fill('#quick-app-name', 'Dynamic App B');
    await page.fill('#quick-app-url', 'https://github.com/test/appb');
    await page.locator('#quick-save-btn').click();
    await expect(appModal).not.toHaveClass(/active/);
    await expect(page).toHaveURL(/#list|#$/);
    await page.waitForSelector(`#dashboard-apps-list tr:has-text("${pkgIdB}")`);

    // ---- 8-2. Edit App A to add non-existent Category 'CateA' ----
    const appRowA = page.locator(`#dashboard-apps-list tr:has-text("${pkgIdA}")`);
    await appRowA.click();
    await expect(appModal).toHaveClass(/active/);
    await page.locator('#quick-detail-btn').click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=app&id=${pkgIdA}`));

    const catName = 'CateA';
    await page.fill('#edit-app-categories', catName);
    const detailedSaveBtn = page.locator('#detailed-app-form button[type="submit"]');
    await detailedSaveBtn.click();

    // Verify App A has CateA category tag in the list
    await expect(page).toHaveURL(/#list|#$/);
    await expect(appRowA.locator(`.category-tag:has-text("${catName}")`)).toBeVisible();

    // ---- 8-3. Create Category 'CateA' (already auto-created in db, now officially configured in settings) ----
    const addCatBtn = page.locator('#add-category-btn');
    await addCatBtn.click();
    await expect(page).toHaveURL(/#new\?type=category/);
    const catModal = page.locator('#category-modal');
    await expect(catModal).toHaveClass(/active/);

    await page.fill('#cat-modal-name', catName);
    await page.fill('#cat-modal-color', '4294901760'); // Red: #ffff0000 -> 4294901760
    await page.locator('#category-modal-form button[type="submit"]').click();
    await expect(catModal).not.toHaveClass(/active/);

    // Verify category chip is shown in category bar
    const catChip = page.locator(`#dashboard-categories-bar .category-tag:has-text("${catName}")`);
    await expect(catChip).toBeVisible();

    // ---- 8-4. Edit Category 'CateA' to bind App B ----
    await catChip.click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=category&id=${catName}`));
    await expect(catModal).toHaveClass(/active/);

    // App A should already be checked since it was associated dynamically
    const appCheckboxA = page.locator(`#category-apps-list input[data-app-id="${pkgIdA}"]`);
    await expect(appCheckboxA).toBeVisible();
    await expect(appCheckboxA).toBeChecked();

    // Bind App B by checking its box
    const appCheckboxB = page.locator(`#category-apps-list input[data-app-id="${pkgIdB}"]`);
    await expect(appCheckboxB).toBeVisible();
    await expect(appCheckboxB).not.toBeChecked();
    await appCheckboxB.check();

    // Save category changes
    await page.locator('#category-modal-form button[type="submit"]').click();
    await expect(catModal).not.toHaveClass(/active/);

    // ---- 8-5. Verify both App A and App B have CateA category tag ----
    await expect(appRowA.locator(`.category-tag:has-text("${catName}")`)).toBeVisible();
    const appRowB = page.locator(`#dashboard-apps-list tr:has-text("${pkgIdB}")`);
    await expect(appRowB.locator(`.category-tag:has-text("${catName}")`)).toBeVisible();

    // ---- 8-6. Cleanup (Delete App A, App B & Category) ----
    // Delete App A
    await appRowA.click();
    await page.locator('#quick-detail-btn').click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(pkgIdA);
      await dialog.accept();
    });
    await page.locator('#edit-delete-btn').click();
    await expect(page.locator(`#dashboard-apps-list tr:has-text("${pkgIdA}")`)).not.toBeVisible();

    // Delete App B
    await appRowB.click();
    await page.locator('#quick-detail-btn').click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(pkgIdB);
      await dialog.accept();
    });
    await page.locator('#edit-delete-btn').click();
    await expect(page.locator(`#dashboard-apps-list tr:has-text("${pkgIdB}")`)).not.toBeVisible();

    // Delete Category
    await catChip.click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(catName);
      await dialog.accept();
    });
    await page.locator('#cat-modal-delete').click();
    await expect(page.locator(`#dashboard-categories-bar .category-tag:has-text("${catName}")`)).not.toBeVisible();
  });

  test('9. Save app with overrideSource set to null via API (Pydantic validation check)', async ({ request }) => {
    const pkgId = 'com.nullsource.test';
    
    // Send POST directly to api/apps/save with overrideSource set to null
    const response = await request.post('/api/apps/save', {
      data: {
        id: pkgId,
        name: 'Null Source Test App',
        url: 'https://github.com/test/nullsource',
        overrideSource: null,
        preferredApkIndex: 0,
        pinned: false,
        allowIdChange: false,
        categories: [],
        additionalSettings: {
          fallbackToOlderReleases: true,
          versionDetection: true
        }
      }
    });

    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.status).toBe('success');

    // Cleanup: delete the test app
    const deleteResponse = await request.post('/api/apps/delete', {
      data: { id: pkgId }
    });
    expect(deleteResponse.status()).toBe(200);
  });

  test('9b. Save app with preferredApkIndex set to null via API (Pydantic validation check)', async ({ request }) => {
    const pkgId = 'com.nullpreferred.test';
    
    // Send POST directly to api/apps/save with preferredApkIndex set to null
    const response = await request.post('/api/apps/save', {
      data: {
        id: pkgId,
        name: 'Null Preferred Test App',
        url: 'https://github.com/test/nullpreferred',
        overrideSource: 'GitHub',
        preferredApkIndex: null,
        pinned: false,
        allowIdChange: false,
        categories: [],
        additionalSettings: {
          fallbackToOlderReleases: true,
          versionDetection: true
        }
      }
    });

    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.status).toBe('success');

    // Cleanup: delete the test app
    const deleteResponse = await request.post('/api/apps/delete', {
      data: { id: pkgId }
    });
    expect(deleteResponse.status()).toBe(200);
  });

  test('10. Rename Category and verify app associations update and old category is deleted', async () => {
    // ---- 10-1. Create App A and App B ----
    // App A
    const addAppBtn = page.locator('#add-app-btn');
    await addAppBtn.click();
    await expect(page).toHaveURL(/#new\?type=app/);
    const appModal = page.locator('#app-modal');
    await expect(appModal).toHaveClass(/active/);
    const pkgIdA = 'com.renamecat.appa';
    await page.fill('#quick-app-id', pkgIdA);
    await page.fill('#quick-app-name', 'Rename App A');
    await page.fill('#quick-app-url', 'https://github.com/test/rename-appa');
    await page.locator('#quick-save-btn').click();
    await page.waitForSelector(`#dashboard-apps-list tr:has-text("${pkgIdA}")`);

    // App B
    await addAppBtn.click();
    await expect(page).toHaveURL(/#new\?type=app/);
    await expect(appModal).toHaveClass(/active/);
    const pkgIdB = 'com.renamecat.appb';
    await page.fill('#quick-app-id', pkgIdB);
    await page.fill('#quick-app-name', 'Rename App B');
    await page.fill('#quick-app-url', 'https://github.com/test/rename-appb');
    await page.locator('#quick-save-btn').click();
    await page.waitForSelector(`#dashboard-apps-list tr:has-text("${pkgIdB}")`);

    // ---- 10-2. Create Category 'OriginalCat' ----
    const addCatBtn = page.locator('#add-category-btn');
    await addCatBtn.click();
    await expect(page).toHaveURL(/#new\?type=category/);
    const catModal = page.locator('#category-modal');
    await expect(catModal).toHaveClass(/active/);

    const originalCatName = 'OriginalCat';
    await page.fill('#cat-modal-name', originalCatName);
    await page.fill('#cat-modal-color', '4294901760'); // Red
    await page.locator('#category-modal-form button[type="submit"]').click();
    await expect(catModal).not.toHaveClass(/active/);

    const catChip = page.locator(`#dashboard-categories-bar .category-tag:has-text("${originalCatName}")`);
    await expect(catChip).toBeVisible();

    // ---- 10-3. Edit Category 'OriginalCat' to bind App A ----
    await catChip.click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=category&id=${originalCatName}`));
    await expect(catModal).toHaveClass(/active/);

    const appCheckboxA = page.locator(`#category-apps-list input[data-app-id="${pkgIdA}"]`);
    await expect(appCheckboxA).toBeVisible();
    await appCheckboxA.check();
    await page.locator('#category-modal-form button[type="submit"]').click();
    await expect(catModal).not.toHaveClass(/active/);

    // Verify App A is bound to OriginalCat
    const appRowA = page.locator(`#dashboard-apps-list tr:has-text("${pkgIdA}")`);
    await expect(appRowA.locator(`.category-tag:has-text("${originalCatName}")`)).toBeVisible();

    // ---- 10-4. Rename Category 'OriginalCat' to 'RenamedCat' and also bind App B ----
    await catChip.click();
    await expect(page).toHaveURL(new RegExp(`#edit\\?type=category&id=${originalCatName}`));
    await expect(catModal).toHaveClass(/active/);

    // Rename
    const renamedCatName = 'RenamedCat';
    await page.fill('#cat-modal-name', renamedCatName);

    // Bind App B
    const appCheckboxB = page.locator(`#category-apps-list input[data-app-id="${pkgIdB}"]`);
    await expect(appCheckboxB).toBeVisible();
    await appCheckboxB.check();

    // Save
    await page.locator('#category-modal-form button[type="submit"]').click();
    await expect(catModal).not.toHaveClass(/active/);

    // ---- 10-5. Verify old category is gone and new category is bound to both A and B ----
    // Category bar checks
    const oldCatChip = page.locator(`#dashboard-categories-bar .category-tag:has-text("${originalCatName}")`);
    await expect(oldCatChip).not.toBeVisible();
    const newCatChip = page.locator(`#dashboard-categories-bar .category-tag:has-text("${renamedCatName}")`);
    await expect(newCatChip).toBeVisible();

    // App A checks (should lose OriginalCat, get RenamedCat)
    await expect(appRowA.locator(`.category-tag:has-text("${originalCatName}")`)).not.toBeVisible();
    await expect(appRowA.locator(`.category-tag:has-text("${renamedCatName}")`)).toBeVisible();

    // App B checks (should get RenamedCat)
    const appRowB = page.locator(`#dashboard-apps-list tr:has-text("${pkgIdB}")`);
    await expect(appRowB.locator(`.category-tag:has-text("${renamedCatName}")`)).toBeVisible();

    // ---- 10-6. Cleanup (Delete App A, App B, Category) ----
    // Delete App A
    await appRowA.click();
    await page.locator('#quick-detail-btn').click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(pkgIdA);
      await dialog.accept();
    });
    await page.locator('#edit-delete-btn').click();
    await expect(page.locator(`#dashboard-apps-list tr:has-text("${pkgIdA}")`)).not.toBeVisible();

    // Delete App B
    await appRowB.click();
    await page.locator('#quick-detail-btn').click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(pkgIdB);
      await dialog.accept();
    });
    await page.locator('#edit-delete-btn').click();
    await expect(page.locator(`#dashboard-apps-list tr:has-text("${pkgIdB}")`)).not.toBeVisible();

    // Delete Category
    await newCatChip.click();
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain(renamedCatName);
      await dialog.accept();
    });
    await page.locator('#cat-modal-delete').click();
    await expect(page.locator(`#dashboard-categories-bar .category-tag:has-text("${renamedCatName}")`)).not.toBeVisible();
  });

  test('11. Edit and Save Global Settings', async () => {
    // Navigate to dashboard
    await page.goto('/#/dashboard');

    // Fill form fields
    const themeSelect = page.locator('#global-setting-theme');
    await expect(themeSelect).toBeVisible();
    await themeSelect.selectOption('dark');

    const checkIntervalInput = page.locator('#global-setting-check-interval');
    await checkIntervalInput.fill('12');

    const checkOnStartup = page.locator('#global-setting-check-on-startup');
    const prerelease = page.locator('#global-setting-prerelease');
    const allowSourceChange = page.locator('#global-setting-allow-source-change');
    const restrictNotification = page.locator('#global-setting-restrict-notification');

    await checkOnStartup.check();
    await prerelease.check();
    await allowSourceChange.check();
    await restrictNotification.check();

    // Submit
    const submitBtn = page.locator('#global-settings-form button[type="submit"]');
    await submitBtn.click();

    // Verify success toast (we use custom toast, check for text)
    const toast = page.locator('#custom-toast');
    await expect(toast).toContainText('グローバル設定を保存しました');

    // Reload page to verify persistence
    await page.reload();
    await page.waitForTimeout(1000); // Give UI a brief moment to load settings

    // Verify fields persisted correctly
    await expect(themeSelect).toHaveValue('dark');
    await expect(checkIntervalInput).toHaveValue('12');
    await expect(checkOnStartup).toBeChecked();
    await expect(prerelease).toBeChecked();
    await expect(allowSourceChange).toBeChecked();
    await expect(restrictNotification).toBeChecked();
  });
});

