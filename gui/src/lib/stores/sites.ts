import { writable } from 'svelte/store';
import type { SyncHistoryEntry } from '$lib/types';

export interface SiteEntry {
  name: string;
  status: 'unknown' | 'ready' | 'syncing' | 'error';
  lastSync?: SyncHistoryEntry | null;
}

/**
 * Store holding the list of known sites and their status.
 */
export const sites = writable<SiteEntry[]>([]);

/**
 * Store holding the currently selected site name.
 */
export const selectedSite = writable<string | null>(null);

/**
 * Refresh the site list from disk, including last sync info.
 */
export async function refreshSiteList(): Promise<void> {
  const { listSites } = await import('$lib/services/config');
  const { loadHistory } = await import('$lib/services/history');
  try {
    const siteNames = await listSites();

    // Load history for all sites once
    let allHistory: SyncHistoryEntry[] = [];
    try {
      allHistory = await loadHistory();
    } catch {
      // History may not exist yet
    }

    const entries: SiteEntry[] = siteNames.map((name) => {
      const lastSync = allHistory.find((h) => h.site_name === name) ?? null;
      const status: SiteEntry['status'] = lastSync
        ? lastSync.status === 'failed'
          ? 'error'
          : 'ready'
        : 'unknown';
      return { name, status, lastSync };
    });

    sites.set(entries);
  } catch (e) {
    console.error('Failed to refresh site list:', e);
    sites.set([]);
  }
}
