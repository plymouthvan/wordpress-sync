import { Command } from '@tauri-apps/plugin-shell';
import { PATH_SETUP } from './cli';
import type { SiteConfig } from '$lib/types';
import { isLegacyBackupConfig } from './config';

// ──────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────

export interface BackupItem {
  name: string;        // filename or directory name
  path: string;        // full path
  type: 'file' | 'directory';
  size: string;        // human-readable (e.g. "12M")
  sizeBytes: number;   // raw bytes for sorting
  date: string;        // ISO date string or raw date
  location: 'local' | 'remote';
  category: 'backup-archive' | 'backup-latest' | 'db-backup';
}

export interface BackupSummary {
  totalSize: string;
  totalSizeBytes: number;
  itemCount: number;
}

// ──────────────────────────────────────────────────────────────
// Path resolution
// ──────────────────────────────────────────────────────────────

/** Default backup directory (unified) */
const DEFAULT_BACKUP_DIR = '../wordpress-sync-backups';

/** Resolve a possibly-relative directory against a base path. */
function resolveDirAgainstBase(dir: string, basePath: string): string {
  if (dir.startsWith('/')) return dir;
  if (dir.startsWith('../')) {
    const parent = basePath.replace(/\/+$/, '').replace(/\/[^/]+$/, '');
    return `${parent}/${dir.slice(3)}`;
  }
  return `${basePath.replace(/\/+$/, '')}/${dir}`;
}

/**
 * Get the directory string for a given location from the backup config.
 * Handles both new format (object { local, remote }) and legacy format (plain string).
 */
function getBackupDirString(config: SiteConfig, location: 'local' | 'remote'): string {
  const dir = config.backup?.directory;
  if (!dir) return DEFAULT_BACKUP_DIR;
  if (typeof dir === 'string') return dir || DEFAULT_BACKUP_DIR;
  return (location === 'local' ? dir.local : dir.remote) || DEFAULT_BACKUP_DIR;
}

/**
 * Resolve the backup root directory for a given location.
 * New format: this is the unified root containing latest/, archives/, db/ subdirs.
 * Legacy format: this is the old backup directory (no subdirs).
 */
function resolveBackupRoot(config: SiteConfig, location: 'local' | 'remote'): string {
  const dirStr = getBackupDirString(config, location);
  const basePath = location === 'remote' ? config.paths.live : config.paths.local;
  return resolveDirAgainstBase(dirStr, basePath);
}

/**
 * Resolve the latest backup directory (where rsync --backup-dir puts files).
 * New format: <backupRoot>/latest
 * Legacy format: <backupRoot> (the old directory IS the backup dir)
 */
export function resolveLatestDir(config: SiteConfig, location: 'local' | 'remote'): string {
  const root = resolveBackupRoot(config, location);
  if (isLegacyBackupConfig(config)) return root;
  return `${root}/latest`;
}

/**
 * Resolve the archives directory (where archived backup snapshots are stored).
 * New format: <backupRoot>/archives
 * Legacy format: parent of the latest backup dir (old behavior)
 */
export function resolveArchivesDir(config: SiteConfig, location: 'local' | 'remote'): string {
  const root = resolveBackupRoot(config, location);
  if (isLegacyBackupConfig(config)) {
    // Legacy: archives lived in the parent of the backup directory
    return root.replace(/\/+$/, '').replace(/\/[^/]+$/, '');
  }
  return `${root}/archives`;
}

/**
 * Resolve the database backup directory.
 * New format: <backupRoot>/db
 * Legacy format: uses the old separate backup.database.directory config
 */
export function resolveDbBackupDir(config: SiteConfig, location: 'local' | 'remote'): string {
  if (isLegacyBackupConfig(config)) {
    // Legacy: use the old separate database.directory field
    const dbDir = config.backup?.database?.directory || '../wordpress-sync-db-backups';
    const basePath = location === 'remote' ? config.paths.live : config.paths.local;
    return resolveDirAgainstBase(dbDir, basePath);
  }
  const root = resolveBackupRoot(config, location);
  return `${root}/db`;
}

