import { readTextFile, writeTextFile, mkdir, exists, readDir } from '@tauri-apps/plugin-fs';
import { homeDir, join } from '@tauri-apps/api/path';
import YAML from 'yaml';
import type { SiteConfig, AppSettings } from '$lib/types';

const CONFIG_DIR = '.wordpress-sync';
const SITES_DIR = 'sites';
const HISTORY_DIR = 'history';
const SETTINGS_FILE = 'settings.json';

const DEFAULT_SETTINGS: AppSettings = {
  cli_path: '',
  cli_version: '',
  theme: 'system',
  log_retention_days: 30,
  notifications_enabled: true,
  default_ssh_key: '~/.ssh/id_rsa'
};

/**
 * Get the base config directory path (~/.wordpress-sync).
 */
export async function getConfigDir(): Promise<string> {
  const home = await homeDir();
  return await join(home, CONFIG_DIR);
}

/**
 * Ensure all required config directories exist.
 */
export async function ensureConfigDirs(): Promise<void> {
  const configDir = await getConfigDir();
  const sitesDir = await join(configDir, SITES_DIR);
  const historyDir = await join(configDir, HISTORY_DIR);

  for (const dir of [configDir, sitesDir, historyDir]) {
    if (!(await exists(dir))) {
      await mkdir(dir, { recursive: true });
    }
  }
}

/**
 * Load global application settings, returning defaults if none exist.
 */
export async function loadSettings(): Promise<AppSettings> {
  try {
    const configDir = await getConfigDir();
    const settingsPath = await join(configDir, SETTINGS_FILE);

    if (await exists(settingsPath)) {
      const raw = await readTextFile(settingsPath);
      const parsed = JSON.parse(raw) as Partial<AppSettings>;
      return { ...DEFAULT_SETTINGS, ...parsed };
    }
  } catch (e) {
    console.warn('Failed to load settings, using defaults:', e);
  }
  return { ...DEFAULT_SETTINGS };
}

/**
 * Save global application settings to disk.
 */
export async function saveSettings(settings: AppSettings): Promise<void> {
  const configDir = await getConfigDir();
  await ensureConfigDirs();
  const settingsPath = await join(configDir, SETTINGS_FILE);
  await writeTextFile(settingsPath, JSON.stringify(settings, null, 2));
}

/**
 * List all site config files (returns names without .yaml extension).
 */
export async function listSites(): Promise<string[]> {
  try {
    const configDir = await getConfigDir();
    const sitesDir = await join(configDir, SITES_DIR);

    if (!(await exists(sitesDir))) {
      return [];
    }

    const entries = await readDir(sitesDir);
    return entries
      .filter((entry) => entry.name?.endsWith('.yaml') || entry.name?.endsWith('.yml'))
      .map((entry) => entry.name!.replace(/\.ya?ml$/, ''))
      .sort();
  } catch (e) {
    console.warn('Failed to list sites:', e);
    return [];
  }
}

/**
 * Default backup directory value used when no config is present.
 * Matches the unified default across CLI and GUI.
 */
const DEFAULT_BACKUP_DIR = '../wordpress-sync-backups';

/**
 * Detect whether a backup config uses the old format (string directory + separate database.directory)
 * and return true if so.
 */
export function isLegacyBackupConfig(config: SiteConfig): boolean {
  return typeof config.backup?.directory === 'string';
}

/**
 * Normalize a site config's backup section.
 *
 * Old format (string directory + separate database.directory):
 *   backup:
 *     directory: "../wordpress-sync-backups"
 *     database:
 *       directory: "../wordpress-sync-db-backups"
 *
 * New format (object directory, no database.directory):
 *   backup:
 *     directory:
 *       local: "../wordpress-sync-backups"
 *       remote: "../wordpress-sync-backups"
 *     database:
 *       filename_format: "..."
 *
 * If the config is already in new format, it is returned unchanged.
 * The original object is NOT mutated; a new config is returned.
 */
export function normalizeBackupConfig(config: SiteConfig): SiteConfig {
  if (!config.backup) return config;

  // Already in new format (directory is an object with local/remote)
  if (typeof config.backup.directory === 'object' && config.backup.directory !== null) {
    return config;
  }

  // Old format: directory is a string (or missing)
  const oldDir = (typeof config.backup.directory === 'string' && config.backup.directory)
    ? config.backup.directory
    : DEFAULT_BACKUP_DIR;

  return {
    ...config,
    backup: {
      ...config.backup,
      directory: {
        local: oldDir,
        remote: oldDir,
      },
      database: {
        ...config.backup.database,
        // Clear the deprecated directory field — DB backups now live at <backup_dir>/db/
        directory: undefined,
      },
    },
  };
}

/**
 * Default DB temp directory value used when no config is present.
 */
const DEFAULT_DB_TEMP = '/tmp';

/**
 * Detect whether a paths config uses the old format (string db_temp).
 */
export function isLegacyDbTempConfig(config: SiteConfig): boolean {
  return typeof config.paths?.db_temp === 'string';
}

/**
 * Normalize a site config's paths.db_temp field.
 *
 * Old format (single string used for both environments):
 *   paths:
 *     db_temp: "/tmp"
 *
 * New format (object with local/remote):
 *   paths:
 *     db_temp:
 *       local: "/tmp"
 *       remote: "/tmp"
 *
 * If the config is already in new format, it is returned unchanged.
 * The original object is NOT mutated; a new config is returned.
 */
export function normalizeDbTempConfig(config: SiteConfig): SiteConfig {
  if (!config.paths) return config;

  // Already in new format
  if (typeof config.paths.db_temp === 'object' && config.paths.db_temp !== null) {
    return config;
  }

  const oldVal = (typeof config.paths.db_temp === 'string' && config.paths.db_temp)
    ? config.paths.db_temp
    : DEFAULT_DB_TEMP;

  return {
    ...config,
    paths: {
      ...config.paths,
      db_temp: {
        local: oldVal,
        remote: oldVal,
      },
    },
  };
}

/**
 * Load a site configuration from its YAML file.
 */
export async function loadSiteConfig(name: string): Promise<SiteConfig> {
  const configDir = await getConfigDir();
  const filePath = await join(configDir, SITES_DIR, `${name}.yaml`);
  const raw = await readTextFile(filePath);
  const parsed = YAML.parse(raw) as Omit<SiteConfig, 'name'>;
  return { name, ...parsed };
}

/**
 * Save a site configuration to its YAML file.
 */
export async function saveSiteConfig(name: string, config: SiteConfig): Promise<void> {
  const configDir = await getConfigDir();
  await ensureConfigDirs();
  const filePath = await join(configDir, SITES_DIR, `${name}.yaml`);

  // Strip the GUI-only 'name' field before writing YAML
  const { name: _name, ...yamlData } = config;
  const yamlStr = YAML.stringify(yamlData, { indent: 2 });
  await writeTextFile(filePath, yamlStr);
}

/**
 * Delete a site configuration file.
 */
export async function deleteSiteConfig(name: string): Promise<void> {
  const configDir = await getConfigDir();
  const filePath = await join(configDir, SITES_DIR, `${name}.yaml`);
  // Use Tauri's remove through the fs plugin
  const { remove } = await import('@tauri-apps/plugin-fs');
  await remove(filePath);
}

/**
 * Get the full path to a site config file.
 */
export async function getSiteConfigPath(name: string): Promise<string> {
  const configDir = await getConfigDir();
  return await join(configDir, SITES_DIR, `${name}.yaml`);
}
