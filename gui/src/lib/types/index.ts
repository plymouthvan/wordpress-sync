// Site configuration (mirrors config.yaml)
export interface SiteConfig {
  name: string; // GUI-only field, not in YAML
  ssh: {
    user: string;
    host: string;
    port: number;
    key_path: string;
    sudo?: {
      user?: string;
      key_path?: string;
    };
  };
  paths: {
    local: string;
    live: string;
    /** Temp directory for DB export/import. New format: { local, remote }. Old format: plain string (backwards compat). */
    db_temp: string | { local: string; remote: string };
    db_filename: string;
  };
  domains: {
    staging: { http: string; https: string };
    live: { http: string; https: string };
  };
  rsync: {
    dry_run: boolean;
    delete: boolean;
    progress: boolean;
    verbose: boolean;
    compress: boolean;
    chmod_files: string;
    chmod_dirs: string;
    excludes: string[];
    cleanup_files: string[];
  };
  ownership: {
    user: string;
    group: string;
  };
  backup: {
    enabled: boolean;
    /** Unified backup root directory. New format: { local, remote }. Old format: plain string (backwards compat). */
    directory: string | { local: string; remote: string };
    archive_format: string;
    cleanup_prompt: boolean;
    database: {
      enabled: boolean;
      /** @deprecated — DB backups now live at <backup_dir>/db/. Kept for backwards compat with old configs. */
      directory?: string;
      filename_format: string;
    };
  };
  validation: {
    enabled: boolean;
    checks: {
      core_files: {
        enabled: boolean;
        verify_checksums: boolean;
        critical_files: string[];
      };
      database: {
        enabled: boolean;
        verify_core_tables: boolean;
        additional_tables: string[];
      };
      accessibility: {
        homepage: boolean;
        wp_admin: boolean;
      };
    };
  };
  plugins: {
    live: { activate: string[]; deactivate: string[] };
    local: { activate: string[]; deactivate: string[] };
  };
  operation: {
    direction: 'push' | 'pull';
  };
}

// Global settings
export interface AppSettings {
  cli_path: string;
  cli_version: string;
  theme: 'light' | 'dark' | 'system';
  log_retention_days: number;
  notifications_enabled: boolean;
  default_ssh_key: string;
}

// Sync history entry
export interface SyncHistoryEntry {
  id: string;
  site_name: string;
  direction: 'push' | 'pull';
  sync_type: 'full' | 'files-only' | 'db-only';
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  status: 'success' | 'failed' | 'cancelled';
  exit_code: number;
  log: string;
  config_snapshot: SiteConfig;
}

// Sync step status
export interface SyncStep {
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  output?: string;
}

// Diff entry from dry run
export interface DiffEntry {
  path: string;
  type: 'file' | 'directory';
  change: 'added' | 'modified' | 'deleted';
  size?: number;
  selected: boolean; // checkbox state
}

// Prerequisites check result
export interface PrerequisiteCheck {
  name: string;
  command: string;
  found: boolean;
  version?: string;
  path?: string;
  error?: string;
}