// ──────────────────────────────────────────────────────────────
// SSH helpers
// ──────────────────────────────────────────────────────────────

function sshPrefix(config: SiteConfig): string {
  const parts = ['ssh'];
  if (config.ssh.key_path) parts.push(`-i "${config.ssh.key_path}"`);
  if (config.ssh.port && config.ssh.port !== 22) parts.push(`-p ${config.ssh.port}`);
  parts.push('-o BatchMode=yes -o ConnectTimeout=30');
  parts.push(`${config.ssh.user}@${config.ssh.host}`);
  return parts.join(' ');
}

function scpPrefix(config: SiteConfig): string {
  const parts = ['scp'];
  if (config.ssh.key_path) parts.push(`-i "${config.ssh.key_path}"`);
  if (config.ssh.port && config.ssh.port !== 22) parts.push(`-P ${config.ssh.port}`);
  parts.push('-o BatchMode=yes -o ConnectTimeout=30 -r');
  return parts.join(' ');
}

async function exec(shellCmd: string): Promise<{ stdout: string; stderr: string; code: number }> {
  try {
    const result = await Command.create('exec-sh', ['-c', `${PATH_SETUP}; ${shellCmd}`]).execute();
    return { stdout: result.stdout, stderr: result.stderr, code: result.code ?? -1 };
  } catch (e) {
    return { stdout: '', stderr: String(e), code: -1 };
  }
}

/**
 * Execute a command on the remote server via SSH.
 * Uses a bash heredoc to avoid quoting issues with the remote command.
 */
async function execRemote(config: SiteConfig, remoteScript: string): Promise<{ stdout: string; stderr: string; code: number }> {
  // Use bash heredoc to pass the script to SSH, avoiding all quoting issues.
  // The heredoc delimiter REMOTECMD must not appear in the script.
  const ssh = sshPrefix(config);
  const fullCmd = `${ssh} bash -s <<'REMOTECMD'\n${remoteScript}\nREMOTECMD`;
  return exec(fullCmd);
}

// ──────────────────────────────────────────────────────────────
// Archive pattern derivation
// ──────────────────────────────────────────────────────────────

/**
 * Derive a glob pattern from the configured archive_format by replacing
 * strftime tokens with '*'. This ensures that archives with custom name
 * prefixes (e.g. "mysite-wordpress-sync-backup_%Y-%m-%d_%H%M%S") are
 * found, rather than relying on hardcoded patterns.
 *
 * Also includes fallback patterns for common legacy names.
 */
function deriveArchivePatterns(config: SiteConfig): string[] {
  const fmt = config.backup?.archive_format || 'wordpress-sync-backup_%Y-%m-%d_%H%M%S';
  // Replace all strftime-style tokens (%Y, %m, %d, %H, %M, %S, etc.) with *
  const globbed = fmt.replace(/%[YmdHMS]/g, '*');

  // Build unique set of patterns, always including the derived one plus legacy fallbacks
  const patterns = new Set<string>();
  patterns.add(globbed);
  patterns.add('wordpress-sync-backup_*');
  patterns.add('wordpress-sync-trash_*');  // backward compat for old archive names
  patterns.add('backup-*');
  patterns.add('*.tar.gz');
  return [...patterns];
}

/**
 * Build the -name clause for find from a list of glob patterns.
 * e.g. ["foo-*", "bar-*"] → "\\( -name 'foo-*' -o -name 'bar-*' \\)"
 */
function buildNameClause(patterns: string[]): string {
  const parts = patterns.map(p => `-name '${p}'`);
  return `\\( ${parts.join(' -o ')} \\)`;
}

// ──────────────────────────────────────────────────────────────
// Listing — platform-aware scripts
// ──────────────────────────────────────────────────────────────

