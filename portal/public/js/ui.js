export function showToast(toastElement) {
  if (!toastElement) return;
  toastElement.classList.remove('hidden');
  setTimeout(() => {
    toastElement.classList.add('hidden');
  }, 2000);
}

export function getCategoryColorStyle(colorCode) {
  if (!colorCode) return '';
  const r = (colorCode >>> 16) & 0xFF;
  const g = (colorCode >>> 8) & 0xFF;
  const b = colorCode & 0xFF;
  return `background: rgba(${r}, ${g}, ${b}, 0.15); border-color: rgba(${r}, ${g}, ${b}, 0.4); color: rgb(${Math.min(r+60, 255)}, ${Math.min(g+60, 255)}, ${Math.min(b+60, 255)});`;
}

export function applyCategoryStyleToElement(element, colorCode) {
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
  element.style.color = `rgb(${Math.min(r+60, 255)}, ${Math.min(g+60, 255)}, ${Math.min(b+60, 255)})`;
}

export function getCategoryModalColorPreview(colorInt) {
  if (!colorInt) {
    return 'transparent';
  }
  const r = (colorInt >>> 16) & 0xFF;
  const g = (colorInt >>> 8) & 0xFF;
  const b = colorInt & 0xFF;
  const a = ((colorInt >>> 24) & 0xFF) / 255;
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function colorIntToHex(colorInt) {
  if (colorInt === undefined || colorInt === null || isNaN(colorInt)) {
    return '';
  }
  const hex = (colorInt >>> 0).toString(16).padStart(8, '0');
  return `#${hex}`;
}

export function parseHexToColorInt(hexStr) {
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

export function escapeHTML(str) {
  if (str === undefined || str === null) return '';
  return str.toString()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function safeURL(url) {
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
