interface CustomToastElement extends HTMLElement {
  timeoutId?: ReturnType<typeof setTimeout>;
}

export function showCustomToast(
  msg: string,
  type: 'info' | 'success' | 'error' | 'warning' = 'info',
  duration = 3000
): void {
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
    if (!toast) return;
    toast.style.opacity = '0';
    toast.style.pointerEvents = 'none';
  }, duration);
}