/**
 * Build a listing script for LOCAL (macOS).
 * Uses BSD stat -f format.
 * Output format per line: TYPE|SIZE_BYTES|DATE_ISO|FULL_PATH
 */
function buildLocalListScript(dir: string): string {
  return `if [ -d "${dir}" ]; then find "${dir}" -maxdepth 1 -mindepth 1 \\( -type f -o -type d \\) -exec stat -f '%HT|%z|%Sm|%N' -t '%Y-%m-%dT%H:%M:%S' {} \\; 2>/dev/null; fi`;
}

/**
 * Build a listing script for REMOTE (Linux).
 * Uses GNU find -printf which is available on virtually all Linux systems.
 * Output format per line: TYPE|SIZE_BYTES|EPOCH|FULL_PATH
 */
function buildRemoteListScript(dir: string): string {
  // %y = type letter (f/d/l), %s = size in bytes, %T@ = mod time as epoch, %p = full path
  return `if [ -d "${dir}" ]; then find "${dir}" -maxdepth 1 -mindepth 1 \\( -type f -o -type d \\) -printf '%y|%s|%T@|%p\\n' 2>/dev/null; fi`;
}

/**
 * Build archive-listing script for LOCAL (macOS).
 * Uses derived patterns from config instead of hardcoded ones.
 */
function buildLocalArchiveScript(archiveDir: string, config: SiteConfig): string {
  const nameClause = buildNameClause(deriveArchivePatterns(config));
  return `if [ -d "${archiveDir}" ]; then find "${archiveDir}" -maxdepth 1 -mindepth 1 ${nameClause} -exec stat -f '%HT|%z|%Sm|%N' -t '%Y-%m-%dT%H:%M:%S' {} \\; 2>/dev/null; fi`;
}

/**
 * Build archive-listing script for REMOTE (Linux).
 * Uses derived patterns from config instead of hardcoded ones.
 */
function buildRemoteArchiveScript(archiveDir: string, config: SiteConfig): string {
  const nameClause = buildNameClause(deriveArchivePatterns(config));
  return `if [ -d "${archiveDir}" ]; then find "${archiveDir}" -maxdepth 1 -mindepth 1 ${nameClause} -printf '%y|%s|%T@|%p\\n' 2>/dev/null; fi`;
}

// ──────────────────────────────────────────────────────────────
// Parsing — platform-aware
// ──────────────────────────────────────────────────────────────

/**
 * Parse LOCAL listing output (BSD stat format).
 * Expected: TYPE_WORD|SIZE_BYTES|DATE_ISO|FULL_PATH
 * e.g.: "Directory|4096|2025-06-15T14:30:00|/path/to/dir"
 *        "Regular File|1234|2025-06-15T14:30:00|/path/to/file.sql"
 */
function parseLocalListOutput(raw: string, category: BackupItem['category']): BackupItem[] {
  const items: BackupItem[] = [];
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.includes('No such file')) continue;

    const parts = trimmed.split('|');
    if (parts.length < 4) continue;

    const typeStr = parts[0];
    const sizeBytes = parseInt(parts[1], 10) || 0;
    const dateStr = parts[2];
    const fullPath = parts.slice(3).join('|');
    const name = fullPath.split('/').pop() || fullPath;

    items.push({
      name,
      path: fullPath,
      type: typeStr.toLowerCase().includes('directory') ? 'directory' : 'file',
      size: humanSize(sizeBytes),
      sizeBytes,
      date: dateStr,
      location: 'local',
      category,
    });
  }
  return items;
}

/**
 * Parse REMOTE listing output (GNU find -printf format).
 * Expected: TYPE_LETTER|SIZE_BYTES|EPOCH_FLOAT|FULL_PATH
 * e.g.: "d|4096|1718450000.0000000000|/path/to/dir"
 *        "f|1234|1718450000.0000000000|/path/to/file.sql"
 */
