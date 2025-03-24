#!/usr/bin/env python3
"""
WordPress Sync: A command-line tool to automate WordPress synchronization between local and live environments.

This script orchestrates the entire synchronization process by coordinating various resource managers
to handle configuration, SSH connections, database operations, URL replacements,
maintenance mode, and validation checks.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import resource managers
try:
    from resources.config_manager import ConfigManager
    from resources.ssh_manager import SSHManager
    from resources.database_manager import DatabaseManager
    from resources.url_manager import URLManager
    from resources.maintenance_manager import MaintenanceManager
    from resources.validation_manager import ValidationManager
    from resources.plugin_manager import PluginManager
    from resources.command_collector import CommandCollector
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please ensure all required modules are installed.")
    sys.exit(1)


class WordPressSync:
    """Main class for WordPress synchronization tool."""

    def __init__(self):
        """Initialize the WordPress Sync tool."""
        self.args = None
        self.config = None
        self.config_manager = None
        self.ssh_manager = None
        self.database_manager = None
        self.url_manager = None
        self.maintenance_manager = None
        self.validation_manager = None
        self.plugin_manager = None
        self.command_collector = None
        self.direction = None
        self.dry_run = None
        
    def _get_trash_path(self):
        """
        Get the path to the trash directory.
        
        Returns:
            str: Path to the trash directory.
        """
        # Get the backup directory from config or use default
        if "backup" not in self.config:
            self.config["backup"] = {}
            
        backup_dir = self.config["backup"].get("directory", "../.trash")
        
        # Determine the base path based on direction
        base_path = self.config["paths"]["live"] if self.direction == "push" else self.config["paths"]["local"]
        
        # If backup_dir is relative, make it relative to the base path
        if not os.path.isabs(backup_dir):
            # For relative paths that start with ../
            if backup_dir.startswith('../'):
                # Get the parent directory of the WordPress directory
                parent_dir = os.path.dirname(base_path.rstrip('/'))
                # Remove the ../ prefix from backup_dir
                relative_path = backup_dir[3:]
                # Join the parent directory with the remaining path
                backup_dir = os.path.join(parent_dir, relative_path)
                
                # For push operations, ensure the path is properly formatted for remote server
                if self.direction == "push" and not self.dry_run:
                    # Log the resolved path for debugging
                    print(f"Resolved trash directory path: {backup_dir}")
            else:
                # For other relative paths, join with base_path
                backup_dir = os.path.join(base_path, backup_dir)
            
        return backup_dir
        
    def _list_trash_contents(self):
        """
        List the contents of the trash directory.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        trash_dir = self._get_trash_path()
        
        try:
            # Check if the trash directory is on the remote server
            if self.direction == "push" and not self.dry_run:
                # Check if directory exists on remote server
                check_dir_cmd = f"test -d {trash_dir} && echo 'exists' || echo 'not exists'"
                success, dir_output = self.ssh_manager.execute_remote_command(check_dir_cmd)
                
                if not success:
                    print(f"Failed to check trash directory: {dir_output}")
                    return False
                
                if dir_output.strip() != "exists":
                    print("Trash directory does not exist on remote server.")
                    return False
                
                # List files on remote server
                cmd = f"find {trash_dir} -type f | sort"
                success, output = self.ssh_manager.execute_remote_command(cmd)
                
                if not success:
                    print(f"Failed to list trash contents: {output}")
                    return False
                    
                if not output.strip():
                    print("No files found in trash directory.")
                    return True
                    
                print("Files in trash directory:")
                for line in output.strip().split('\n'):
                    print(f"  {line}")
            else:
                # List files on local system
                if not os.path.exists(trash_dir):
                    print("Trash directory does not exist.")
                    return False
                    
                files = []
                for root, _, filenames in os.walk(trash_dir):
                    for filename in filenames:
                        files.append(os.path.join(root, filename))
                        
                if not files:
                    print("No files found in trash directory.")
                    return True
                    
                print("Files in trash directory:")
                for file in sorted(files):
                    print(f"  {file}")
                    
            return True
            
        except Exception as e:
            print(f"Error listing trash contents: {e}")
            return False
            
    def handle_existing_trash(self):
        """
        Handle existing trash directory contents before sync.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        if self.args.no_trash:
            return True  # Skip trash handling if --no-trash flag is used
            
        trash_dir = self._get_trash_path()
        
        try:
            # Check if the trash directory exists and has contents
            if self.direction == "push" and not self.dry_run:
                # Check on remote server
                # First ensure the directory exists
                mkdir_cmd = f"mkdir -p {trash_dir}"
                self.ssh_manager.execute_remote_command(mkdir_cmd)
                
                # Then check if it has any files
                check_cmd = f"find {trash_dir} -type f | wc -l || echo 0"
                success, output = self.ssh_manager.execute_remote_command(check_cmd)
                
                if not success:
                    print(f"Failed to check trash directory: {output}")
                    return False
                    
                file_count = int(output.strip())
                if file_count == 0:
                    return True
            else:
                # Check on local system
                if not os.path.exists(trash_dir):
                    os.makedirs(trash_dir, exist_ok=True)
                    return True
                    
                # Count files in trash directory
                file_count = 0
                for root, _, filenames in os.walk(trash_dir):
                    file_count += len(filenames)
                    
                if file_count == 0:
                    return True
                    
            # If we get here, the trash directory exists and has files
            print("\nExisting files found in trash directory:")
            self._list_trash_contents()
            
            while True:
                response = input("\nWould you like to keep these files? (yes/no): ").lower()
                if response in ["yes", "y"]:
                    # Archive existing trash with timestamp
                    timestamp = time.strftime(self.config["backup"].get("archive_format", "wordpress-sync-trash_%Y-%m-%d_%H%M%S"))
                    archive_path = os.path.join(os.path.dirname(trash_dir), timestamp)
                    
                    if self.direction == "push" and not self.dry_run:
                        # Archive on remote server - don't recreate trash directory
                        mv_cmd = f"mv {trash_dir} {archive_path}"
                        success, output = self.ssh_manager.execute_remote_command(mv_cmd)
                        
                        if not success:
                            print(f"Failed to archive trash directory: {output}")
                            return False
                    else:
                        # Archive on local system - don't recreate trash directory
                        import shutil
                        shutil.move(trash_dir, archive_path)
                        
                    print(f"Archived existing trash to: {archive_path}")
                    return True
                elif response in ["no", "n"]:
                    # Remove existing trash
                    if self.direction == "push" and not self.dry_run:
                        # Remove entire trash directory on remote server
                        rm_cmd = f"rm -rf {trash_dir} || true"
                        success, output = self.ssh_manager.execute_remote_command(rm_cmd)
                        
                        if not success:
                            print(f"Failed to remove trash directory: {output}")
                            return False
                            
                        # Recreate the empty directory
                        mkdir_cmd = f"mkdir -p {trash_dir}"
                        self.ssh_manager.execute_remote_command(mkdir_cmd)
                    else:
                        # Remove entire trash directory on local system
                        import shutil
                        shutil.rmtree(trash_dir, ignore_errors=True)
                        os.makedirs(trash_dir, exist_ok=True)
                                
                    print("Removed existing trash directory")
                    return True
                else:
                    print("Please answer 'yes' or 'no'")
                    
        except Exception as e:
            print(f"Error handling existing trash: {e}")
            return False
            
    def handle_final_trash_cleanup(self):
        """
        Handle final trash cleanup after sync and verification.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        if self.args.no_trash:
            return True  # Skip trash handling if --no-trash flag is used
            
        trash_dir = self._get_trash_path()
        
        try:
            # Check if the trash directory exists and has contents
            if self.direction == "push" and not self.dry_run:
                # First ensure the directory exists
                mkdir_cmd = f"mkdir -p {trash_dir}"
                self.ssh_manager.execute_remote_command(mkdir_cmd)
                
                # Then check if it has any files
                check_cmd = f"find {trash_dir} -type f | wc -l || echo 0"
                success, output = self.ssh_manager.execute_remote_command(check_cmd)
                
                if not success:
                    print(f"Failed to check trash directory: {output}")
                    return False
                    
                file_count = int(output.strip())
                if file_count == 0:
                    print("No files were backed up during sync.")
                    return True
            else:
                # Check on local system
                if not os.path.exists(trash_dir):
                    print("No files were backed up during sync.")
                    return True
                    
                # Count files in trash directory
                file_count = 0
                for root, _, filenames in os.walk(trash_dir):
                    file_count += len(filenames)
                    
                if file_count == 0:
                    print("No files were backed up during sync.")
                    return True
                    
            # If we get here, the trash directory exists and has files
            print("\nThe following files were backed up during sync:")
            self._list_trash_contents()
            
            while True:
                response = input("\nWould you like to delete these backed up files? (yes/no): ").lower()
                if response in ["yes", "y"]:
                    if self.direction == "push" and not self.dry_run:
                        # Remove on remote server - remove entire trash directory
                        rm_cmd = f"rm -rf {trash_dir} || true"
                        success, output = self.ssh_manager.execute_remote_command(rm_cmd)
                        
                        if not success:
                            print(f"Failed to remove trash directory: {output}")
                            return False
                    else:
                        # Remove on local system - remove entire trash directory
                        import shutil
                        shutil.rmtree(trash_dir, ignore_errors=True)
                                
                    print("Backed up files have been deleted")
                    return True
                elif response in ["no", "n"]:
                    # Archive the trash directory with timestamp
                    timestamp = time.strftime(self.config["backup"].get("archive_format", "wordpress-sync-trash_%Y-%m-%d_%H%M%S"))
                    archive_path = os.path.join(os.path.dirname(trash_dir), timestamp)
                    
                    if self.direction == "push" and not self.dry_run:
                        # Archive on remote server - don't recreate trash directory
                        mv_cmd = f"mv {trash_dir} {archive_path}"
                        success, output = self.ssh_manager.execute_remote_command(mv_cmd)
                        
                        if not success:
                            print(f"Failed to archive trash directory: {output}")
                            return False
                    else:
                        # Archive on local system - don't recreate trash directory
                        import shutil
                        shutil.move(trash_dir, archive_path)
                        
                    print(f"Backed up files have been archived to: {archive_path}")
                    return True
                else:
                    print("Please answer 'yes' or 'no'")
                    
        except Exception as e:
            print(f"Error handling final trash cleanup: {e}")
            return False

    def parse_arguments(self):
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(
            description="WordPress Synchronization Tool",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        parser.add_argument(
            "--direction",
            choices=["push", "pull"],
            help="Direction of synchronization: 'push' (local to live) or 'pull' (live to local)"
        )
        
        parser.add_argument(
            "--config",
            default=os.path.join(SCRIPT_DIR, "config/config.yaml"),
            help="Path to configuration file"
        )
        
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            help="Skip dry run and perform actual synchronization"
        )
        
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Skip validation checks after synchronization"
        )
        
        parser.add_argument(
            "--skip-wp-check",
            action="store_true",
            help="Skip WordPress installation check"
        )
        
        parser.add_argument(
            "--command-only",
            action="store_true",
            help="Only output the commands that would be executed without performing any actions"
        )
        
        parser.add_argument(
            "--sudo-password",
            help="Password for sudo commands on the remote server (if required)"
        )
        
        parser.add_argument(
            "--no-trash",
            action="store_true",
            help="Skip backup of deleted/modified files to trash directory"
        )
        
        # Add mutually exclusive group for synchronization type
        synchronization_type_group = parser.add_mutually_exclusive_group()
        synchronization_type_group.add_argument(
            "--db-only",
            action="store_true",
            help="Only synchronize the database, skip file transfer"
        )
        synchronization_type_group.add_argument(
            "--files-only",
            action="store_true",
            help="Only synchronize files, skip database operations"
        )
        
        self.args = parser.parse_args()
        
        # Set dry run flag (default is True, --no-dry-run makes it False)
        self.dry_run = not self.args.no_dry_run
        
        return self.args

    def initialize_managers(self):
        """Initialize all resource managers."""
        try:
            # Initialize config manager and load configuration
            self.config_manager = ConfigManager(self.args.config)
            self.config = self.config_manager.load_config()
            
            # Set direction from args or config
            if self.args.direction:
                self.direction = self.args.direction
            else:
                self.direction = self.config["operation"]["direction"]
                
            # Command line argument (--no-dry-run) always takes precedence over config
            # If --no-dry-run was NOT provided (self.dry_run is True), then check config
            if self.dry_run and "rsync" in self.config and "dry_run" in self.config["rsync"]:
                # Only use config value if it's explicitly set to False (to skip dry run)
                if self.config["rsync"]["dry_run"] is False:
                    self.dry_run = False
                    
            # Command line argument (--no-trash) takes precedence over config
            if self.args.no_trash:
                self.config["no_trash"] = True
            
            # Initialize command collector if --command-only flag is used
            if self.args.command_only:
                self.command_collector = CommandCollector()
            
            # Initialize other managers
            self.ssh_manager = SSHManager(self.config)
            self.database_manager = DatabaseManager(self.config)
            self.url_manager = URLManager(self.config)
            self.maintenance_manager = MaintenanceManager(self.config)
            self.plugin_manager = PluginManager(self.config)
            
            # Initialize validation manager if validation is enabled
            if not self.args.skip_validation and self.config.get("validation", {}).get("enabled", True):
                self.validation_manager = ValidationManager(self.config)
                
            return True
            
        except Exception as e:
            print(f"Error initializing managers: {e}")
            return False

    def validate_environment(self):
        """Validate the environment before synchronization."""
        print("Validating environment...")
        
        # Check if WordPress CLI is installed
        if not self.database_manager.check_wp_cli():
            print("Error: WordPress CLI (wp) is not installed or not in PATH.")
            return False
            
        # Check SSH connection
        if not self.ssh_manager.test_connection():
            print("Error: Cannot establish SSH connection to the server.")
            return False
            
        # Check if WordPress is installed in both environments
        if not self.database_manager.check_wordpress_installed(self.direction):
            print("Error: WordPress is not properly installed in one or both environments.")
            return False
            
        print("Environment validation successful.")
        return True

    def confirm_synchronization(self):
        """Confirm with the user before proceeding with the actual synchronization."""
        if self.dry_run:
            print("\n" + "="*80)
            print("DRY RUN COMPLETED")
            print("="*80)
            print("\nThis was a dry run. No actual changes were made.")
            
            while True:
                response = input("\nDo you want to proceed with the actual synchronization? (yes/no): ").lower()
                if response in ["yes", "y"]:
                    self.dry_run = False
                    return True
                elif response in ["no", "n"]:
                    print("Synchronization cancelled by user.")
                    return False
                else:
                    print("Please answer 'yes' or 'no'.")
        else:
            return True

    def run_synchronization(self):
        """Run the synchronization process."""
        try:
            source_env = "local" if self.direction == "push" else "live"
            target_env = "live" if self.direction == "push" else "local"
            
            # Determine synchronization type
            db_only = self.args.db_only
            files_only = self.args.files_only
            full_sync = not db_only and not files_only
            
            sync_type = "database-only" if db_only else "files-only" if files_only else "full"
            
            # If --command-only flag is used, collect and display commands without executing
            if self.args.command_only:
                print(f"\nCollecting commands for {sync_type} WordPress synchronization: {source_env} → {target_env}")
                
                # Set up command sections
                self.command_collector.set_section("Environment Validation")
                
                # SSH connection test
                ssh_test_cmd = f'ssh -i {self.config["ssh"]["key_path"]} -o BatchMode=yes -o ConnectTimeout=5 {self.config["ssh"]["user"]}@{self.config["ssh"]["host"]} "echo \'Connection successful\'"'
                self.command_collector.add_command(
                    ssh_test_cmd,
                    "Test SSH connection to remote server",
                    "local",
                    "Local User"
                )
                
                if not self.args.skip_wp_check:
                    self.command_collector.add_command(
                        "wp --info",
                        "Check WordPress CLI installation",
                        "local",
                        "Local User"
                    )
                    
                    local_wp_check = f'wp --path="{self.config["paths"]["local"]}" core is-installed --allow-root'
                    self.command_collector.add_command(
                        local_wp_check,
                        "Check if WordPress is installed in local environment",
                        "local",
                        "Local User (root)"
                    )
                    
                    remote_wp_check = f'wp --path="{self.config["paths"]["live"]}" core is-installed --allow-root'
                    self.command_collector.add_command(
                        remote_wp_check,
                        "Check if WordPress is installed in remote environment",
                        "remote",
                        f"{self.config['ssh']['user']}"
                    )
                
                # Directory setup
                self.command_collector.set_section("Directory Setup")
                
                # Ensure local temp directory exists
                local_temp_dir = self.config["paths"]["db_temp"]
                mkdir_local_cmd = f'mkdir -p {local_temp_dir}'
                self.command_collector.add_command(
                    mkdir_local_cmd,
                    "Create local temporary directory for database files",
                    "local",
                    "Local User"
                )
                
                # Ensure remote temp directory exists if needed
                if self.direction == "push" or self.direction == "pull":
                    # Get the correct remote temp directory path
                    db_temp = self.config["paths"]["db_temp"]
                    remote_db_temp = ""
                    
                    # If db_temp is an absolute path, use it directly
                    if os.path.isabs(db_temp):
                        remote_db_temp = db_temp
                    # If db_temp starts with ../ or ./, it's relative to the live path's parent directory
                    elif db_temp.startswith(('../', './')):
                        # Get the parent directory of live_path
                        live_parent = os.path.dirname(self.config["paths"]["live"].rstrip('/'))
                        # Normalize the path to resolve any .. or . components
                        remote_db_temp = os.path.normpath(os.path.join(live_parent, db_temp))
                    # Otherwise, treat it as relative to the live path itself
                    else:
                        remote_db_temp = os.path.join(self.config["paths"]["live"], db_temp)
                    
                    mkdir_remote_cmd = f'mkdir -p {remote_db_temp}'
                    self.command_collector.add_command(
                        mkdir_remote_cmd,
                        "Create remote temporary directory for database files",
                        "remote",
                        f"{self.config['ssh']['user']}"
                    )
                
                # Pre-sync cleanup
                if "rsync" in self.config and "cleanup_files" in self.config["rsync"] and self.config["rsync"]["cleanup_files"]:
                    self.command_collector.set_section("Pre-sync Cleanup")
                    
                    if self.direction == "push":
                        # Cleanup on remote (destination)
                        for file_pattern in self.config["rsync"]["cleanup_files"]:
                            cleanup_cmd = f'find {self.config["paths"]["live"]} -name \'{file_pattern}\' -type f -delete'
                            self.command_collector.add_command(
                                cleanup_cmd,
                                f"Clean up {file_pattern} files on remote server before sync",
                                "remote",
                                f"{self.config['ssh']['user']}"
                            )
                    else:  # pull
                        # Cleanup on local (destination)
                        for file_pattern in self.config["rsync"]["cleanup_files"]:
                            cleanup_cmd = f'find {self.config["paths"]["local"]} -name \'{file_pattern}\' -type f -delete'
                            self.command_collector.add_command(
                                cleanup_cmd,
                                f"Clean up {file_pattern} files on local system before sync",
                                "local",
                                "Local User"
                            )
                
                # Maintenance mode commands
                self.command_collector.set_section("Maintenance Mode")
                local_maint_activate = f'wp --path="{self.config["paths"]["local"]}" maintenance-mode activate --allow-root'
                self.command_collector.add_command(
                    local_maint_activate,
                    "Activate maintenance mode on local WordPress",
                    "local",
                    "Local User (root)"
                )
                
                remote_maint_activate = f'wp --path="{self.config["paths"]["live"]}" maintenance-mode activate --allow-root'
                self.command_collector.add_command(
                    remote_maint_activate,
                    "Activate maintenance mode on remote WordPress",
                    "remote",
                    f"{self.config['ssh']['user']}"
                )
                
                # Alternative maintenance mode method (creating .maintenance file)
                local_maint_file = f'echo "<?php $upgrading = time(); ?>" > {os.path.join(self.config["paths"]["local"], ".maintenance")}'
                self.command_collector.add_command(
                    local_maint_file,
                    "Create .maintenance file on local WordPress (alternative method)",
                    "local",
                    "Local User"
                )
                
                remote_maint_file = f'echo "<?php $upgrading = time(); ?>" > {os.path.join(self.config["paths"]["live"], ".maintenance")}'
                self.command_collector.add_command(
                    remote_maint_file,
                    "Create .maintenance file on remote WordPress (alternative method)",
                    "remote",
                    f"{self.config['ssh']['user']}"
                )
                
                # Database commands - skip if files_only
                if not files_only:
                    self.command_collector.set_section("Database Operations")
                    
                    # Check if database backups are enabled
                    backup_enabled = False
                    if "backup" in self.config and "database" in self.config["backup"]:
                        backup_enabled = self.config["backup"]["database"].get("enabled", False)
                    
                    if self.direction == "push":
                        # Export from local
                        db_file = os.path.join(self.config["paths"]["db_temp"], self.config["paths"].get("db_filename", "wordpress-sync-database.sql"))
                        export_cmd = f'wp --path="{self.config["paths"]["local"]}" db export {db_file} --allow-root'
                        self.command_collector.add_command(
                            export_cmd,
                            "Export database from local WordPress",
                            "local",
                            "Local User (root)"
                        )
                        
                        # Transfer database file to remote
                        # Get the correct remote temp directory path
                        db_temp = self.config["paths"]["db_temp"]
                        remote_db_temp = ""
                        
                        # If db_temp is an absolute path, use it directly
                        if os.path.isabs(db_temp):
                            remote_db_temp = db_temp
                        # If db_temp starts with ../
                        elif db_temp.startswith('../'):
                            # Get the parent directory of the WordPress directory
                            live_parent = os.path.dirname(self.config["paths"]["live"].rstrip('/'))
                            # Remove the ../ prefix from db_temp
                            relative_path = db_temp[3:]
                            # Join the parent directory with the remaining path
                            remote_db_temp = os.path.join(live_parent, relative_path)
                        # Otherwise, treat it as relative to the live path itself
                        else:
                            remote_db_temp = os.path.join(self.config["paths"]["live"], db_temp)
                            
                        remote_db_file = os.path.join(remote_db_temp, self.config["paths"].get("db_filename", "wordpress-sync-database.sql"))
                        scp_cmd = f'scp -i {self.config["ssh"]["key_path"]} {db_file} {self.config["ssh"]["user"]}@{self.config["ssh"]["host"]}:{remote_db_file}'
                        self.command_collector.add_command(
                            scp_cmd,
                            "Transfer database file to remote server",
                            "local",
                            "Local User"
                        )
                        
                        # Database backup commands (if enabled)
                        if backup_enabled:
                            # Get backup paths
                            backup_dir = self.config["backup"]["database"].get("directory", "../wordpress-sync-db-backups")
                            filename_format = self.config["backup"]["database"].get("filename_format", "db-backup_%Y-%m-%d_%H%M%S.sql")
                            
                            # Resolve the full backup directory path
                            if os.path.isabs(backup_dir):
                                full_backup_dir = backup_dir
                            elif backup_dir.startswith('../'):
                                # Get the parent directory of the WordPress directory
                                live_parent = os.path.dirname(self.config["paths"]["live"].rstrip('/'))
                                # Remove the ../ prefix from backup_dir
                                relative_path = backup_dir[3:]
                                # Join the parent directory with the remaining path
                                full_backup_dir = os.path.join(live_parent, relative_path)
                            else:
                                # For other relative paths, join with live_path
                                full_backup_dir = os.path.join(self.config["paths"]["live"], backup_dir)
                                
                            # Create backup directory
                            mkdir_cmd = f"mkdir -p {full_backup_dir}"
                            self.command_collector.add_command(
                                mkdir_cmd,
                                "Create database backup directory on remote server",
                                "remote",
                                f"{self.config['ssh']['user']}"
                            )
                            
                            # Generate timestamp for backup filename
                            timestamp = time.strftime(filename_format.replace(".sql", ""))
                            backup_file = os.path.join(full_backup_dir, f"{timestamp}.sql")
                            
                            # Backup command
                            backup_cmd = f'wp --path="{self.config["paths"]["live"]}" db export {backup_file} --allow-root'
                            self.command_collector.add_command(
                                backup_cmd,
                                "Backup remote database before reset (optional)",
                                "remote",
                                f"{self.config['ssh']['user']}"
                            )
                        
                        # Reset and import to remote
                        reset_cmd = f'wp --path="{self.config["paths"]["live"]}" db reset --yes --allow-root'
                        self.command_collector.add_command(
                            reset_cmd,
                            "Reset database on remote WordPress",
                            "remote",
                            f"{self.config['ssh']['user']}"
                        )
                        
                        import_cmd = f'wp --path="{self.config["paths"]["live"]}" db import {remote_db_file} --allow-root'
                        self.command_collector.add_command(
                            import_cmd,
                            "Import database to remote WordPress",
                            "remote",
                            f"{self.config['ssh']['user']}"
                        )
                    else:  # pull
                        # Export from remote
                        # Get the correct remote temp directory path
                        db_temp = self.config["paths"]["db_temp"]
                        remote_db_temp = ""
                        
                        # If db_temp is an absolute path, use it directly
                        if os.path.isabs(db_temp):
                            remote_db_temp = db_temp
                        # If db_temp starts with ../
                        elif db_temp.startswith('../'):
                            # Get the parent directory of the WordPress directory
                            live_parent = os.path.dirname(self.config["paths"]["live"].rstrip('/'))
                            # Remove the ../ prefix from db_temp
                            relative_path = db_temp[3:]
                            # Join the parent directory with the remaining path
                            remote_db_temp = os.path.join(live_parent, relative_path)
                        # Otherwise, treat it as relative to the live path itself
                        else:
                            remote_db_temp = os.path.join(self.config["paths"]["live"], db_temp)
                            
                        remote_db_file = os.path.join(remote_db_temp, self.config["paths"].get("db_filename", "wordpress-sync-database.sql"))
                        export_cmd = f'wp --path="{self.config["paths"]["live"]}" db export {remote_db_file} --allow-root'
                        self.command_collector.add_command(
                            export_cmd,
                            "Export database from remote WordPress",
                            "remote",
                            f"{self.config['ssh']['user']}"
                        )
                        
                        # Transfer database file to local
                        db_file = os.path.join(self.config["paths"]["db_temp"], self.config["paths"].get("db_filename", "wordpress-sync-database.sql"))
                        scp_cmd = f'scp -i {self.config["ssh"]["key_path"]} {self.config["ssh"]["user"]}@{self.config["ssh"]["host"]}:{remote_db_file} {db_file}'
                        self.command_collector.add_command(
                            scp_cmd,
                            "Transfer database file to local system",
                            "local",
                            "Local User"
                        )
                        
                        # Database backup commands (if enabled)
                        if backup_enabled:
                            # Get backup paths
                            backup_dir = self.config["backup"]["database"].get("directory", "../wordpress-sync-db-backups")
                            filename_format = self.config["backup"]["database"].get("filename_format", "db-backup_%Y-%m-%d_%H%M%S.sql")
                            
                            # Resolve the full backup directory path
                            if os.path.isabs(backup_dir):
                                full_backup_dir = backup_dir
                            elif backup_dir.startswith('../'):
                                # Get the parent directory of the WordPress directory
                                local_parent = os.path.dirname(self.config["paths"]["local"].rstrip('/'))
                                # Remove the ../ prefix from backup_dir
                                relative_path = backup_dir[3:]
                                # Join the parent directory with the remaining path
                                full_backup_dir = os.path.join(local_parent, relative_path)
                            else:
                                # For other relative paths, join with local_path
                                full_backup_dir = os.path.join(self.config["paths"]["local"], backup_dir)
                                
                            # Create backup directory
                            mkdir_cmd = f"mkdir -p {full_backup_dir}"
                            self.command_collector.add_command(
                                mkdir_cmd,
                                "Create database backup directory on local system",
                                "local",
                                "Local User"
                            )
                            
                            # Generate timestamp for backup filename
                            timestamp = time.strftime(filename_format.replace(".sql", ""))
                            backup_file = os.path.join(full_backup_dir, f"{timestamp}.sql")
                            
                            # Backup command
                            backup_cmd = f'wp --path="{self.config["paths"]["local"]}" db export {backup_file} --allow-root'
                            self.command_collector.add_command(
                                backup_cmd,
                                "Backup local database before reset (optional)",
                                "local",
                                "Local User (root)"
                            )
                        
                        # Reset and import to local
                        reset_cmd = f'wp --path="{self.config["paths"]["local"]}" db reset --yes --allow-root'
                        self.command_collector.add_command(
                            reset_cmd,
                            "Reset database on local WordPress",
                            "local",
                            "Local User (root)"
                        )
                        
                        import_cmd = f'wp --path="{self.config["paths"]["local"]}" db import {db_file} --allow-root'
                        self.command_collector.add_command(
                            import_cmd,
                            "Import database to local WordPress",
                            "local",
                            "Local User (root)"
                        )
                
                # File transfer commands - skip if db_only
                if not db_only:
                    self.command_collector.set_section("File Transfer")
                    
                    # Build rsync options
                    rsync_options = self.ssh_manager._build_rsync_options()
                    rsync_opts_str = " ".join(rsync_options)
                    
                    # Display rsync options details as a single description
                    rsync_description = f"Using the following rsync options: {rsync_opts_str}\n"
                    
                    if "rsync" in self.config:
                        if "chmod_files" in self.config["rsync"]:
                            rsync_description += f"Files will be set to permission {self.config['rsync']['chmod_files']}\n"
                        if "chmod_dirs" in self.config["rsync"]:
                            rsync_description += f"Directories will be set to permission {self.config['rsync']['chmod_dirs']}\n"
                        if "excludes" in self.config["rsync"] and self.config["rsync"]["excludes"]:
                            exclude_list = ", ".join(self.config["rsync"]["excludes"])
                            rsync_description += f"The following items will be excluded from transfer: {exclude_list}"
                    
                    self.command_collector.add_command(
                        "",
                        rsync_description,
                        "both"
                    )
                    
                    # Set source and destination based on direction
                    local_path = self.config["paths"]["local"] if self.config["paths"]["local"].endswith('/') else f"{self.config['paths']['local']}/"
                    live_path = self.config["paths"]["live"] if self.config["paths"]["live"].endswith('/') else f"{self.config['paths']['live']}/"
                    
                    if self.direction == "push":
                        rsync_cmd = f"rsync {rsync_opts_str} {local_path} {self.config['ssh']['user']}@{self.config['ssh']['host']}:{live_path}"
                        self.command_collector.add_command(
                            rsync_cmd,
                            "Transfer files from local to remote server",
                            "local",
                            "Local User"
                        )
                        
                        # Permission commands
                        if "ownership" in self.config:
                            user = self.config["ownership"]["user"]
                            group = self.config["ownership"]["group"]
                            
                            chown_cmd = f"sudo chown -R {user}:{group} {live_path}"
                            self.command_collector.add_command(
                                chown_cmd,
                                "Set ownership of files on remote server",
                                "remote",
                                f"{self.config['ssh']['sudo']['user']} (sudo)"
                            )
                            
                            chmod_dirs_cmd = f"sudo find {live_path} -type d -exec chmod 755 {{}} \\;"
                            self.command_collector.add_command(
                                chmod_dirs_cmd,
                                "Set directory permissions on remote server",
                                "remote",
                                f"{self.config['ssh']['sudo']['user']} (sudo)"
                            )
                            
                            chmod_files_cmd = f"sudo find {live_path} -type f -exec chmod 644 {{}} \\;"
                            self.command_collector.add_command(
                                chmod_files_cmd,
                                "Set file permissions on remote server",
                                "remote",
                                f"{self.config['ssh']['sudo']['user']} (sudo)"
                            )
                    else:  # pull
                        rsync_cmd = f"rsync {rsync_opts_str} {self.config['ssh']['user']}@{self.config['ssh']['host']}:{live_path} {local_path}"
                        self.command_collector.add_command(
                            rsync_cmd,
                            "Transfer files from remote to local server",
                            "local",
                            "Local User"
                        )
                
                # URL replacement commands - skip if files_only
                if not files_only:
                    self.command_collector.set_section("URL Replacement")
                    
                    if self.direction == "push":
                        # Replace staging URLs with live URLs on the remote server
                        target_path = self.config["paths"]["live"]
                        search_domains = self.config["domains"]["staging"]
                        replace_domains = self.config["domains"]["live"]
                        is_remote = True
                    else:  # pull
                        # Replace live URLs with staging URLs on the local server
                        target_path = self.config["paths"]["local"]
                        search_domains = self.config["domains"]["live"]
                        replace_domains = self.config["domains"]["staging"]
                        is_remote = False
                    
                    # HTTP URLs
                    search_url = search_domains["http"]
                    replace_url = replace_domains["http"]
                    search_replace_cmd = f'wp --path="{target_path}" search-replace "{search_url}" "{replace_url}" --all-tables --allow-root'
                    self.command_collector.add_command(
                        search_replace_cmd,
                        f"Replace HTTP URLs: {search_url} → {replace_url}",
                        "remote" if is_remote else "local",
                        f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                    )
                    
                    # HTTPS URLs
                    search_url = search_domains["https"]
                    replace_url = replace_domains["https"]
                    search_replace_cmd = f'wp --path="{target_path}" search-replace "{search_url}" "{replace_url}" --all-tables --allow-root'
                    self.command_collector.add_command(
                        search_replace_cmd,
                        f"Replace HTTPS URLs: {search_url} → {replace_url}",
                        "remote" if is_remote else "local",
                        f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                    )
                    
                    # Domain without protocol
                    search_url = search_domains["http"].replace("http://", "")
                    replace_url = replace_domains["http"].replace("http://", "")
                    search_replace_cmd = f'wp --path="{target_path}" search-replace "{search_url}" "{replace_url}" --all-tables --allow-root'
                    self.command_collector.add_command(
                        search_replace_cmd,
                        f"Replace domain without protocol: {search_url} → {replace_url}",
                        "remote" if is_remote else "local",
                        f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                    )
                    
                    # Escaped URLs for JSON data
                    search_url = search_domains["https"].replace(":", "\\:").replace("/", "\\/")
                    replace_url = replace_domains["https"].replace(":", "\\:").replace("/", "\\/")
                    search_replace_cmd = f'wp --path="{target_path}" search-replace "{search_url}" "{replace_url}" --all-tables --allow-root'
                    self.command_collector.add_command(
                        search_replace_cmd,
                        f"Replace escaped URLs for JSON data: {search_url} → {replace_url}",
                        "remote" if is_remote else "local",
                        f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                    )
                    
                    # Cache clearing
                    cache_cmd = f'wp --path="{target_path}" cache flush --allow-root'
                    self.command_collector.add_command(
                        cache_cmd,
                        "Clear WordPress cache",
                        "remote" if is_remote else "local",
                        f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                    )
                
                # Plugin management commands
                if "plugins" in self.config:
                    self.command_collector.set_section("Plugin Management")
                    
                    # Get target environment and plugin lists
                    target_env = "live" if self.direction == "push" else "local"
                    
                    # Plugins to activate
                    if target_env in self.config["plugins"] and "activate" in self.config["plugins"][target_env]:
                        plugins_to_activate = self.config["plugins"][target_env]["activate"]
                        if plugins_to_activate:
                            plugin_list = " ".join(plugins_to_activate)
                            activate_cmd = f'wp --path="{target_path}" plugin activate {plugin_list} --allow-root'
                            self.command_collector.add_command(
                                activate_cmd,
                                f"Activate plugins on {target_env} environment: {', '.join(plugins_to_activate)}",
                                "remote" if is_remote else "local",
                                f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                            )
                    
                    # Plugins to deactivate
                    if target_env in self.config["plugins"] and "deactivate" in self.config["plugins"][target_env]:
                        plugins_to_deactivate = self.config["plugins"][target_env]["deactivate"]
                        if plugins_to_deactivate:
                            plugin_list = " ".join(plugins_to_deactivate)
                            deactivate_cmd = f'wp --path="{target_path}" plugin deactivate {plugin_list} --allow-root'
                            self.command_collector.add_command(
                                deactivate_cmd,
                                f"Deactivate plugins on {target_env} environment: {', '.join(plugins_to_deactivate)}",
                                "remote" if is_remote else "local",
                                f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                            )
                
                # Validation commands
                if not self.args.skip_validation:
                    self.command_collector.set_section("Validation")
                    
                    if not files_only:
                        # Database validation
                        tables_cmd = f'wp --path="{target_path}" db tables --allow-root'
                        self.command_collector.add_command(
                            tables_cmd,
                            "List database tables to verify database integrity",
                            "remote" if is_remote else "local",
                            f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                        )
                        
                        # Get table prefix
                        prefix_cmd = f'wp --path="{target_path}" config get table_prefix --allow-root'
                        self.command_collector.add_command(
                            prefix_cmd,
                            "Get WordPress database table prefix",
                            "remote" if is_remote else "local",
                            f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                        )
                        
                        # Check additional tables if specified
                        if "validation" in self.config and "checks" in self.config["validation"] and \
                           "database" in self.config["validation"]["checks"] and \
                           "additional_tables" in self.config["validation"]["checks"]["database"] and \
                           self.config["validation"]["checks"]["database"]["additional_tables"]:
                            additional_tables = ", ".join(self.config["validation"]["checks"]["database"]["additional_tables"])
                            self.command_collector.add_command(
                                "# Additional tables check:",
                                f"Verify these additional tables exist: {additional_tables}",
                                "remote" if is_remote else "local"
                            )
                    
                    if not db_only:
                        # Core files validation
                        checksums_cmd = f'wp --path="{target_path}" core verify-checksums --allow-root'
                        self.command_collector.add_command(
                            checksums_cmd,
                            "Verify WordPress core file checksums",
                            "remote" if is_remote else "local",
                            f"{self.config['ssh']['user']}" if is_remote else "Local User (root)"
                        )
                        
                        # Critical files check
                        if "validation" in self.config and "checks" in self.config["validation"] and \
                           "core_files" in self.config["validation"]["checks"] and \
                           "critical_files" in self.config["validation"]["checks"]["core_files"]:
                            for file in self.config["validation"]["checks"]["core_files"]["critical_files"]:
                                file_path = os.path.join(target_path, file)
                                check_cmd = f'test -f "{file_path}" && echo "exists" || echo "not found"'
                                self.command_collector.add_command(
                                    check_cmd,
                                    f"Check if critical file exists: {file}",
                                    "remote" if is_remote else "local",
                                    f"{self.config['ssh']['user']}" if is_remote else "Local User"
                                )
                    
                    # Accessibility checks
                    if "validation" in self.config and "checks" in self.config["validation"] and \
                       "accessibility" in self.config["validation"]["checks"]:
                        
                        # Homepage check
                        if self.config["validation"]["checks"]["accessibility"].get("homepage", True):
                            if self.direction == "push":
                                url = self.config["domains"]["live"]["https"]
                            else:  # pull
                                url = self.config["domains"]["staging"]["https"]
                                
                            curl_cmd = f'curl -sSL --head "{url}" | grep -E "^HTTP"'
                            self.command_collector.add_command(
                                curl_cmd,
                                f"Check if homepage is accessible: {url}",
                                "local",
                                "Local User"
                            )
                        
                        # WP Admin check
                        if self.config["validation"]["checks"]["accessibility"].get("wp_admin", True):
                            if self.direction == "push":
                                url = f"{self.config['domains']['live']['https']}/wp-admin/"
                            else:  # pull
                                url = f"{self.config['domains']['staging']['https']}/wp-admin/"
                                
                            curl_cmd = f'curl -sSL --head "{url}" | grep -E "^HTTP"'
                            self.command_collector.add_command(
                                curl_cmd,
                                f"Check if wp-admin is accessible: {url}",
                                "local",
                                "Local User"
                            )
                
                # Maintenance mode deactivation
                self.command_collector.set_section("Maintenance Mode Deactivation")
                
                local_maint_deactivate = f'wp --path="{self.config["paths"]["local"]}" maintenance-mode deactivate --allow-root'
                self.command_collector.add_command(
                    local_maint_deactivate,
                    "Deactivate maintenance mode on local WordPress",
                    "local",
                    "Local User (root)"
                )
                
                remote_maint_deactivate = f'wp --path="{self.config["paths"]["live"]}" maintenance-mode deactivate --allow-root'
                self.command_collector.add_command(
                    remote_maint_deactivate,
                    "Deactivate maintenance mode on remote WordPress",
                    "remote",
                    f"{self.config['ssh']['user']}"
                )
                
                # Add verification message
                self.command_collector.add_command(
                    "",
                    "After maintenance mode is deactivated, verify the site is functioning correctly at the appropriate URL",
                    "both"
                )
                
                # Trash operations
                if not self.args.no_trash:
                    self.command_collector.set_section("Trash Management")
                    
                    # Get the trash directory path
                    trash_dir = self._get_trash_path()
                    
                    # Check for existing trash before sync
                    if self.direction == "push":
                        check_cmd = f"test -d {trash_dir} && find {trash_dir} -type f | wc -l || echo 0"
                        self.command_collector.add_command(
                            check_cmd,
                            f"Check for existing files in trash directory: {trash_dir}",
                            "remote",
                            f"{self.config['ssh']['user']}"
                        )
                        
                        mkdir_cmd = f"mkdir -p {trash_dir}"
                        self.command_collector.add_command(
                            mkdir_cmd,
                            f"Ensure trash directory exists: {trash_dir}",
                            "remote",
                            f"{self.config['ssh']['user']}"
                        )
                    else:
                        check_cmd = f"test -d {trash_dir} && find {trash_dir} -type f | wc -l || echo 0"
                        self.command_collector.add_command(
                            check_cmd,
                            f"Check for existing files in trash directory: {trash_dir}",
                            "local",
                            "Local User"
                        )
                        
                        mkdir_cmd = f"mkdir -p {trash_dir}"
                        self.command_collector.add_command(
                            mkdir_cmd,
                            f"Ensure trash directory exists: {trash_dir}",
                            "local",
                            "Local User"
                        )
                    
                    # Note about backup during rsync
                    self.command_collector.add_command(
                        "",
                        f"Files that would be deleted or modified will be backed up to: {trash_dir}",
                        "both"
                    )
                    
                    # Final trash cleanup
                    if self.direction == "push":
                        list_cmd = f"find {trash_dir} -type f | sort"
                        self.command_collector.add_command(
                            list_cmd,
                            "List backed up files after sync",
                            "remote",
                            f"{self.config['ssh']['user']}"
                        )
                        
                        # Add command to remove entire trash directory
                        rm_cmd = f"rm -rf {trash_dir}"
                        self.command_collector.add_command(
                            rm_cmd,
                            "Remove trash directory when user chooses to delete backed up files",
                            "remote",
                            f"{self.config['ssh']['user']}"
                        )
                    else:
                        list_cmd = f"find {trash_dir} -type f | sort"
                        self.command_collector.add_command(
                            list_cmd,
                            "List backed up files after sync",
                            "local",
                            "Local User"
                        )
                        
                        # Add command to remove entire trash directory
                        rm_cmd = f"rm -rf {trash_dir}"
                        self.command_collector.add_command(
                            rm_cmd,
                            "Remove trash directory when user chooses to delete backed up files",
                            "local",
                            "Local User"
                        )
                
                # Final cleanup
                self.command_collector.set_section("Cleanup")
                
                # Display all collected commands
                print(self.command_collector.format_commands())
                return True
            
            print(f"\nStarting {'dry run of ' if self.dry_run else ''}{sync_type} WordPress synchronization: {source_env} → {target_env}")
            
            # Check for existing trash before sync (if not --no-trash)
            if self.args.no_trash:
                print("\nSkipping trash operations (--no-trash flag used)")
            elif self.dry_run:
                trash_dir = self._get_trash_path()
                print(f"\nDuring actual sync, existing files in trash directory will be checked: {trash_dir}")
                print("You will be prompted to keep or remove existing trash before sync")
            else:
                print("\nChecking for existing trash...")
                if not self.handle_existing_trash():
                    return False
            
            # Step 1: Enable maintenance mode (always do this for safety)
            print("\nStep 1: Enabling maintenance mode...")
            self.maintenance_manager.activate_maintenance_mode(self.direction, self.dry_run)
            
            # Database operations - skip if files_only
            db_file = None
            if not files_only:
                # Step 2: Export database from source
                print("\nStep 2: Exporting database from source...")
                db_file = self.database_manager.export_database(self.direction, self.dry_run)
            else:
                print("\nStep 2: Skipping database export (--files-only flag used)")
            
            # File operations - skip if db_only
            if not db_only:
                # Step 3: Transfer files
                print("\nStep 3: Transferring files...")
                self.ssh_manager.transfer_files(self.direction, self.dry_run, sudo_password=self.args.sudo_password)
                
                # Step 4: Set file permissions (only for push)
                if self.direction == "push" and not self.dry_run:
                    print("\nStep 4: Setting file permissions...")
                    self.ssh_manager.set_permissions(sudo_password=self.args.sudo_password)
            else:
                print("\nStep 3: Skipping file transfer (--db-only flag used)")
                print("\nStep 4: Skipping permission setting (--db-only flag used)")
            
            # More database operations - skip if files_only
            if not files_only and db_file:
                # Step 5: Import database to target
                print("\nStep 5: Importing database to target...")
                self.database_manager.import_database(self.direction, db_file, self.dry_run)
                
                # Step 6: Update URLs
                print("\nStep 6: Updating URLs...")
                self.url_manager.replace_urls(self.direction, self.dry_run)
                
                # Step 7: Clear cache
                print("\nStep 7: Clearing cache...")
                self.database_manager.clear_cache(self.direction, self.dry_run)
                
                # Step 8: Manage plugins
                print("\nStep 8: Managing plugins...")
                self.plugin_manager.manage_plugins(self.direction, self.dry_run)
            else:
                print("\nStep 5: Skipping database import (--files-only flag used)")
                print("\nStep 6: Skipping URL replacement (--files-only flag used)")
                print("\nStep 7: Skipping cache clearing (--files-only flag used)")
                print("\nStep 8: Skipping plugin management (--files-only flag used)")
            
            # Step 9: Run validation checks
            if not self.args.skip_validation and not self.dry_run:
                print("\nStep 9: Running validation checks...")
                # Pass flags to validation manager to skip irrelevant checks
                validation_result = self.validation_manager.run_validation_checks(
                    self.direction,
                    skip_files=db_only,
                    skip_db=files_only
                )
                if not validation_result:
                    print("Warning: Validation checks failed. Please verify the site manually.")
            
            # Step 10: Disable maintenance mode (always do this)
            print("\nStep 10: Disabling maintenance mode...")
            self.maintenance_manager.deactivate_maintenance_mode(self.direction, self.dry_run)
            
            # Add a pause and message for user verification
            print("\nMaintenance mode has been deactivated.")
            print("Please verify the site is functioning correctly at:")
            if self.direction == "push":
                print(f"  {self.config['domains']['live']['https']}")
            else:
                print(f"  {self.config['domains']['staging']['https']}")
            
            # Step 11: Review backed up files (if not --no-trash)
            if self.args.no_trash:
                print("\nStep 11: Skipping trash operations (--no-trash flag used)")
            elif self.dry_run:
                trash_dir = self._get_trash_path()
                print(f"\nStep 11: During actual sync, files will be backed up to: {trash_dir}")
                print("         You will be prompted to review backed up files after verifying the site")
            else:
                print("\nStep 11: Reviewing backed up files...")
                if not self.handle_final_trash_cleanup():
                    return False
            
            # Step 12: Clean up
            print("\nStep 12: Cleaning up temporary files...")
            if db_file:
                self.database_manager.cleanup(self.direction, db_file, self.dry_run)
            else:
                print("No database file to clean up")
            
            print("\nSynchronization completed successfully!")
            return True
            
        except Exception as e:
            print(f"\nError during synchronization: {e}")
            
            # Try to disable maintenance mode in case of error
            try:
                print("Attempting to disable maintenance mode...")
                self.maintenance_manager.deactivate_maintenance_mode(self.direction, False)
            except Exception as me:
                print(f"Error disabling maintenance mode: {me}")
                
            return False

    def run(self):
        """Main method to run the synchronization tool."""
        try:
            # Parse command line arguments
            self.parse_arguments()
            
            # Set environment variable for skipping WordPress installation check
            if self.args.skip_wp_check:
                os.environ['WORDPRESS_SYNC_SKIP_WP_CHECK'] = 'true'
                print("WordPress installation check will be skipped (--skip-wp-check)")
            
            # Initialize resource managers
            if not self.initialize_managers():
                return 1
            
            # If --command-only flag is used, skip environment validation
            if self.args.command_only:
                if not self.run_synchronization():
                    return 1
                return 0
                
            # Validate environment
            if not self.validate_environment():
                return 1
                
            # Run synchronization (dry run first if enabled)
            if self.dry_run:
                if not self.run_synchronization():
                    return 1
                    
                # Confirm with user before actual synchronization
                if not self.confirm_synchronization():
                    return 0
            
            # Run actual synchronization
            if not self.run_synchronization():
                return 1
                
            return 0
            
        except KeyboardInterrupt:
            print("\nSynchronization cancelled by user.")
            return 1
        except Exception as e:
            print(f"Unhandled error: {e}")
            return 1


if __name__ == "__main__":
    wordpress_sync = WordPressSync()
    sys.exit(wordpress_sync.run())
