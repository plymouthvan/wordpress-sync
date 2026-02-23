import { readTextFile, writeTextFile, readDir, exists, mkdir, remove } from '@tauri-apps/plugin-fs';
import { homeDir, join } from '@tauri-apps/api/path';
import type { SyncHistoryEntry } from '$lib/types';

/**
 * Get the history directory path (~/.wordpress-sync/history).
 */
export async function getHistoryDir(): Promise<string> {
  const home = await homeDir();
  return await join(home, '.wordpress-sync', 'history');
}

/**
 * Save a sync history entry to disk.
 */
export async function saveHistoryEntry(entry: SyncHistoryEntry): Promise<void> {
  const dir = await getHistoryDir();
  if (!(await exists(dir))) {
    await mkdir(dir, { recursive: true });
  }
  const filename = `${entry.started_at.replace(/[:.]/g, '')}_${entry.site_name}_${entry.direction}.json`;
  const filePath = await join(dir, filename);
  await writeTextFile(filePath, JSON.stringify(entry, null, 2));
}

/**
 * Load sync history entries, optionally filtered by site name.
 */
export async function loadHistory(siteName?: string): Promise<SyncHistoryEntry[]> {
  const dir = await getHistoryDir();
  if (!(await exists(dir))) return [];

  const files = await readDir(dir);
  const entries: SyncHistoryEntry[] = [];

  for (const file of files) {
    if (!file.name?.endsWith('.json')) continue;
    try {
      const filePath = await join(dir, file.name);
      const content = await readTextFile(filePath);
      const entry = JSON.parse(content) as SyncHistoryEntry;
      if (!siteName || entry.site_name === siteName) {
        entries.push(entry);
      }
    } catch {
      // Skip corrupt entries
    }
  }

  // Sort by date, newest first
  entries.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
  return entries;
}

/**
 * Delete a history entry by its ID.
 */
export async function deleteHistoryEntry(id: string): Promise<void> {
  const dir = await getHistoryDir();
  if (!(await exists(dir))) return;

  const files = await readDir(dir);
  for (const file of files) {
    if (!file.name?.endsWith('.json')) continue;
    try {
      const filePath = await join(dir, file.name);
      const content = await readTextFile(filePath);
      const entry = JSON.parse(content) as SyncHistoryEntry;
      if (entry.id === id) {
        await remove(filePath);
        return;
      }
    } catch {
      // Skip corrupt entries
    }
  }
}

/**
 * Delete history entries older than the specified number of days.
 * Returns the count of deleted entries.
 */
export async function cleanupOldHistory(retentionDays: number): Promise<number> {
  const dir = await getHistoryDir();
  if (!(await exists(dir))) return 0;

  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - retentionDays);
  const cutoffTime = cutoff.getTime();

  const files = await readDir(dir);
  let deleted = 0;

  for (const file of files) {
    if (!file.name?.endsWith('.json')) continue;
    try {
      const filePath = await join(dir, file.name);
      const content = await readTextFile(filePath);
      const entry = JSON.parse(content) as SyncHistoryEntry;
      if (new Date(entry.started_at).getTime() < cutoffTime) {
        await remove(filePath);
        deleted++;
      }
    } catch {
      // Skip corrupt entries
    }
  }

  return deleted;
}

/**
 * Get the most recent history entry for a given site.
 */
export async function getLastSync(siteName: string): Promise<SyncHistoryEntry | null> {
  const entries = await loadHistory(siteName);
  return entries.length > 0 ? entries[0] : null;
}