function parseRemoteListOutput(raw: string, category: BackupItem['category']): BackupItem[] {
  const items: BackupItem[] = [];
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.includes('No such file')) continue;

    const parts = trimmed.split('|');
    if (parts.length < 4) continue;

    const typeLetter = parts[0]; // 'f' or 'd'
    const sizeBytes = parseInt(parts[1], 10) || 0;
    const epochStr = parts[2];
    const fullPath = parts.slice(3).join('|');
    const name = fullPath.split('/').pop() || fullPath;

    // Convert epoch to ISO date string
    const epoch = parseFloat(epochStr) || 0;
    let dateStr: string;
    try {
      dateStr = new Date(epoch * 1000).toISOString().replace(/\.\d+Z$/, '');
    } catch {
      dateStr = epochStr;
    }

    items.push({
      name,
      path: fullPath,
      type: typeLetter === 'd' ? 'directory' : 'file',
      size: humanSize(sizeBytes),
      sizeBytes,
      date: dateStr,
      location: 'remote',
      category,
    });
  }
  return items;
}

function humanSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / Math.pow(1024, i);
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[i]}`;
}

// ──────────────────────────────────────────────────────────────
// Directory size fill-in
// ──────────────────────────────────────────────────────────────

async function fillDirectorySizes(items: BackupItem[], config: SiteConfig): Promise<BackupItem[]> {
  const dirs = items.filter(i => i.type === 'directory');
  if (dirs.length === 0) return items;

  const pathList = dirs.map(d => `"${d.path}"`).join(' ');

  let duOutput: string;
  if (dirs[0].location === 'remote') {
    // Linux: du -sb gives bytes
    const result = await execRemote(config, `du -sb ${pathList} 2>/dev/null`);
    duOutput = result.stdout;
  } else {
    // macOS: du -sk gives kilobytes
    const result = await exec(`du -sk ${pathList} 2>/dev/null`);
    duOutput = result.stdout;
  }

  const sizeMap = new Map<string, number>();
  for (const line of duOutput.split('\n')) {
    const match = line.match(/^(\d+)\s+(.+)$/);
    if (match) {
      const rawSize = parseInt(match[1], 10);
      const path = match[2].trim().replace(/\/+$/, '');
      const bytes = dirs[0].location === 'remote' ? rawSize : rawSize * 1024;
      sizeMap.set(path, bytes);
    }
  }

  return items.map(item => {
    const cleanPath = item.path.replace(/\/+$/, '');
    const bytes = sizeMap.get(cleanPath);
    if (bytes !== undefined) {
      return { ...item, sizeBytes: bytes, size: humanSize(bytes) };
    }
    return item;
  });
}

// ──────────────────────────────────────────────────────────────
// Main listing entry points
// ──────────────────────────────────────────────────────────────

/** List all backup items for a site on local (macOS). */
async function listLocalBackups(config: SiteConfig): Promise<BackupItem[]> {
  const latestDir = resolveLatestDir(config, 'local');
  const archivesDir = resolveArchivesDir(config, 'local');
  const dbDir = resolveDbBackupDir(config, 'local');

  const combined = [
    'echo "===LATEST==="',
    buildLocalListScript(latestDir),
    'echo "===ARCHIVES==="',
    buildLocalArchiveScript(archivesDir, config),
    'echo "===DB==="',
    buildLocalListScript(dbDir),
    'echo "===END==="',
  ].join('; ');

  const result = await exec(combined);
  const output = result.stdout;

  const latestSection = output.split('===LATEST===')[1]?.split('===ARCHIVES===')[0] ?? '';
  const archiveSection = output.split('===ARCHIVES===')[1]?.split('===DB===')[0] ?? '';
  const dbSection = output.split('===DB===')[1]?.split('===END===')[0] ?? '';

  const items: BackupItem[] = [
    ...parseLocalListOutput(latestSection, 'backup-latest'),
    ...parseLocalListOutput(archiveSection, 'backup-archive'),
    ...parseLocalListOutput(dbSection, 'db-backup'),
  ];

  return fillDirectorySizes(items, config);
}

/** List all backup items for a site on remote (Linux). */
async function listRemoteBackups(config: SiteConfig): Promise<BackupItem[]> {
  const latestDir = resolveLatestDir(config, 'remote');
  const archivesDir = resolveArchivesDir(config, 'remote');
  const dbDir = resolveDbBackupDir(config, 'remote');

  // Build the remote script using GNU find -printf (no quoting issues with heredoc)
  const remoteScript = [
    'echo "===LATEST==="',
    buildRemoteListScript(latestDir),
    'echo "===ARCHIVES==="',
    buildRemoteArchiveScript(archivesDir, config),
    'echo "===DB==="',
    buildRemoteListScript(dbDir),
    'echo "===END==="',
  ].join('\n');

  const result = await execRemote(config, remoteScript);
  if (result.code !== 0) {
    // SSH failed — might just mean directories don't exist yet
    return [];
  }
  const output = result.stdout;

  const latestSection = output.split('===LATEST===')[1]?.split('===ARCHIVES===')[0] ?? '';
  const archiveSection = output.split('===ARCHIVES===')[1]?.split('===DB===')[0] ?? '';
  const dbSection = output.split('===DB===')[1]?.split('===END===')[0] ?? '';

  const items: BackupItem[] = [
    ...parseRemoteListOutput(latestSection, 'backup-latest'),
    ...parseRemoteListOutput(archiveSection, 'backup-archive'),
    ...parseRemoteListOutput(dbSection, 'db-backup'),
  ];

  return fillDirectorySizes(items, config);
}

/** List all backups for a site (both local and remote). */
export async function listAllBackups(config: SiteConfig): Promise<BackupItem[]> {
  const [localItems, remoteItems] = await Promise.all([
    listLocalBackups(config).catch(() => [] as BackupItem[]),
    listRemoteBackups(config).catch(() => [] as BackupItem[]),
  ]);

  const all = [...localItems, ...remoteItems];
  all.sort((a, b) => {
    const da = new Date(a.date).getTime() || 0;
    const db = new Date(b.date).getTime() || 0;
    return db - da;
  });
  return all;
}

/** Compute a summary from a list of backup items. */
export function computeSummary(items: BackupItem[]): BackupSummary {
  const totalBytes = items.reduce((sum, i) => sum + i.sizeBytes, 0);
  return {
    totalSize: humanSize(totalBytes),
    totalSizeBytes: totalBytes,
    itemCount: items.length,
  };
}

// ──────────────────────────────────────────────────────────────
// Download (remote → local)
// ──────────────────────────────────────────────────────────────

export async function downloadBackup(
  config: SiteConfig,
  item: BackupItem,
  localDestDir: string,
): Promise<{ success: boolean; localPath?: string; error?: string }> {
  if (item.location !== 'remote') {
    return { success: false, error: 'Item is already local' };
  }

  const scp = scpPrefix(config);
  const remoteSrc = `${config.ssh.user}@${config.ssh.host}:"${item.path}"`;
  const cmd = `${scp} ${remoteSrc} "${localDestDir}/"`;

  const result = await exec(cmd);
  if (result.code === 0) {
    const localPath = `${localDestDir}/${item.name}`;
    return { success: true, localPath };
  }
  return { success: false, error: result.stderr.trim() || `scp exited with code ${result.code}` };
}

// ──────────────────────────────────────────────────────────────
// Delete
// ──────────────────────────────────────────────────────────────

/**
 * Move a local file or directory to the macOS Trash via Finder.
 * Items moved this way are restorable via Finder's "Put Back".
 */
async function trashLocalItem(itemPath: string): Promise<{ success: boolean; error?: string }> {
  // osascript: tell Finder to move the POSIX file to trash
  const script = `tell application "Finder" to delete (POSIX file "${itemPath}" as alias)`;
  const result = await exec(`osascript -e '${script.replace(/'/g, "'\\''")}'`);
  if (result.code === 0) {
    return { success: true };
  }
  return { success: false, error: result.stderr.trim() || `Move to Trash failed with code ${result.code}` };
}

