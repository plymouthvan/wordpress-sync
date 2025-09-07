# WordPress Sync

A command-line tool to automate WordPress synchronization between your local staging site and your live server.

---

## 🚀 Features

- Bi-directional sync support (push to live or pull from live)
- Automated validation of core WordPress files and database
- Syncs WordPress files using `rsync`
- Handles database export/import and URL rewriting
- Puts sites into maintenance mode automatically during synchronization
- Respects file permissions and ownership
- Uses a flexible YAML config file for all environment-specific settings
- Runs a dry-run by default to preview changes before committing
- User confirmation required to proceed with the actual synchronization after dry run

---

## 📁 Directory Structure

wordpress-sync/
├── wordpress_sync.py      # Main script
├── wordpress-sync         # Wrapper script (created during installation)
├── resources/             # Resource managers
│   ├── config_manager.py
│   ├── ssh_manager.py
│   ├── database_manager.py
│   ├── url_manager.py
│   ├── maintenance_manager.py
│   └── validation_manager.py
├── config/                # Configuration files
│   ├── config.yaml
│   └── config.yaml.sample
├── venv/                  # Virtual environment (created during installation)
├── install.sh             # Installation script
└── README.md

---

## 🛠️ Prerequisites

- Python 3.8+
- SSH key-based login to the server (no password prompts)
- WordPress CLI (`wp`) installed locally and on the server
- `rsync` and `scp` available locally
- Existing WordPress installations on both ends with:
  - Valid wp-config.php files
  - Working database connections
  - Appropriate file permissions
- Sufficient disk space for:
  - Database export files
  - Temporary files during transfer
  - File synchronization

## 🔧 Installation

1. Clone or download this repository
2. Run the installation script:
   ```bash
   ./install.sh
   ```
   This will:
   - Create a Python virtual environment
   - Install all required dependencies
   - Make scripts executable
   - Create a wrapper script for easy execution

---

## ⚙️ Configuration

All environment settings are stored in `config.yaml`. Example:

```yaml
ssh:
  user: username
  host: 0.0.0.0
  port: 22  # Optional: SSH port (default: 22)
  key_path: path/to/ssh/keys

operation:
  direction: "push"  # Options: "push" (local to live) or "pull" (live to local)

paths:
  local: /path/to/local/site/
  live: /path/to/live/site/
  db_temp: /tmp/
  db_filename: wordpress-sync-database.sql

ownership:
  user: username
  group: username

rsync:
  dry_run: true  # Run in dry-run mode by default
  delete: true
  progress: true
  verbose: true
  compress: true
  chmod_files: "664"
  chmod_dirs: "775"
  excludes:
    - "wp-config.php"  # Files that should never be transferred or deleted
  cleanup_files:
    - ".DS_Store"  # Files to remove from destination before sync

domains:
  staging:
    http: http://staging.domain.com
    https: https://staging.domain.com
  live:
    http: http://www.domain.com
    https: https://www.domain.com

---

## 🧪 Usage

After installation, run the tool from your terminal using the wrapper script:

```bash
# Push local changes to live server
./wordpress-sync --direction push

# Pull live server changes to local
./wordpress-sync --direction pull

# Skip WordPress installation check (useful if wp core is-installed fails but WordPress is working)
./wordpress-sync --direction pull --skip-wp-check

# Skip validation checks after synchronization
./wordpress-sync --direction push --skip-validation

# Skip dry run and perform actual synchronization immediately
./wordpress-sync --direction push --no-dry-run

# Only output the commands that would be executed without performing any actions
./wordpress-sync --direction push --command-only

# Provide sudo password for remote server operations (when pushing to live)
./wordpress-sync --direction push --sudo-password "your-sudo-password"

# Skip backup of deleted/modified files to trash directory
./wordpress-sync --direction push --no-trash
```

### Command-Only Mode

The `--command-only` flag provides a way to see all the commands that would be executed during a synchronization without actually performing any actions. This is useful for:

- **Learning and understanding** the synchronization process in detail
- **Debugging** issues by examining the exact commands being used
- **Manual execution** of specific commands when needed
- **Documentation** of the synchronization process for your team
- **Scripting** custom synchronization workflows based on the generated commands
- **Auditing** the operations that would be performed on your systems

When you run with `--command-only`, the tool will:
1. Skip environment validation checks
2. Output all commands organized by synchronization stage
3. Show which environment (local or remote) each command would run in
4. Include detailed descriptions of what each command does
5. Format the output in a clear, readable way

This flag is compatible with all other flags, allowing you to see the commands for any synchronization scenario:
```bash
# See commands for a database-only pull operation
./wordpress-sync --direction pull --db-only --command-only

