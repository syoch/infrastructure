export interface ConfirmDialogOptions {
  title?: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
}

export interface PromptDialogOptions {
  title?: string;
  message?: string;
  label?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
}

export interface ConfirmDialogRequest extends ConfirmDialogOptions {
  id: number;
}

export interface PromptDialogRequest extends PromptDialogOptions {
  id: number;
}

let confirmRequest: ConfirmDialogRequest | null = $state(null);
let promptRequest: PromptDialogRequest | null = $state(null);

let confirmResolve: ((value: boolean) => void) | null = null;
let promptResolve: ((value: string | null) => void) | null = null;
let nextId = 1;

export function getConfirmRequest(): ConfirmDialogRequest | null {
  return confirmRequest;
}

export function getPromptRequest(): PromptDialogRequest | null {
  return promptRequest;
}

export function resolveConfirm(value: boolean): void {
  const resolve = confirmResolve;
  confirmResolve = null;
  confirmRequest = null;
  if (resolve) resolve(value);
}

export function resolvePrompt(value: string | null): void {
  const resolve = promptResolve;
  promptResolve = null;
  promptRequest = null;
  if (resolve) resolve(value);
}

/**
 * Promise-based replacement for the native `confirm()`.
 * Resolves `true` when confirmed, `false` when cancelled/dismissed.
 */
export function confirmDialog(options: ConfirmDialogOptions = {}): Promise<boolean> {
  if (confirmResolve) {
    const pending = confirmResolve;
    confirmResolve = null;
    pending(false);
  }
  return new Promise<boolean>((resolve) => {
    confirmResolve = resolve;
    confirmRequest = { id: nextId++, ...options };
  });
}

/**
 * Promise-based replacement for the native `prompt()`.
 * Resolves the entered string, or `null` when cancelled/dismissed.
 */
export function promptDialog(options: PromptDialogOptions = {}): Promise<string | null> {
  if (promptResolve) {
    const pending = promptResolve;
    promptResolve = null;
    pending(null);
  }
  return new Promise<string | null>((resolve) => {
    promptResolve = resolve;
    promptRequest = { id: nextId++, ...options };
  });
}