/**
 * Delete a backup item.
 * - Local items are moved to macOS Trash (restorable).
 * - Remote items are permanently deleted.
 */
export async function deleteBackup(
  config: SiteConfig,
  item: BackupItem,
): Promise<{ success: boolean; trashed?: boolean; error?: string }> {
  if (item.location === 'local') {
    const result = await trashLocalItem(item.path);
    return { ...result, trashed: result.success };
  }

  // Remote: permanent delete
  const rmCmd = item.type === 'directory' ? `rm -rf "${item.path}"` : `rm -f "${item.path}"`;
  const result = await execRemote(config, rmCmd);
  if (result.code === 0) {
    return { success: true, trashed: false };
  }
  return { success: false, error: result.stderr.trim() || `Delete failed with code ${result.code}` };
}

// ──────────────────────────────────────────────────────────────
// Browse backup contents (recursive file listing)
// ──────────────────────────────────────────────────────────────

export interface BackupFileEntry {
  path: string;       // relative path within the backup/archive dir
  size: string;       // human-readable
  sizeBytes: number;
}

export async function browseBackupContents(
  config: SiteConfig,
  item: BackupItem,
): Promise<BackupFileEntry[]> {
  if (item.type !== 'directory') {
    return [{ path: item.name, size: item.size, sizeBytes: item.sizeBytes }];
  }

  let output: string;
  if (item.location === 'remote') {
    // Linux: use GNU find -printf for size|path
    const script = `find "${item.path}" -type f -printf '%s|%p\\n' 2>/dev/null`;
    const result = await execRemote(config, script);
    output = result.stdout;
  } else {
    // macOS: use BSD stat -f
    const script = `find "${item.path}" -type f -exec stat -f '%z|%N' {} \\; 2>/dev/null`;
    const result = await exec(script);
    output = result.stdout;
  }

  const entries: BackupFileEntry[] = [];
  const baseLen = item.path.length + (item.path.endsWith('/') ? 0 : 1);

  for (const line of output.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const pipeIdx = trimmed.indexOf('|');
    if (pipeIdx < 0) continue;
    const sizeBytes = parseInt(trimmed.substring(0, pipeIdx), 10) || 0;
    const fullPath = trimmed.substring(pipeIdx + 1);
    const relativePath = fullPath.substring(baseLen) || fullPath.split('/').pop() || fullPath;
    entries.push({ path: relativePath, size: humanSize(sizeBytes), sizeBytes });
  }

  entries.sort((a, b) => a.path.localeCompare(b.path));
  return entries;
}

