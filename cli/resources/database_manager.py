#!/usr/bin/env python3
"""
Database Manager for WordPress Sync.

This module handles database operations such as export, import, and reset using WP-CLI.
It manages the WordPress database operations during the synchronization process.
"""

import os
import subprocess
import sys
import shlex
import time
from pathlib import Path


class DatabaseManager:
    """Manages database operations for WordPress Sync."""

    def __init__(self, config):
        """
        Initialize the Database Manager.

        Args:
            config (dict): Configuration dictionary.
        """
        self.config = config
        self.local_path = config["paths"]["local"]
        self.live_path = config["paths"]["live"]
        # db_temp can be a string (old format) or dict with local/remote (new format)
        raw_db_temp = config["paths"]["db_temp"]
        if isinstance(raw_db_temp, dict):
            self.db_temp_local = raw_db_temp.get("local", "/tmp")
            self.db_temp_remote = raw_db_temp.get("remote", "/tmp")
        else:
            self.db_temp_local = raw_db_temp
            self.db_temp_remote = raw_db_temp
        # Keep legacy attribute for any code that reads self.db_temp directly
        self.db_temp = self.db_temp_local
        self.db_filename = config["paths"].get("db_filename", "wordpress-sync-database.sql")
        
        # Get the correct local temp directory path
        local_db_temp = self._get_local_db_temp_path()
        
        # Ensure temp directory exists
        os.makedirs(local_db_temp, exist_ok=True)

    def check_wp_cli(self):
        """
        Check if WordPress CLI is installed.

        Returns:
            bool: True if WP-CLI is installed, False otherwise.
        """
        try:
            result = subprocess.run(
                ["wp", "--info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            return result.returncode == 0
            
        except FileNotFoundError:
            print("WordPress CLI (wp) not found. Please install it and make sure it's in your PATH.")
            return False
        except Exception as e:
            print(f"Error checking WordPress CLI: {e}")
            return False

    def check_wordpress_installed(self, direction):
        """
        Check if WordPress is installed in both environments.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').

        Returns:
            bool: True if WordPress is installed in both environments, False otherwise.
        """
        # Skip WordPress installation check if environment variable is set
        if os.environ.get('WORDPRESS_SYNC_SKIP_WP_CHECK', '').lower() in ('true', '1', 'yes'):
            print(f"Skipping WordPress installation check (WORDPRESS_SYNC_SKIP_WP_CHECK=true)")
            return True
            
        print("Checking WordPress installations...")
        
        # Check local WordPress installation
        local_installed = self._check_wp_installed(self.local_path, is_remote=False)
        if not local_installed:
            return False
            
        # Check remote WordPress installation
        remote_installed = self._check_wp_installed(self.live_path, is_remote=True)
        if not remote_installed:
            return False
            
        print("WordPress is properly installed in both environments.")
        return True

    def _check_wp_installed(self, path, is_remote=False):
        """
        Check if WordPress is installed at the specified path.

        Args:
            path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if WordPress is installed, False otherwise.
        """
        # Add an environment variable option to skip the check
        if os.environ.get('WORDPRESS_SYNC_SKIP_WP_CHECK', '').lower() in ('true', '1', 'yes'):
            print(f"Skipping WordPress installation check (WORDPRESS_SYNC_SKIP_WP_CHECK=true)")
            return True
            
        print(f"Checking WordPress installation at: {path}")
        
        # First check if the directory exists
        if not is_remote and not os.path.isdir(path):
            print(f"Error: Directory does not exist: {path}")
            return False
            
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            # Check if directory exists on remote server
            dir_check_cmd = f"[ -d \"{path}\" ] && echo 'exists' || echo 'not found'"
            success, output = ssh_manager.execute_remote_command(dir_check_cmd)
            if not success or 'not found' in output:
                print(f"Error: Remote directory does not exist: {path}")
                return False
                
            # Check if wp-config.php exists (basic check for WordPress installation)
            config_check_cmd = f"[ -f \"{path}/wp-config.php\" ] && echo 'exists' || echo 'not found'"
            success, output = ssh_manager.execute_remote_command(config_check_cmd)
            if not success or 'not found' in output:
                print(f"Error: wp-config.php not found in remote directory: {path}")
                return False
                
            # Try the WP-CLI command
            print(f"Running 'wp core is-installed' on remote server...")
            cmd = f'wp --path="{path}" core is-installed'
            success, output = ssh_manager.execute_remote_command(cmd)
            
            # If it fails, try with --allow-root
            if not success:
                print(f"Trying with --allow-root flag...")
                cmd = f'wp --path="{path}" core is-installed --allow-root'
                success, output = ssh_manager.execute_remote_command(cmd)
                
            if success:
                print(f"WordPress is installed at remote path: {path}")
            else:
                print(f"WordPress is not installed at remote path: {path}")
                if output:
                    print(f"Error output: {output}")
                    
            return success
        else:
            try:
                # Check if wp-config.php exists (basic check for WordPress installation)
                if not os.path.isfile(os.path.join(path, 'wp-config.php')):
                    print(f"Error: wp-config.php not found in directory: {path}")
                    return False
                    
                # Try without --allow-root flag first
                print(f"Running 'wp core is-installed'...")
                # Use a single string command with shell=True to ensure proper path handling
                cmd = f'wp --path="{path}" core is-installed'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                # If it fails, try with --allow-root flag
                if result.returncode != 0:
                    print(f"Trying with --allow-root flag...")
                    cmd = f'wp --path="{path}" core is-installed --allow-root'
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                        shell=True
                    )
                
                is_installed = result.returncode == 0
                
                if is_installed:
                    print(f"WordPress is installed at local path: {path}")
                else:
                    print(f"WordPress is not installed at local path: {path}")
                    if result.stderr:
                        print(f"Error output: {result.stderr}")
                        
                return is_installed
                
            except Exception as e:
                print(f"Error checking WordPress installation: {e}")
                return False

    def _get_local_db_temp_path(self):
        """
        Get the correct path for the local temporary database directory.
        
        Returns:
            str: Path to the local temporary database directory.
        """
        db_temp = self.db_temp_local
        
        # If db_temp is an absolute path, use it directly
        if os.path.isabs(db_temp):
            return db_temp
            
        # For relative paths that start with ../
        if db_temp.startswith('../'):
            # Get the parent directory of the WordPress directory
            parent_dir = os.path.dirname(self.local_path.rstrip('/'))
            # Remove the ../ prefix from db_temp
            relative_path = db_temp[3:]
            # Join the parent directory with the remaining path
            return os.path.join(parent_dir, relative_path)
        
        # For other relative paths, join with local_path
        return os.path.join(self.local_path, db_temp)
            
    def _get_remote_db_temp_path(self):
        """
        Get the correct path for the remote temporary database directory.
        
        Returns:
            str: Path to the remote temporary database directory.
        """
        db_temp = self.db_temp_remote
        
        # If db_temp is an absolute path, use it directly
        if os.path.isabs(db_temp):
            return db_temp
            
        # For relative paths that start with ../
        if db_temp.startswith('../'):
            # Get the parent directory of the WordPress directory
            parent_dir = os.path.dirname(self.live_path.rstrip('/'))
            # Remove the ../ prefix from db_temp
            relative_path = db_temp[3:]
            # Join the parent directory with the remaining path
            return os.path.join(parent_dir, relative_path)
        
        # For other relative paths, join with live_path
        return os.path.join(self.live_path, db_temp)
        
    def _get_db_backup_path(self, is_remote=False):
        """
        Get the path for database backups.
        
        Supports both new format (unified backup.directory dict → <root>/db/)
        and old format (separate backup.database.directory string).
        
        Args:
            is_remote (bool): Whether the path is for the remote server.
            
        Returns:
            tuple: (backup_dir, backup_filename) - Paths for the backup directory and filename.
        """
        # Get filename format (same in both old and new formats)
        filename_format = "db-backup_%Y-%m-%d_%H%M%S.sql"
        if "backup" in self.config and "database" in self.config["backup"]:
            filename_format = self.config["backup"]["database"].get("filename_format", filename_format)
        
        # Generate timestamp for unique backup filename
        timestamp = time.strftime(filename_format.replace(".sql", ""))
        backup_filename = f"{timestamp}.sql"
        
        # Determine base path based on whether it's remote or local
        base_path = self.live_path if is_remote else self.local_path
        
        # Check if using new unified backup directory format
        raw_dir = self.config.get("backup", {}).get("directory")
        if isinstance(raw_dir, dict):
            # New format: DB backups go in <backup_root>/db/
            dir_key = "remote" if is_remote else "local"
            root_dir = raw_dir.get(dir_key, "../wordpress-sync-backups")
            
            # Resolve relative path
            if os.path.isabs(root_dir):
                full_backup_dir = os.path.join(root_dir, "db")
            elif root_dir.startswith('../'):
                parent_dir = os.path.dirname(base_path.rstrip('/'))
                full_backup_dir = os.path.join(parent_dir, root_dir[3:], "db")
            else:
                full_backup_dir = os.path.join(base_path.rstrip('/'), root_dir, "db")
        else:
            # Old format: use separate backup.database.directory
            if "backup" not in self.config or "database" not in self.config["backup"]:
                backup_dir = "../wordpress-sync-db-backups"
            else:
                backup_dir = self.config["backup"]["database"].get("directory", "../wordpress-sync-db-backups")
            
            # Resolve the full backup directory path
            if os.path.isabs(backup_dir):
                full_backup_dir = backup_dir
            elif backup_dir.startswith('../'):
                parent_dir = os.path.dirname(base_path.rstrip('/'))
                relative_path = backup_dir[3:]
                full_backup_dir = os.path.join(parent_dir, relative_path)
            else:
                full_backup_dir = os.path.join(base_path, backup_dir)
            
        return full_backup_dir, backup_filename
        
    def backup_database(self, direction, dry_run=False):
        """
        Create a backup of the destination database before reset.
        
        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.
            
        Returns:
            str: Path to the backup file, or None if backup failed.
        """
        # For push: backup remote db (live site)
        # For pull: backup local db (local site)
        if direction == "push":
            target_path = self.live_path
            is_remote = True
        else:  # pull
            target_path = self.local_path
            is_remote = False
            
        # Get backup paths
        backup_dir, backup_filename = self._get_db_backup_path(is_remote)
        backup_file = os.path.join(backup_dir, backup_filename)
        
        if dry_run:
            print(f"[DRY RUN] Would backup database at {target_path} to {backup_file}")
            return backup_file
            
        # Ensure backup directory exists
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            mkdir_cmd = f"mkdir -p {backup_dir}"
            success, _ = ssh_manager.execute_remote_command(mkdir_cmd)
            if not success:
                print(f"Failed to create backup directory on remote server: {backup_dir}")
                return None
                
            # Export database to backup file
            export_cmd = f'wp --path="{target_path}" db export {backup_file} --allow-root'
            success, output = ssh_manager.execute_remote_command(export_cmd)
            
            if not success:
                print(f"Failed to backup remote database: {output}")
                return None
                
            print(f"Database backed up to {backup_file} on remote server")
        else:
            # Ensure local backup directory exists
            os.makedirs(backup_dir, exist_ok=True)
            
            try:
                # Export database to backup file
                cmd = f'wp --path="{target_path}" db export {backup_file} --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to backup local database: {result.stderr}")
                    return None
                    
                print(f"Database backed up to {backup_file}")
                
            except Exception as e:
                print(f"Error backing up database: {e}")
                return None
                
        return backup_file

    def export_database(self, direction, dry_run=False):
        """
        Export the database from the source environment.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            str: Path to the exported database file, or None if export failed.
        """
        if direction == "push":
            # Export from local
            source_path = self.local_path
            # Get the correct local temp directory path
            local_db_temp = self._get_local_db_temp_path()
            db_file = os.path.join(local_db_temp, self.db_filename)
            is_remote = False
        else:  # pull
            # Export from remote
            source_path = self.live_path
            # Get the correct remote temp directory path
            remote_db_temp = self._get_remote_db_temp_path()
            db_file = os.path.join(remote_db_temp, self.db_filename)
            is_remote = True
            
            # Ensure remote db_temp directory exists
            if not dry_run:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                mkdir_cmd = f"mkdir -p {remote_db_temp}"
                ssh_manager.execute_remote_command(mkdir_cmd)

        if dry_run:
            print(f"[DRY RUN] Would export database from {source_path} to {db_file}")
            return db_file

        # Export database
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            export_cmd = f'wp --path="{source_path}" db export {db_file} --allow-root'
            success, output = ssh_manager.execute_remote_command(export_cmd)
            
            if not success:
                print(f"Failed to export remote database: {output}")
                return None
                
            print(f"Database exported to {db_file} on remote server")
        else:
            try:
                cmd = f'wp --path="{source_path}" db export {db_file} --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to export local database: {result.stderr}")
                    return None
                    
                print(f"Database exported to {db_file}")
                
            except Exception as e:
                print(f"Error exporting database: {e}")
                return None

        # If pulling, transfer the database file from remote to local
        if direction == "pull" and not dry_run:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            # Get the correct local temp directory path
            local_db_temp = self._get_local_db_temp_path()
            local_db_file = os.path.join(local_db_temp, self.db_filename)
            success = ssh_manager.transfer_file(db_file, local_db_file, "pull")
            
            if not success:
                print("Failed to transfer database file from remote server")
                return None
                
            db_file = local_db_file

        return db_file

    def import_database(self, direction, db_file, dry_run=False):
        """
        Import the database to the target environment.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            db_file (str): Path to the database file to import.
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if import is successful, False otherwise.
        """
        if direction == "push":
            # Import to remote
            target_path = self.live_path
            # Get the correct remote temp directory path
            remote_db_temp = self._get_remote_db_temp_path()
            remote_db_file = os.path.join(remote_db_temp, self.db_filename)
            is_remote = True
            
            # Transfer database file to remote server
            if not dry_run:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                # Ensure remote db_temp directory exists
                mkdir_cmd = f"mkdir -p {remote_db_temp}"
                ssh_manager.execute_remote_command(mkdir_cmd)
                
                # Transfer file
                success = ssh_manager.transfer_file(db_file, remote_db_file, "push")
                if not success:
                    print("Failed to transfer database file to remote server")
                    return False
                    
                db_file = remote_db_file
        else:  # pull
            # Import to local
            target_path = self.local_path
            is_remote = False

        if dry_run:
            print(f"[DRY RUN] Would import database to {target_path} from {db_file}")
            return True

        # Reset database before import (optional)
        reset_success = self.reset_database(direction, dry_run)
        if not reset_success:
            print("Warning: Database reset failed, proceeding with import anyway")

        # Import database
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            import_cmd = f'wp --path="{target_path}" db import {db_file} --allow-root'
            success, output = ssh_manager.execute_remote_command(import_cmd)
            
            if not success:
                print(f"Failed to import database to remote server: {output}")
                return False
                
            print("Database imported to remote server")
        else:
            try:
                cmd = f'wp --path="{target_path}" db import {db_file} --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to import local database: {result.stderr}")
                    return False
                    
                print("Database imported to local server")
                
            except Exception as e:
                print(f"Error importing database: {e}")
                return False

        return True

    def reset_database(self, direction, dry_run=False):
        """
        Reset the database in the target environment.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if reset is successful, False otherwise.
        """
        if direction == "push":
            # Reset remote database
            target_path = self.live_path
            is_remote = True
        else:  # pull
            # Reset local database
            target_path = self.local_path
            is_remote = False

        if dry_run:
            print(f"[DRY RUN] Would reset database at {target_path}")
            return True
            
        # Check if database backups are enabled
        backup_enabled = False
        if "backup" in self.config and "database" in self.config["backup"]:
            backup_enabled = self.config["backup"]["database"].get("enabled", False)
            
        # Offer to backup the database before reset
        if backup_enabled:
            non_interactive = self.config.get("_non_interactive", False)
            if non_interactive:
                print("\nNon-interactive mode: automatically backing up database before reset.")
                response = "yes"
            else:
                response = input("\nWould you like to backup the destination database before reset? (yes/no): ").lower()
            if response in ["yes", "y"]:
                backup_file = self.backup_database(direction, dry_run=False)
                if backup_file:
                    print(f"Database backed up successfully to: {backup_file}")
                else:
                    print("Warning: Database backup failed, proceeding with reset anyway")
                    
        # Reset database
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            reset_cmd = f'wp --path="{target_path}" db reset --yes --allow-root'
            success, output = ssh_manager.execute_remote_command(reset_cmd)
            
            if not success:
                print(f"Failed to reset remote database: {output}")
                return False
                
            print("Remote database reset")
        else:
            try:
                cmd = f'wp --path="{target_path}" db reset --yes --allow-root'
                result = subprocess.run(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to reset local database: {result.stderr}")
                    return False
                    
                print("Local database reset")
                
            except Exception as e:
                print(f"Error resetting database: {e}")
                return False

        return True

    def clear_cache(self, direction, dry_run=False):
        """
        Clear the cache in the target environment.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if cache clearing is successful, False otherwise.
        """
        if direction == "push":
            # Clear remote cache
            target_path = self.live_path
            is_remote = True
        else:  # pull
            # Clear local cache
            target_path = self.local_path
            is_remote = False

        if dry_run:
            print(f"[DRY RUN] Would clear cache at {target_path}")
            return True

        # Clear cache
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            cache_cmd = f'wp --path="{target_path}" cache flush --allow-root'
            success, output = ssh_manager.execute_remote_command(cache_cmd)
            
            if not success:
                print(f"Failed to clear remote cache: {output}")
                return False
                
            print("Remote cache cleared")
        else:
            try:
                cmd = f'wp --path="{target_path}" cache flush --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to clear local cache: {result.stderr}")
                    return False
                    
                print("Local cache cleared")
                
            except Exception as e:
                print(f"Error clearing cache: {e}")
                return False

        return True

    def cleanup(self, direction, db_file, dry_run=False):
        """
        Clean up temporary files after synchronization.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            db_file (str): Path to the database file to clean up.
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if cleanup is successful, False otherwise.
        """
        if dry_run:
            print(f"[DRY RUN] Would clean up temporary files")
            return True

        try:
            # Get the correct local and remote temp directory paths
            local_db_temp = self._get_local_db_temp_path()
            remote_db_temp = self._get_remote_db_temp_path()
            remote_db_file = os.path.join(remote_db_temp, self.db_filename)
            
            # Clean up local database file and directory
            if os.path.exists(db_file):
                os.remove(db_file)
                print(f"Removed local database file: {db_file}")
            
            # Remove the local temp directory if it exists and is empty
            if os.path.exists(local_db_temp):
                # Check if directory is empty
                if not os.listdir(local_db_temp):
                    os.rmdir(local_db_temp)
                    print(f"Removed local temp directory: {local_db_temp}")
                else:
                    print(f"Local temp directory not empty, skipping removal: {local_db_temp}")

            # Clean up remote database file and directory
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            if direction == "push":
                # Clean up the file we pushed to the remote server
                cleanup_cmd = f'rm -f "{remote_db_file}"'
                success, _ = ssh_manager.execute_remote_command(cleanup_cmd)
                
                if success:
                    print(f"Removed remote database file: {remote_db_file}")
                else:
                    print(f"Warning: Failed to remove remote database file: {remote_db_file}")
                
                # Force remove the remote temp directory
                rmdir_cmd = f'rm -rf "{remote_db_temp}"'
                success, _ = ssh_manager.execute_remote_command(rmdir_cmd)
                if success:
                    print(f"Removed remote temp directory: {remote_db_temp}")
                else:
                    print(f"Warning: Failed to remove remote temp directory: {remote_db_temp}")
            else:  # pull
                # Clean up the file we exported on the remote server
                cleanup_cmd = f'rm -f "{remote_db_file}"'
                success, _ = ssh_manager.execute_remote_command(cleanup_cmd)
                
                if success:
                    print(f"Removed remote database file: {remote_db_file}")
                else:
                    print(f"Warning: Failed to remove remote database file: {remote_db_file}")
                
                # Force remove the remote temp directory
                rmdir_cmd = f'rm -rf "{remote_db_temp}"'
                success, _ = ssh_manager.execute_remote_command(rmdir_cmd)
                if success:
                    print(f"Removed remote temp directory: {remote_db_temp}")
                else:
                    print(f"Warning: Failed to remove remote temp directory: {remote_db_temp}")

            return True
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return False