# See commands for a files-only push operation
./wordpress-sync --direction push --files-only --command-only
```

The script will:
1. Verify the direction of synchronization
2. Activate maintenance mode on both environments
3. Show a dry-run of file changes (default behavior)
4. Prompt for confirmation before proceeding
5. Execute the synchronization:
   - Transfer files via rsync
   - Handle database export/import
   - Update domain URLs
   - Fix permissions (for push operations)
   - Run validation checks
   - Flush caches
   - Disable maintenance mode
   - Clean up temporary files

---

## 🔍 Validation Checks

The tool uses WP-CLI to perform thorough validation after synchronization:

### Core Files Validation
- Uses `wp core verify-checksums` to verify WordPress core files
- Checks presence of critical files:
  - wp-config.php
  - wp-content/index.php
  - .htaccess
- Verifies file permissions

### Database Validation
- Verifies all WordPress core tables exist
- Checks custom tables (if specified)
- Confirms table accessibility

### Accessibility Checks
- Verifies the homepage is accessible
- Confirms wp-admin login page loads

If validation fails, the script will:
1. Display specific validation errors
2. Indicate which checks failed
3. Provide guidance for manual verification

---

## ⚠️ Error Handling

If the synchronization fails:

1. The script will:
   - Display detailed error information
   - Attempt to disable maintenance mode on both sites
   - Clean up any temporary files
   
2. Manual intervention may be required to:
   - Fix any partially transferred files
   - Restore database from backup if needed
   - Reset file permissions if necessary
   
3. Common error scenarios:
   - SSH connection failures
   - Insufficient disk space
   - Database connection issues
   - Permission problems
   
Always verify your site's functionality after addressing any errors.

---

## 📝 Notes
- The synchronization process always begins in dry-run mode, allowing you to review the changes before confirming the sync.
- wp-config.php is excluded during the sync process to avoid overwriting critical configuration.
- Ensure your SSH key is loaded in the SSH agent or explicitly provided in config.yaml if necessary.
- If your server uses a non-standard SSH port, set `ssh.port` in config.yaml.
- Always test your synchronization first with dry-run mode enabled before syncing to the live site.

### Understanding Excludes vs. Cleanup Files

The configuration has two different ways to handle files during sync:

1. **excludes**: Files that should be completely ignored during sync. These files:
   - Will not be transferred from source to destination
   - Will not be deleted from the destination if they exist there
   - Example: `wp-config.php` should never be transferred or deleted to preserve environment-specific settings

2. **cleanup_files**: Files that should be removed from the destination before sync. These files:
   - Will not be transferred from source to destination
   - Will be deleted from the destination before rsync runs
   - Help ensure directories can be properly deleted by rsync
   - Example: `.DS_Store` files (created by macOS) should be removed to allow proper directory cleanup

When to use cleanup_files:
- For hidden system files like `.DS_Store` that might prevent directory deletion
- For temporary files that should never be transferred but should be removed if present
- For any files that might interfere with rsync's ability to clean up empty directories

This approach solves the "cannot delete non-empty directory" error that can occur when excluded files prevent rsync from removing directories.

### Staging Environment Visual Indicator

The `staging_etc/mu-plugins/admin-bar-color-for-staging.php` file is a must-use plugin that helps identify staging environments. While not part of the core synchronization functionality, this optional plugin changes the WordPress admin bar color to orange (#e88a01) on any staging site (domains starting with 'staging.'). This provides a clear visual indicator that you're working in a staging environment, helping prevent accidental changes to the live site.

To use this plugin:
1. Copy the file from `staging_etc/mu-plugins/` to your staging site's `wp-content/mu-plugins/` directory
2. No activation is needed - mu-plugins are automatically loaded by WordPress

Note: This plugin is included in the default rsync excludes in the sample configuration file to prevent it from being transferred to the live site during push operations. You can see this in the `config.yaml.sample` file:
```yaml
rsync:
  excludes:
    - "admin-bar-color-for-staging.php"  # changes the admin color bar when installed on the staging site, but prevents this transfer to live