// ──────────────────────────────────────────────────────────────
// Resolved path getters (for display)
// ──────────────────────────────────────────────────────────────

/** Get the resolved backup root directory for display. */
export function getBackupRootDir(config: SiteConfig, location: 'local' | 'remote'): string {
  return resolveBackupRoot(config, location);
}

/** Get the resolved latest backup directory for display. */
export function getLatestDir(config: SiteConfig, location: 'local' | 'remote'): string {
  return resolveLatestDir(config, location);
}

/** Get the resolved DB backup directory for display. */
export function getDbBackupDir(config: SiteConfig, location: 'local' | 'remote'): string {
  return resolveDbBackupDir(config, location);
}

/** Get the resolved archives directory for display. */
export function getArchivesDir(config: SiteConfig, location: 'local' | 'remote'): string {
  return resolveArchivesDir(config, location);
}

// ──────────────────────────────────────────────────────────────
// Post-sync backup cleanup
// ──────────────────────────────────────────────────────────────

/**
 * Check whether the latest backup directory has any files.
 * `direction` determines which side to check:
 *   - push → check remote (destination)
 *   - pull → check local (destination)
 */
export async function checkLatestHasContents(
  config: SiteConfig,
  direction: 'push' | 'pull',
): Promise<{ hasContents: boolean; fileCount: number; error?: string }> {
  const location = direction === 'push' ? 'remote' : 'local';
  const latestDir = resolveLatestDir(config, location);

  // Use test -d guard to handle non-existent directories gracefully
  const countCmd = `test -d "${latestDir}" && find "${latestDir}" -type f 2>/dev/null | wc -l || echo 0`;
  let result;
  if (location === 'remote') {
    result = await execRemote(config, countCmd);
  } else {
    result = await exec(countCmd);
  }

  if (result.code !== 0) {
    // Directory likely doesn't exist
    return { hasContents: false, fileCount: 0 };
  }

  const count = parseInt(result.stdout.trim(), 10) || 0;
  return { hasContents: count > 0, fileCount: count };
}

