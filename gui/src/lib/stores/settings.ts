import { writable } from 'svelte/store';
import type { AppSettings } from '$lib/types';

const DEFAULT_SETTINGS: AppSettings = {
  cli_path: '',
  cli_version: '',
  theme: 'system',
  log_retention_days: 30,
  notifications_enabled: true,
  default_ssh_key: '~/.ssh/id_rsa'
};

/**
 * Store holding the global application settings.
 */
export const settings = writable<AppSettings>({ ...DEFAULT_SETTINGS });

/**
 * Load settings from disk and populate the store.
 */
export async function initSettings(): Promise<void> {
  const { loadSettings } = await import('$lib/services/config');
  try {
    const loaded = await loadSettings();
    settings.set(loaded);
  } catch (e) {
    console.error('Failed to load settings:', e);
    settings.set({ ...DEFAULT_SETTINGS });
  }
}

/**
 * Persist the current settings to disk.
 */
export async function persistSettings(updated: AppSettings): Promise<void> {
  const { saveSettings } = await import('$lib/services/config');
  settings.set(updated);
  await saveSettings(updated);
}