```

### Sudo Password Handling

When pushing to a live server, you may need sudo privileges to set file permissions and ownership. The tool provides four ways to handle sudo operations:

1. **Dedicated sudo user (most secure)**: Configure a separate sudo user in the config file:
   ```yaml
   ssh:
     user: username
     host: example.com
     key_path: ~/.ssh/id_rsa
     sudo:
       user: root  # User with sudo privileges
       key_path: ~/.ssh/root_id_rsa  # Optional: Different SSH key for sudo user
   ```
   - Commands requiring sudo privileges will be executed directly as the sudo user
   - No sudo password is required as the sudo user already has the necessary privileges
   - This is the most secure approach as it uses proper user separation

2. **NOPASSWD sudo configuration**: Configure your server to allow the SSH user to run sudo commands without a password prompt:
   - Connect to your server and edit the sudoers file: `sudo visudo`
   - Add this line (replace `username` with your SSH user): `username ALL=(ALL) NOPASSWD: ALL`
   - This approach is convenient but requires modifying the server's sudo configuration

3. **Sudo password via command line**: Provide the sudo password when running the tool:
   ```bash
   ./wordpress-sync --direction push --sudo-password "your-sudo-password"
   ```
   - The password is used to execute sudo commands on the remote server
   - This approach is convenient for automation but less secure as the password appears in command history

4. **Interactive password prompt**: If sudo requires a password and none is provided via command line:
   - The tool will securely prompt you to enter the password
   - Password is entered securely (not displayed on screen)
   - Password is cached for the duration of the session to avoid multiple prompts
   - This is the most user-friendly approach for manual operations

The tool automatically detects which method to use by checking for a dedicated sudo user first, then trying NOPASSWD sudo, and finally falling back to interactive prompting if needed.

### Backup and Trash Management

The tool includes a comprehensive backup system that preserves both files and databases during synchronization:

1. **File Backup**:
   - During rsync operations, the `--backup` flag is used to preserve files that would be overwritten or deleted
   - These files are moved to a trash directory (`.trash` by default) in the parent directory of the target site
   - Before synchronization, the tool checks if the trash directory already contains files
   - After synchronization and validation, the tool prompts you to review and optionally delete the backed-up files

2. **Database Backup**:
   - Before resetting a database during import, the tool offers to create a backup
   - Database backups are stored in a dedicated backup directory with timestamped filenames
   - This provides a safety net in case you need to restore the database to its previous state
   - Backups are preserved and not cleaned up automatically, allowing for point-in-time recovery

3. **Configuration options** in `config.yaml`:
   ```yaml
   backup:
     enabled: true  # Enable backup of deleted/modified files during rsync
     directory: "../wordpress-sync-trash"  # Path to backup directory (relative to local/live paths)
     archive_format: "wordpress-sync-trash_%Y-%m-%d_%H%M%S"  # Format for archive names
     cleanup_prompt: true  # Whether to prompt for cleanup after sync
     database:
       enabled: true  # Enable database backups before reset
       directory: "../wordpress-sync-db-backups"  # Path to store database backups
       filename_format: "db-backup_%Y-%m-%d_%H%M%S.sql"  # Format for backup filenames
   ```

4. **Command-line control**:
   - Use `--no-trash` to disable the file backup functionality
   - Database backups are controlled via the configuration file

5. **Workflow**:
   - **Before sync**: If the trash directory contains files from a previous sync:
     - The tool shows you the existing files
     - You can choose to keep them (they'll be archived with a timestamp) or delete them
   - **During database reset**: If database backups are enabled:
     - The tool prompts you to create a backup before resetting the database
     - If you choose yes, a timestamped backup is created in the configured backup directory
   - **After sync**: If files were backed up during the sync:
     - The tool shows you which files were backed up
     - You can choose to delete them or keep them for reference

This backup system provides a safety net when synchronizing WordPress sites, allowing you to:
- Recover accidentally deleted files
- Restore databases to their previous state if needed
- Review what changes were made during synchronization
- Keep a history of changes by archiving old trash directories and database backups
- Safely clean up backup files when they're no longer needed

---

## 📌 License

MIT License