/**
 * Delete the latest backup directory contents.
 * For local: uses macOS Finder Trash (restorable).
 * For remote: permanent rm -rf.
 */
export async function deleteLatestContents(
  config: SiteConfig,
  direction: 'push' | 'pull',
): Promise<{ success: boolean; trashed?: boolean; error?: string }> {
  const location = direction === 'push' ? 'remote' : 'local';
  const latestDir = resolveLatestDir(config, location);

  if (location === 'local') {
    const r = await trashLocalItem(latestDir);
    return { ...r, trashed: r.success };
  }

  const result = await execRemote(config, `rm -rf "${latestDir}"`);
  if (result.code === 0) {
    return { success: true, trashed: false };
  }
  return { success: false, error: result.stderr.trim() || `rm failed with code ${result.code}` };
}

/**
 * Archive the latest backup directory by moving it into the archives dir
 * with the configured archive_format timestamp.
 * Mirrors the CLI's `handle_final_backup_cleanup` "keep/archive" behavior.
 */
export async function archiveLatestContents(
  config: SiteConfig,
  direction: 'push' | 'pull',
): Promise<{ success: boolean; archivePath?: string; error?: string }> {
  const location = direction === 'push' ? 'remote' : 'local';
  const latestDir = resolveLatestDir(config, location);
  const archivesDir = resolveArchivesDir(config, location);

  // Build the archive name using the configured format (strftime-style)
  const fmt = config.backup?.archive_format || 'wordpress-sync-backup_%Y-%m-%d_%H%M%S';
  const now = new Date();
  const archiveName = fmt
    .replace('%Y', String(now.getFullYear()))
    .replace('%m', String(now.getMonth() + 1).padStart(2, '0'))
    .replace('%d', String(now.getDate()).padStart(2, '0'))
    .replace('%H', String(now.getHours()).padStart(2, '0'))
    .replace('%M', String(now.getMinutes()).padStart(2, '0'))
    .replace('%S', String(now.getSeconds()).padStart(2, '0'));

  const archivePath = `${archivesDir}/${archiveName}`;

  // Ensure archives dir exists, then move latest into it
  const mkdirCmd = `mkdir -p "${archivesDir}"`;
  const mvCmd = `mv "${latestDir}" "${archivePath}"`;
  const fullCmd = `${mkdirCmd} && ${mvCmd}`;

  let result;
  if (location === 'remote') {
    result = await execRemote(config, fullCmd);
  } else {
    result = await exec(fullCmd);
  }

  if (result.code === 0) {
    return { success: true, archivePath };
  }
  return { success: false, error: result.stderr.trim() || `mv failed with code ${result.code}` };
}

// ──────────────────────────────────────────────────────────────
// Restore
// ──────────────────────────────────────────────────────────────

export interface RestoreResult {
  success: boolean;
  detail?: string;  // human-readable summary
  error?: string;
}

/**
 * Restore a file backup (archive or latest backup) by rsyncing its
 * contents back to the original WordPress directory.
 *
 * The backup directory mirrors the destination's directory tree, so
 * `rsync -av <backup>/ <destination>/` puts every file back in its
 * original location.
 *
 * - Local backup → local WordPress dir: plain rsync (no SSH).
 * - Remote backup → remote WordPress dir: rsync over SSH (remote-to-remote
 *   is done via SSH command on the remote host itself).
 */
