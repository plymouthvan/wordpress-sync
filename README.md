# WordPress Sync

A tool to synchronize WordPress installations between staging and live environments. Includes both a **command-line interface** (Python) and a **desktop GUI application** (Tauri + Svelte 5) that wraps the CLI.

---

## Quick Start (GUI)

Get up and running in under 5 minutes.

### 1. Install the CLI

The GUI is a visual wrapper around the `wordpress-sync` CLI. Install it first:

```bash
cd cli/
pip install .
```

Verify it's working:
```bash
wordpress-sync --version
```

### 2. Launch the GUI

```bash
cd gui/
npm install
npm run tauri dev
```

> If the CLI isn't found on PATH, the GUI will show a banner offering to install it for you automatically.

### Before you start: Remote server requirements

Your remote (live) WordPress server needs the following in place before syncing:

- **SSH access** -- You must be able to SSH into the server using a key (not password). Test with: `ssh -i ~/.ssh/your_key user@host`
- **rsync installed** on the remote server (most Linux servers have it by default)
- **WP-CLI** (`wp`) installed on the remote server -- the CLI uses it for database export, import, search-replace, and cache flush. [Install guide](https://wp-cli.org/#installing)
- **An existing WordPress installation** on the remote with a valid `wp-config.php`
- **Write permissions** to the WordPress directory -- either as the SSH user, or via sudo (configure `ssh.sudo.user` in site config)

> **Tip:** The GUI's **Health Check** feature (available per-site from the sidebar) can test all of these for you and report what's missing.

### 3. Add your first site

1. Click **"+ New Site"** in the sidebar (or press **Cmd+N**)
2. Give it a name (e.g., "My Blog")
3. Fill in the basics:
   - **SSH** -- hostname, user, and path to your SSH key
   - **Paths** -- local WordPress directory and remote WordPress directory
   - **Domains** -- your staging and live URLs (used for database search-replace)
4. Click **Save**

That's it for configuration. Everything else has sensible defaults.

### 4. Pull from live (recommended first sync)

1. Click your site in the sidebar
2. Select **Pull** direction (remote -> local)
3. Click **Start Dry Run** -- this previews what would change without touching any files
4. Review the diff tree -- expand folders, check/uncheck files you want to include or skip
5. When you're satisfied, click **Start Sync**
6. Watch the 12-step progress tracker as it runs

### 5. Push to live

Same workflow, but select **Push** direction. The GUI shows an amber safety warning reminding you that push overwrites the live server. Backups are enabled by default.

### What else can you do?

- **Backup Manager** -- Browse, download, restore, or delete backup artifacts from past syncs
- **History** -- See every sync you've run, with full logs and the ability to re-run
- **Health Check** -- Test SSH connectivity, WordPress installation, and database access
- **Command Preview** -- See exactly what shell commands the CLI would execute
- **Settings** -- Check prerequisite tools, customize theme, view keyboard shortcuts

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Cmd+N | New site |
| Cmd+S | Save config |
| Cmd+, | Settings |
| Cmd+K | Search |

---

## What's New in v2.0.0

This release restructures the project as a **monorepo** (`cli/` + `gui/`) and adds a full-featured desktop GUI. The CLI remains fully standalone and backward-compatible.

### Repository Structure Change

The project has been reorganized from a flat Python project into a monorepo:

```
wordpress-sync/
  README.md
  LICENSE
  CHANGELOG.md
  cli/                 # Python CLI tool (moved from root)
    wordpress_sync.py
    pyproject.toml     # NEW: pip/pipx installable
    resources/
    config/
    ...
  gui/                 # NEW: Tauri desktop application
    src/               # Svelte 5 frontend
    src-tauri/         # Rust/Tauri backend
    ...
```

All CLI source files that previously lived at the repository root (`wordpress_sync.py`, `resources/`, `config/`, etc.) now live under `cli/`. No files were deleted or renamed -- only moved.

### CLI Changes (Backward-Compatible)

All CLI changes are **additive** -- existing behavior is preserved. New flags have safe defaults.

**New flags:**
- `--non-interactive` -- Run without interactive prompts. In dry-run mode, exits after showing changes. In sync mode, auto-accepts safe defaults for all prompts (always backs up, never deletes). This is the flag the GUI uses when spawning the CLI.
- `--version` -- Prints `wordpress-sync 2.0.0` and exits.
- `--itemize-changes` -- Adds rsync's `--itemize-changes` flag for structured per-file change output. The GUI uses this to build the visual diff tree.
- `--extra-rsync-args` -- Pass additional arguments through to rsync (e.g., `--bwlimit`, `--exclude-from`).

**Non-interactive mode safety measures:**
When `--non-interactive` is active, the CLI applies multiple layers of protection against hanging:

1. **Direct prompt guards** -- All 4 `input()` calls and 1 `getpass()` call in the codebase are guarded with `if self.non_interactive` checks that return safe defaults:
   - "Keep existing trash files?" -> Yes (archive, preserve data)
   - "Delete backed-up files?" -> No (archive, preserve data)
   - "Backup database before reset?" -> Yes (always backup)
   - "Proceed with synchronization?" -> Exit (let the caller decide)

2. **stdin redirect** -- `os.dup2(os.devnull, sys.stdin.fileno())` replaces stdin with `/dev/null` at the OS level, so all child processes (ssh, scp, rsync, wp-cli) receive EOF instead of inheriting a pipe that could cause them to hang.

3. **`builtins.input` monkeypatch** -- A safety net that replaces Python's global `input()` with a function that auto-responds based on keyword analysis (backup/keep/archive prompts get "yes", everything else gets "no"). Catches any `input()` call that was missed by the direct guards.

4. **`stdin=subprocess.DEVNULL`** -- Added to all 10 `subprocess.run()` and `subprocess.Popen()` calls in `ssh_manager.py` and `database_manager.py`. Defense-in-depth alongside the global stdin redirect.

5. **`BatchMode=yes` + `ConnectTimeout=30`** -- Added to all SSH and SCP commands when in non-interactive mode. SSH fails immediately if it can't authenticate (e.g., key not in agent) instead of prompting for a passphrase. Connection attempts time out after 30 seconds instead of hanging.

**Packaging:**
A new `pyproject.toml` makes the CLI installable via pip or pipx:
```bash
cd cli/
pip install .          # System install
pip install -e .       # Editable/development install
pipx install .         # Isolated install (recommended)
```
This creates a `wordpress-sync` executable on PATH, which is how the GUI discovers and invokes the CLI.

### Desktop GUI Application

The GUI is a native macOS desktop application built with **Tauri v2** (Rust) and **Svelte 5** (TypeScript). It wraps the CLI -- it does not reimplement sync logic. The GUI constructs YAML configs, builds CLI arguments, spawns the CLI as a child process, and streams its output in real time.

---

## Features

### CLI Features
- Bi-directional sync (push to live or pull from live)
- Automated validation of WordPress core files and database
- File sync via `rsync` with backup/trash management
- Database export/import with URL rewriting via WP-CLI
- Automatic maintenance mode during sync
- File permission and ownership management
- Flexible YAML configuration
- Dry-run by default with user confirmation
- Command-only mode for auditing (`--command-only`)
- Non-interactive mode for GUI/scripted use (`--non-interactive`)

### GUI Features
- **Multi-site management** -- Configure and manage multiple WordPress sites from a single interface. Site configs are stored as YAML files in `~/.wordpress-sync/sites/`.
- **Visual configuration editor** -- All YAML options exposed as form controls across 9 collapsible sections (SSH, Paths, Domains, Rsync, Backup, Ownership, Validation, Plugins, Operation). Raw YAML editor available as a power-user escape hatch.
- **Sync execution with real-time streaming** -- 5-phase workflow: Options -> Dry Run -> Diff Viewer -> Syncing -> Complete. Output streams in real time with batched rendering (250ms throttle, max 4 updates/sec) to prevent UI freeze.
- **Dry run diff viewer** -- Transforms rsync's itemize-changes output into a collapsible directory tree with tri-state checkboxes for selective file exclusion, filtering by change type (added/modified/deleted), size filtering, and search.
- **12-step sync tracker** -- Visual stepper showing progress through all 12 CLI sync steps with automatic detection of skipped steps.
- **Backup Manager** -- Browse, download, restore, and delete backup artifacts (trash archives, current trash, database backups) from both local and remote. Supports bulk operations with multi-select.
- **File restore** -- Rsync a trash archive back to the WordPress directory, putting every file back in its original location.
- **Database restore** -- Import a SQL backup via `wp db import`. Always takes a safety backup of the current database first.
- **Post-sync trash cleanup** -- After a successful sync, optionally prompts to delete or archive backed-up files (controlled by `backup.cleanup_prompt` config).
- **Sync history** -- Persisted to `~/.wordpress-sync/history/` as JSON files. Filterable table with log viewer, re-run, and delete.
- **Health checks** -- Diagnostic checks for SSH connectivity, WordPress installation, database, and tools.
- **Command preview** -- Shows all shell commands the CLI would execute, organized by section.
- **CLI auto-detection and installation** -- Detects `wordpress-sync` on PATH at launch. If missing, offers one-click installation via pipx or pip.
- **Built-in terminal** -- Collapsible panel showing all command execution output with color-coded log levels.
- **Keyboard shortcuts** -- Cmd+N (new site), Cmd+S (save config), Cmd+, (settings), Cmd+K (search).

---

## Prerequisites

- **Python 3.8+**
- **SSH key-based authentication** to the remote server
- **WP-CLI** (`wp`) installed locally and on the remote server
- **rsync** and **scp** available locally
- Existing WordPress installations on both local and remote with valid `wp-config.php` files

For the GUI additionally:
- **macOS** (v1 is macOS-only; Windows/Linux are future)
- **Node.js 18+** and **npm** (for development)
- **Rust toolchain** (for building the Tauri backend)

---

## Installation

### CLI Only

```bash
cd cli/

# Option 1: pipx (recommended -- isolated environment)
pipx install .

# Option 2: pip
pip install .

# Option 3: editable install (for development)
pip install -e .
```

After installation, `wordpress-sync` is available on PATH:
```bash
wordpress-sync --version
wordpress-sync --direction pull --config /path/to/config.yaml
```

### GUI Application

```bash
cd gui/

# Install dependencies
npm install

# Development mode (hot-reload)
npm run tauri dev

# Production build
npm run tauri build
```

The GUI will automatically detect the CLI on PATH. If not found, it offers to install it for you.

---

## Configuration

### CLI Configuration

The CLI reads a YAML config file passed via `--config`. Example:

```yaml
ssh:
  user: username
  host: example.com
  port: 22
  key_path: ~/.ssh/id_rsa
  sudo:
    user: root              # Optional: dedicated sudo user
    key_path: ~/.ssh/root   # Optional: separate SSH key for sudo

operation:
  direction: "pull"

paths:
  local: /Users/me/Sites/wordpress/
  live: /var/www/html/wordpress/
  db_temp: /tmp/
  db_filename: wordpress-sync-database.sql

domains:
  staging:
    http: http://staging.example.com
    https: https://staging.example.com
  live:
    http: http://www.example.com
    https: https://www.example.com

rsync:
  dry_run: true
  delete: true
  progress: true
  verbose: true
  compress: true
  chmod_files: "664"
  chmod_dirs: "775"
  excludes:
    - "wp-config.php"
  cleanup_files:
    - ".DS_Store"

ownership:
  user: www-data
  group: www-data

backup:
  enabled: true
  directory: "../wordpress-sync-trash"
  archive_format: "wordpress-sync-trash_%Y-%m-%d_%H%M%S"
  cleanup_prompt: true
  database:
    enabled: true
    directory: "../wordpress-sync-db-backups"
    filename_format: "db-backup_%Y-%m-%d_%H%M%S.sql"

validation:
  enabled: true
  checks:
    core_files:
      enabled: true
      verify_checksums: true
      critical_files:
        - "wp-config.php"
        - "wp-content/index.php"
        - ".htaccess"
    database:
      enabled: true
      verify_core_tables: true
    accessibility:
      homepage: true
      wp_admin: true
```

See `cli/config/config.yaml.sample` for a fully documented template.

### GUI Configuration

The GUI stores its data in `~/.wordpress-sync/`:
```
~/.wordpress-sync/
  settings.json          # Global app settings (theme, CLI path, etc.)
  sites/                 # Site YAML configs (one per site)
    my-site.yaml
    another-site.yaml
  history/               # Sync history entries (one JSON per sync)
    2026-02-14T...json
```

Site configs use the same YAML format as the CLI. The GUI's config editor produces configs that the CLI can read directly.

---

## CLI Usage

```bash
# Pull live server changes to local (dry-run first, then confirm)
wordpress-sync --direction pull --config config.yaml

# Push local changes to live
wordpress-sync --direction push --config config.yaml

# Skip dry-run and sync immediately
wordpress-sync --direction push --config config.yaml --no-dry-run

# Files only (no database)
wordpress-sync --direction pull --config config.yaml --files-only

# Database only (no files)
wordpress-sync --direction pull --config config.yaml --db-only

# Preview commands without executing
wordpress-sync --direction push --config config.yaml --command-only

# Non-interactive mode (for GUI/scripted use)
wordpress-sync --direction pull --config config.yaml --non-interactive

# With itemize-changes output (machine-parseable)
wordpress-sync --direction pull --config config.yaml --non-interactive --itemize-changes

# Skip specific checks
wordpress-sync --direction pull --config config.yaml --skip-validation
wordpress-sync --direction pull --config config.yaml --skip-wp-check

# Disable file backup to trash
wordpress-sync --direction push --config config.yaml --no-trash

# Pass extra args to rsync
wordpress-sync --direction push --config config.yaml --extra-rsync-args "--bwlimit=1000"

# Provide sudo password for remote operations
wordpress-sync --direction push --config config.yaml --sudo-password "password"
```

### Sync Workflow

1. Activate maintenance mode on both environments
2. Run a dry-run preview of file changes (default)
3. Prompt for user confirmation
4. Transfer files via rsync (with `--backup-dir` for trash)
5. Export/import database and rewrite URLs
6. Set file permissions and ownership
7. Run validation checks
8. Flush caches
9. Disable maintenance mode
10. Clean up temporary files
11. Handle trash (archive or delete backed-up files)

---

## Backup and Restore

### How Backups Work

**File backups:** During rsync, the `--backup` and `--backup-dir` flags cause any overwritten or deleted files to be moved to the trash directory. The directory structure is preserved -- e.g., if `wp-content/themes/style.css` is overwritten, it appears at `<trash>/wp-content/themes/style.css`.

**Database backups:** Before a database reset/import, a `wp db export` creates a timestamped SQL dump in the DB backup directory.

**Backup location:** Backups are always created on the **destination** side:
- Push (local -> remote): backups on the remote server
- Pull (remote -> local): backups on the local machine

### Restoring from Backups (GUI)

The Backup Manager in the GUI provides restore functionality:

**File restore:** Select a trash archive and click the restore button. The GUI rsyncs the archive's contents back to the WordPress directory, putting every file back in its original location. Works for both local and remote backups.

**Database restore:** Select a `.sql` backup and click restore. The GUI:
1. Takes a safety backup of the current database (so you can undo the undo)
2. Imports the selected backup via `wp db import`
3. Shows the safety backup path in case you need to roll back

### Trash Cleanup

After a sync, if `backup.cleanup_prompt` is enabled in the site config, the GUI prompts:
- **Delete** -- Removes the trash directory (local items go to macOS Trash and are restorable via Finder; remote items are permanently deleted)
- **Keep (Archive)** -- Renames the trash directory with a timestamp using the `archive_format` pattern

### Configuration

```yaml
backup:
  enabled: true                                    # Enable file backup during rsync
  directory: "../wordpress-sync-trash"             # Trash directory (relative to site root)
  archive_format: "wordpress-sync-trash_%Y-%m-%d_%H%M%S"  # Timestamp format for archives
  cleanup_prompt: true                             # Prompt to clean up after sync (GUI only)
  database:
    enabled: true                                  # Enable DB backup before import
    directory: "../wordpress-sync-db-backups"       # DB backup directory
    filename_format: "db-backup_%Y-%m-%d_%H%M%S.sql"
```

Use `--no-trash` on the CLI (or the "No Trash" checkbox in the GUI) to disable file backups.

---

## Understanding Excludes vs. Cleanup Files

- **excludes** -- Files completely ignored by rsync. They are not transferred and not deleted from the destination. Example: `wp-config.php`.
- **cleanup_files** -- Files deleted from the destination *before* rsync runs. This prevents them from blocking rsync's ability to remove empty directories. Example: `.DS_Store`.

---

## Validation Checks

After synchronization, the tool validates the WordPress installation:

- **Core files** -- `wp core verify-checksums`, presence of critical files (`wp-config.php`, `.htaccess`, etc.)
- **Database** -- All WordPress core tables exist, custom tables accessible
- **Accessibility** -- Homepage returns 200, wp-admin login page loads

---

## Architecture

### Monorepo Layout

```
cli/                          # Python CLI tool
  wordpress_sync.py           # Main entry point, 12-step sync orchestrator
  pyproject.toml              # Python packaging (pip/pipx installable)
  resources/
    ssh_manager.py            # SSH/SCP/rsync operations
    database_manager.py       # WP-CLI database export/import/reset
    config_manager.py         # YAML config loading
    url_manager.py            # Domain URL search-replace
    validation_manager.py     # Post-sync validation checks
    maintenance_manager.py    # Maintenance mode toggle
    plugin_manager.py         # WordPress plugin management
    password_manager.py       # Sudo password handling
    command_collector.py      # --command-only output
  config/
    config.yaml.sample        # Annotated config template

gui/                          # Tauri desktop application
  src/                        # Svelte 5 frontend
    routes/+page.svelte       # Main router (string-based client-side routing)
    views/                    # 8 page-level views
    components/               # Reusable UI components
    lib/
      services/               # Backend integration (CLI, backup, config, history)
      stores/                 # Svelte stores (terminal, sites, settings, sync)
      utils/                  # Parsers, tree builder, theme
      types/                  # TypeScript interfaces
  src-tauri/                  # Rust/Tauri backend
    capabilities/             # Shell and FS permission definitions
    src/                      # Rust entry point (plugin registration only)
```

### How the GUI Wraps the CLI

1. The GUI detects `wordpress-sync` on PATH (checking `/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`, `~/Library/Python/*/bin`, etc.)
2. It constructs a YAML config file in `~/.wordpress-sync/sites/`
3. It spawns the CLI via Tauri's shell plugin: `wordpress-sync --config <path> --non-interactive --itemize-changes --direction <dir> [flags]`
4. Output is streamed in real time via `spawn()` event handlers
5. Step markers (`Step N:`) are parsed for the progress tracker
6. Itemize-changes output is parsed into a structured diff tree
7. Post-sync cleanup is handled by the GUI itself (not the CLI)

### Key Technical Details

- **macOS PATH issue:** Tauri processes inherit a minimal PATH (`/usr/bin:/bin`). A `PATH_SETUP` constant is prepended to every shell command, adding Homebrew, pip, and pipx paths. It also recovers `SSH_AUTH_SOCK` via `launchctl getenv` and sets `PYTHONUNBUFFERED=1`.
- **Output batching:** CLI output is buffered for 250ms before flushing to the Svelte store, limiting UI updates to 4/sec during rapid output.
- **Platform-aware commands:** Local backup listing uses macOS BSD tools (`stat -f`); remote uses Linux GNU tools (`find -printf`). SSH commands use heredocs (`<<'REMOTECMD'`) to avoid quoting issues.
- **Local delete uses macOS Trash:** When deleting local backup items, the GUI moves them to Finder Trash via `osascript` so they're restorable. Remote items are permanently deleted with a warning dialog.

---

## Sudo Password Handling

The CLI supports four methods for sudo operations (used when pushing to set permissions on the remote server):

1. **Dedicated sudo user** (most secure) -- Configure `ssh.sudo.user` and optionally `ssh.sudo.key_path` in the config
2. **NOPASSWD sudo** -- Configure the server to allow passwordless sudo
3. **Command-line password** -- Pass `--sudo-password "..."` (appears in process list)
4. **Interactive prompt** -- The CLI prompts securely via `getpass()` (CLI-only, not available in non-interactive mode)

---

## Staging Environment Visual Indicator

An optional mu-plugin (`cli/staging_etc/mu-plugins/admin-bar-color-for-staging.php`) changes the WordPress admin bar to orange on staging sites. Copy it to your staging site's `wp-content/mu-plugins/` directory. It's excluded from sync by default.

---

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)

Free to use, copy, modify, and redistribute for any noncommercial purpose. Commercial distribution and resale of derivative works are not permitted. See [LICENSE](LICENSE) for full terms.
