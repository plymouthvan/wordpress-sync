/**
 * macOS Keychain integration for storing sensitive credentials.
 *
 * Uses Tauri invoke commands backed by the security-framework Rust crate
 * to store, retrieve, and delete passwords in the system Keychain.
 * Passwords never touch the filesystem — they live only in the OS credential store.
 */

import { invoke } from '@tauri-apps/api/core';

const SUDO_SERVICE = 'com.wordpress-sync.sudo';

/**
 * Store a sudo password for a site in the macOS Keychain.
 */
export async function storeSudoPassword(siteName: string, password: string): Promise<void> {
  await invoke('store_credential', {
    service: SUDO_SERVICE,
    account: siteName,
    password,
  });
}

/**
 * Retrieve a sudo password for a site from the macOS Keychain.
 * Returns null if no password is stored.
 */
export async function getSudoPassword(siteName: string): Promise<string | null> {
  return await invoke<string | null>('get_credential', {
    service: SUDO_SERVICE,
    account: siteName,
  });
}

/**
 * Delete a sudo password for a site from the macOS Keychain.
 * Silently succeeds if no password is stored.
 */
export async function deleteSudoPassword(siteName: string): Promise<void> {
  await invoke('delete_credential', {
    service: SUDO_SERVICE,
    account: siteName,
  });
}

/**
 * Check whether a sudo password exists in the Keychain for a site.
 */
export async function hasSudoPassword(siteName: string): Promise<boolean> {
  const pw = await getSudoPassword(siteName);
  return pw !== null;
}