export async function restoreFileBackup(
  config: SiteConfig,
  item: BackupItem,
): Promise<RestoreResult> {
  if (item.category !== 'backup-archive' && item.category !== 'backup-latest') {
    return { success: false, error: 'Item is not a file backup' };
  }
  if (item.type !== 'directory') {
    return { success: false, error: 'File backup must be a directory' };
  }

  const backupPath = item.path.replace(/\/+$/, '');
  const destPath = item.location === 'remote'
    ? config.paths.live.replace(/\/+$/, '')
    : config.paths.local.replace(/\/+$/, '');

  if (item.location === 'remote') {
    // Remote-to-remote: run rsync locally on the remote host via SSH
    const rsyncCmd = `rsync -av "${backupPath}/" "${destPath}/"`;
    const result = await execRemote(config, rsyncCmd);
    if (result.code === 0) {
      return { success: true, detail: `Restored files from ${item.name} to ${destPath}` };
    }
    return { success: false, error: result.stderr.trim() || `rsync failed with code ${result.code}` };
  } else {
    // Local-to-local: plain rsync, no SSH needed
    const rsyncCmd = `rsync -av "${backupPath}/" "${destPath}/"`;
    const result = await exec(rsyncCmd);
    if (result.code === 0) {
      return { success: true, detail: `Restored files from ${item.name} to ${destPath}` };
    }
    return { success: false, error: result.stderr.trim() || `rsync failed with code ${result.code}` };
  }
}

/**
 * Restore a database backup by importing the SQL file via wp-cli.
 *
 * Safety: always takes a fresh backup of the current database before
 * importing, so the user can undo the undo.
 *
 * - Local DB backup → import into local WordPress DB.
 * - Remote DB backup → import into remote WordPress DB via SSH.
 *
 * Returns the path to the safety backup on success.
 */
export async function restoreDbBackup(
  config: SiteConfig,
  item: BackupItem,
): Promise<RestoreResult & { safetyBackupPath?: string }> {
  if (item.category !== 'db-backup') {
    return { success: false, error: 'Item is not a database backup' };
  }
  if (!item.name.endsWith('.sql')) {
    return { success: false, error: 'Expected a .sql file' };
  }

  const isRemote = item.location === 'remote';
  const wpPath = isRemote ? config.paths.live : config.paths.local;

  // 1. Take a safety backup of the current database
  const now = new Date();
  const ts = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
    '-',
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0'),
  ].join('');
  const safetyFilename = `pre-restore-safety-${ts}.sql`;

  // Put the safety backup next to the backup being restored
  const backupDir = item.path.replace(/\/[^/]+$/, ''); // parent dir of the .sql file
  const safetyPath = `${backupDir}/${safetyFilename}`;

  const exportCmd = `wp --path="${wpPath}" db export "${safetyPath}" --allow-root 2>&1`;
  let exportResult;
  if (isRemote) {
    exportResult = await execRemote(config, exportCmd);
  } else {
    exportResult = await exec(exportCmd);
  }

  if (exportResult.code !== 0) {
    return {
      success: false,
      error: `Safety backup failed — aborting restore.\n${exportResult.stderr || exportResult.stdout}`.trim(),
    };
  }

  // 2. Import the backup
  const importCmd = `wp --path="${wpPath}" db import "${item.path}" --allow-root 2>&1`;
  let importResult;
  if (isRemote) {
    importResult = await execRemote(config, importCmd);
  } else {
    importResult = await exec(importCmd);
  }

  if (importResult.code === 0) {
    return {
      success: true,
      detail: `Database restored from ${item.name}`,
      safetyBackupPath: safetyPath,
    };
  }
  return {
    success: false,
    error: `Import failed: ${importResult.stderr || importResult.stdout}`.trim(),
    safetyBackupPath: safetyPath, // still return it — the safety backup exists
  };
}
