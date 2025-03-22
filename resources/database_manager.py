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
        self.db_temp = config["paths"]["db_temp"]
        self.db_filename = config["paths"].get("db_filename", "wordpress-sync-database.sql")
        
        # Ensure temp directory exists
        os.makedirs(self.db_temp, exist_ok=True)

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
            db_file = os.path.join(self.db_temp, self.db_filename)
            is_remote = False
        else:  # pull
            # Export from remote
            source_path = self.live_path
            db_file = os.path.join(self.live_path, "tmp", self.db_filename)
            is_remote = True
            
            # Ensure remote tmp directory exists
            if not dry_run:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                mkdir_cmd = f"mkdir -p {os.path.dirname(db_file)}"
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
            
            local_db_file = os.path.join(self.db_temp, self.db_filename)
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
            remote_db_file = os.path.join(self.live_path, "tmp", self.db_filename)
            is_remote = True
            
            # Transfer database file to remote server
            if not dry_run:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                # Ensure remote tmp directory exists
                mkdir_cmd = f"mkdir -p {os.path.dirname(remote_db_file)}"
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
            # Clean up local database file
            if os.path.exists(db_file):
                os.remove(db_file)
                print(f"Removed local database file: {db_file}")

            # Clean up remote database file if pushing
            if direction == "push":
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                remote_db_file = os.path.join(self.live_path, "tmp", self.db_filename)
                cleanup_cmd = f'rm -f "{remote_db_file}"'
                success, _ = ssh_manager.execute_remote_command(cleanup_cmd)
                
                if success:
                    print(f"Removed remote database file: {remote_db_file}")
                else:
                    print(f"Warning: Failed to remove remote database file: {remote_db_file}")

            return True
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return False
