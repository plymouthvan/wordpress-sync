# Changelog

All notable changes to this project will be documented in this file.

## [2.1.0] - 2026-02-23

### Added

**Unified backup directory structure:**
- All backups (files, archives, database) are now stored under a single configurable root with three subdirectories:
  - `latest/` -- rsync's `--backup-dir` target (replaces the old flat trash directory)
  - `archives/` -- timestamped snapshots created when archiving the latest backup
  - `db/` -- database SQL dumps (replaces the old separate `backup.database.directory`)
- Old flat directory layout and separate DB backup directory are still recognized for backward compatibility

**Split local/remote config paths:**
- `backup.directory` now accepts a `{ local: "...", remote: "..." }` dict so local and remote backup roots can differ. Old single-string format still supported.
- `paths.db_temp` now accepts a `{ local: "...", remote: "..." }` dict so local and remote staging directories can differ. Old single-string format still supported.

**New CLI flags:**
- `--no-backup` -- Disable file backup during sync (replaces `--no-trash`, which is kept as a backward-compatible alias)
- `--skip-final-cleanup` -- Skip the post-sync backup cleanup step (step 11), allowing the GUI to own that dialog instead of the CLI silently archiving in non-interactive mode

**GUI enhancements:**
- Config auto-normalization: old-format configs are automatically migrated to the new `{ local, remote }` dict format on load (`normalizeBackupConfig`, `normalizeDbTempConfig`)
- Browse buttons added to config editor for local backup directory, local DB temp directory, and local WordPress path (native macOS directory picker)
- Resolved path preview in the Backup config section showing the full directory tree (`root/`, `├─ latest/`, `├─ archives/`, `└─ db/`) for both local and remote
- "Show in Finder" button in Backup Manager for local backup items
- Paths config section reorganized into "WordPress Directories", "Database Temp Directories", and "DB Export Filename" groups with separate local/remote inputs
- SvelteKit `$lib` convention adopted: GUI services, stores, types, and utilities now live in `gui/src/lib/` with `$lib/` import aliases

### Changed

**Rename "trash" to "backup" throughout the codebase:**
- On-disk directory renamed from `trash/` to `latest/` inside the backup root
- Default `archive_format` changed from `wordpress-sync-trash_*` to `wordpress-sync-backup_*`
- All UI labels updated: "Current Trash" -> "Latest Backup", "Trash Archive" -> "Backup Archive", "No Trash" -> "Skip File Backup", "Trash Management" -> "Backup Management", "Backup & Trash" -> "Backups"
- Config key `no_trash` still recognized for backward compatibility alongside `no_backup`
- Existing `trash/` directories and `wordpress-sync-trash_*` archive patterns are still recognized for backward compatibility

**CLI internals:**
- `_get_trash_path()` replaced by `_resolve_backup_root()`, `_get_latest_backup_path()`, and `_get_archives_path()`
- `handle_existing_trash()` renamed to `handle_existing_backup()`
- `handle_final_trash_cleanup()` renamed to `handle_final_backup_cleanup()`
- All inline `db_temp` and `db_backup_dir` resolution consolidated into dedicated helper methods
- `checkLatestHasContents()` hardened with a `test -d` guard before listing directory contents

**GUI internals:**
- Backup service: `getTrashDir` -> `getLatestDir`, `checkTrashHasContents` -> `checkLatestHasContents`, `deleteTrashContents` -> `deleteLatestContents`, `archiveTrashContents` -> `archiveLatestContents`
- `TrashFileEntry` type renamed to `BackupFileEntry`
- Backup Manager directory display expanded from 2 rows to 6, showing root, latest, archives, and DB paths for both local and remote

### Deprecated

- `backup.database.directory` config key -- DB backups are now stored automatically at `<backup_root>/db/`. The old key is still read for backward compatibility but is no longer included in default configs or the sample config.

## [2.0.0] - 2026-02-14

### Added

**Monorepo restructure:**
- Reorganized project into `cli/` + `gui/` monorepo layout
- All existing CLI files moved under `cli/` (no files deleted or renamed)

**CLI -- new flags (backward-compatible):**
- `--non-interactive` -- Run without prompts; auto-accepts safe defaults (always backs up, never deletes); used by the GUI when spawning the CLI
- `--version` -- Print version and exit
- `--itemize-changes` -- Pass rsync's `--itemize-changes` for structured per-file change output
- `--extra-rsync-args` -- Pass additional arguments through to rsync

**CLI -- non-interactive safety layers:**
- Direct guards on all 4 `input()` calls and 1 `getpass()` call with safe defaults
- `os.dup2(devnull, stdin)` to prevent child process hangs
- `builtins.input` monkeypatch as a catch-all safety net
- `stdin=subprocess.DEVNULL` on all subprocess calls in `ssh_manager.py` and `database_manager.py`
- `BatchMode=yes` + `ConnectTimeout=30` on all SSH/SCP commands in non-interactive mode

**CLI -- packaging:**
- Added `pyproject.toml` for pip/pipx installation (`wordpress-sync` command on PATH)

**Desktop GUI application (Tauri v2 + Svelte 5):**
- Multi-site management with YAML configs stored in `~/.wordpress-sync/sites/`
- Visual configuration editor with 9 collapsible sections and raw YAML tab
- Show in Finder button on YAML tab to reveal the config file
- 5-phase sync workflow: Options, Dry Run, Diff Viewer, Syncing, Complete
- Dry run diff viewer with collapsible directory tree, tri-state checkboxes, change-type and size filters, and search
- 12-step progress tracker matching all CLI sync steps with skipped-step detection
- Backup Manager: browse, download, restore, and delete backup artifacts (trash archives + database backups) from local and remote
- File restore via rsync (puts files back in original locations)
- Database restore via `wp db import` with automatic safety backup of current database
- Bulk operations in Backup Manager (multi-select, bulk download, bulk delete)
- Post-sync trash cleanup prompt (delete via macOS Trash or archive with timestamp)
- Sync history persisted as JSON files with filterable table, log viewer, and re-run
- Health checks for SSH connectivity, WordPress installation, database, and tools
- Command preview showing all shell commands the CLI would execute
- CLI auto-detection on PATH with one-click install via pipx or pip
- Built-in collapsible terminal panel with color-coded log output
- Streaming output with 250ms batched rendering to prevent UI freeze
- macOS PATH resolution for Homebrew, pipx, and pip install locations
- SSH_AUTH_SOCK recovery via `launchctl getenv` for passphrase-protected keys
- Keyboard shortcuts: Cmd+N (new site), Cmd+S (save), Cmd+, (settings), Cmd+K (search)
- Local deletes use macOS Finder Trash (restorable via Put Back)
- Remote deletes show explicit permanent-deletion warning dialog

### Changed
- License changed from MIT to PolyForm Noncommercial 1.0.0
- README completely rewritten with Quick Start guide, full feature documentation, architecture overview, and backup/restore reference

## [1.1.0] - 2025-03-24

### Added
- New trash directory functionality for safer file operations
  - Files are now moved to a temporary trash directory instead of being directly deleted
  - Added option to save or delete trashed files after operations complete
- New `--no-trash` option to skip backup of deleted/modified files entirely
- Added option to backup destination database before importing source database
- Backup management system in SSHManager

### Changed
- Enhanced database operations with timing capabilities
- Updated documentation with new command options
