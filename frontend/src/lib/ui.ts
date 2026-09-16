export function showToast(toastElement: HTMLElement | null): void {
  if (!toastElement) return;
  toastElement.classList.remove('hidden');
  setTimeout(() => {
    toastElement.classList.add('hidden');
  }, 2000);
}

export function getCategoryColorStyle(colorCode: number | null | undefined): string {
  if (!colorCode) return '';
  const r = (colorCode >>> 16) & 0xFF;
  const g = (colorCode >>> 8) & 0xFF;
  const b = colorCode & 0xFF;
  return `background: rgba(${r}, ${g}, ${b}, 0.15); border-color: rgba(${r}, ${g}, ${b}, 0.4); color: rgb(${Math.min(r + 60, 255)}, ${Math.min(g + 60, 255)}, ${Math.min(b + 60, 255)});`;
}

export function applyCategoryStyleToElement(element: HTMLElement, colorCode: number | null | undefined): void {
  if (!colorCode) {
    element.style.backgroundColor = '';
    element.style.borderColor = '';
    element.style.color = '';
    return;
  }
  const r = (colorCode >>> 16) & 0xFF;
  const g = (colorCode >>> 8) & 0xFF;
  const b = colorCode & 0xFF;
  element.style.backgroundColor = `rgba(${r}, ${g}, ${b}, 0.15)`;
  element.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.4)`;
  element.style.color = `rgb(${Math.min(r + 60, 255)}, ${Math.min(g + 60, 255)}, ${Math.min(b + 60, 255)})`;
}

export function getCategoryModalColorPreview(colorInt: number | null | undefined): string {
  if (!colorInt) {
    return 'transparent';
  }
  const r = (colorInt >>> 16) & 0xFF;
  const g = (colorInt >>> 8) & 0xFF;
  const b = colorInt & 0xFF;
  const a = ((colorInt >>> 24) & 0xFF) / 255;
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function colorIntToHex(colorInt: number | null | undefined): string {
  if (colorInt === undefined || colorInt === null || isNaN(colorInt)) {
    return '';
  }
  const hex = (colorInt >>> 0).toString(16).padStart(8, '0');
  return `#${hex}`;
}

export function parseHexToColorInt(hexStr: string | null | undefined): number {
  if (!hexStr) return NaN;
  let clean = hexStr.trim();

  // Backwards compatibility for 10-decimal ARGB strings
  if (/^\d+$/.test(clean)) {
    const parsed = parseInt(clean, 10) >>> 0;
    return isNaN(parsed) ? NaN : parsed;
  }

  clean = clean.replace(/^#/, '');
  if (clean.length === 6) {
    clean = 'ff' + clean;
  }
  if (clean.length === 8) {
    const parsed = parseInt(clean, 16) >>> 0;
    return isNaN(parsed) ? NaN : parsed;
  }
  return NaN;
}

export function escapeHTML(str: string | null | undefined): string {
  if (str === undefined || str === null) return '';
  return str.toString()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function safeURL(url: string | null | undefined): string {
  if (!url) return '#';
  const lower = url.trim().toLowerCase();
  if (
    lower.startsWith('http://') ||
    lower.startsWith('https://') ||
    lower.startsWith('obtainium://') ||
    (lower.startsWith('/') && !lower.startsWith('//'))
  ) {
    return url;
  }
  return '#';
}

// URL ↔ Source validation

interface SourcePattern {
  source: string;
  pattern: RegExp;
}

const URL_SOURCE_MAP: SourcePattern[] = [
  { source: 'GitHub', pattern: /^https?:\/\/github\.com\/[^/]+\/[^/]+/ },
  { source: 'GitLab', pattern: /^https?:\/\/gitlab\.com\/[^/]+\/[^/]+/ },
  { source: 'F-Droid', pattern: /^https?:\/\/(f-droid\.org|fdroid\.github\.io)/ },
  { source: 'APKPure', pattern: /^https?:\/\/([^/]+\.)?apkpure\.(com|net)/ },
  { source: 'HTML', pattern: /^\// },
];

export function detectSourceFromUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  for (const { source, pattern } of URL_SOURCE_MAP) {
    if (pattern.test(trimmed)) return source;
  }
  return null;
}

export interface ValidationResult {
  valid: boolean;
  warning: string | null;
}

export function validateUrlSourceMatch(url: string | null | undefined, source: string | null | undefined): ValidationResult {
  if (!source) return { valid: true, warning: null };
  const detected = detectSourceFromUrl(url);
  if (!detected) return { valid: true, warning: null };
  if (detected === source) return { valid: true, warning: null };
  return {
    valid: false,
    warning: `この URL は ${detected} として自動検出されます。手動で「${source}」に設定されています。Auto-detect に変更することを推奨します。`,
  };
}