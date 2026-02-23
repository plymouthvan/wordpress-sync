#!/usr/bin/env python3
"""
Maintenance Manager for WordPress Sync.

This module manages the activation and deactivation of maintenance mode
during WordPress synchronization to prevent user access during the process.
"""

import os
import subprocess
import sys
from pathlib import Path


class MaintenanceManager:
    """Manages maintenance mode for WordPress Sync."""

    def __init__(self, config):
        """
        Initialize the Maintenance Manager.

        Args:
            config (dict): Configuration dictionary.
        """
        self.config = config
        self.local_path = config["paths"]["local"]
        self.live_path = config["paths"]["live"]

    def activate_maintenance_mode(self, direction, dry_run=False):
        """
        Activate maintenance mode on both local and remote environments.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if activation is successful, False otherwise.
        """
        if dry_run:
            print("[DRY RUN] Would activate maintenance mode on local and remote environments")
            return True

        # Activate maintenance mode on local environment
        local_success = self._activate_local_maintenance_mode()
        if not local_success:
            print("Warning: Failed to activate maintenance mode on local environment")

        # Activate maintenance mode on remote environment
        remote_success = self._activate_remote_maintenance_mode()
        if not remote_success:
            print("Warning: Failed to activate maintenance mode on remote environment")

        return local_success and remote_success

    def deactivate_maintenance_mode(self, direction, dry_run=False):
        """
        Deactivate maintenance mode on both local and remote environments.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if deactivation is successful, False otherwise.
        """
        if dry_run:
            print("[DRY RUN] Would deactivate maintenance mode on local and remote environments")
            return True

        # Deactivate maintenance mode on local environment
        local_success = self._deactivate_local_maintenance_mode()
        if not local_success:
            print("Warning: Failed to deactivate maintenance mode on local environment")

        # Deactivate maintenance mode on remote environment
        remote_success = self._deactivate_remote_maintenance_mode()
        if not remote_success:
            print("Warning: Failed to deactivate maintenance mode on remote environment")

        return local_success and remote_success

    def _activate_local_maintenance_mode(self):
        """
        Activate maintenance mode on the local environment.

        Returns:
            bool: True if activation is successful, False otherwise.
        """
        try:
            print("Activating maintenance mode on local environment...")
            cmd = f'wp --path="{self.local_path}" maintenance-mode activate --allow-root'
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                shell=True
            )
            
            if result.returncode != 0:
                print(f"Failed to activate maintenance mode on local environment: {result.stderr}")
                return False
                
            print("Maintenance mode activated on local environment")
            return True
            
        except Exception as e:
            print(f"Error activating maintenance mode on local environment: {e}")
            return False

    def _deactivate_local_maintenance_mode(self):
        """
        Deactivate maintenance mode on the local environment.

        Returns:
            bool: True if deactivation is successful, False otherwise.
        """
        try:
            print("Deactivating maintenance mode on local environment...")
            cmd = f'wp --path="{self.local_path}" maintenance-mode deactivate --allow-root'
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                shell=True
            )
            
            if result.returncode != 0:
                print(f"Failed to deactivate maintenance mode on local environment: {result.stderr}")
                return False
                
            print("Maintenance mode deactivated on local environment")
            return True
            
        except Exception as e:
            print(f"Error deactivating maintenance mode on local environment: {e}")
            return False

    def _activate_remote_maintenance_mode(self):
        """
        Activate maintenance mode on the remote environment.

        Returns:
            bool: True if activation is successful, False otherwise.
        """
        try:
            print("Activating maintenance mode on remote environment...")
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            cmd = f'wp --path="{self.live_path}" maintenance-mode activate --allow-root'
            success, output = ssh_manager.execute_remote_command(cmd)
            
            if not success:
                print(f"Failed to activate maintenance mode on remote environment: {output}")
                return False
                
            print("Maintenance mode activated on remote environment")
            return True
            
        except Exception as e:
            print(f"Error activating maintenance mode on remote environment: {e}")
            return False

    def _deactivate_remote_maintenance_mode(self):
        """
        Deactivate maintenance mode on the remote environment.

        Returns:
            bool: True if deactivation is successful, False otherwise.
        """
        try:
            print("Deactivating maintenance mode on remote environment...")
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            cmd = f'wp --path="{self.live_path}" maintenance-mode deactivate --allow-root'
            success, output = ssh_manager.execute_remote_command(cmd)
            
            if not success:
                print(f"Failed to deactivate maintenance mode on remote environment: {output}")
                return False
                
            print("Maintenance mode deactivated on remote environment")
            return True
            
        except Exception as e:
            print(f"Error deactivating maintenance mode on remote environment: {e}")
            return False

    def check_maintenance_mode_status(self, is_remote=False):
        """
        Check the status of maintenance mode.

        Args:
            is_remote (bool): Whether to check the remote environment.

        Returns:
            bool: True if maintenance mode is active, False otherwise.
        """
        try:
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                cmd = f'wp --path="{self.live_path}" maintenance-mode status --allow-root'
                success, output = ssh_manager.execute_remote_command(cmd)
                
                if not success:
                    print(f"Failed to check maintenance mode status on remote environment: {output}")
                    return False
                    
                return "is active" in output.lower()
            else:
                cmd = f'wp --path="{self.local_path}" maintenance-mode status --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to check maintenance mode status on local environment: {result.stderr}")
                    return False
                    
                return "is active" in result.stdout.lower()
                
        except Exception as e:
            print(f"Error checking maintenance mode status: {e}")
            return False

    def create_maintenance_file(self, is_remote=False, dry_run=False):
        """
        Create a .maintenance file as a fallback method.

        Args:
            is_remote (bool): Whether to create the file on the remote environment.
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if file creation is successful, False otherwise.
        """
        if dry_run:
            print(f"[DRY RUN] Would create .maintenance file on {'remote' if is_remote else 'local'} environment")
            return True

        maintenance_content = "<?php $upgrading = time(); ?>"
        
        try:
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                # Create temporary file locally
                raw_db_temp = self.config["paths"]["db_temp"]
                local_db_temp = raw_db_temp.get("local", "/tmp") if isinstance(raw_db_temp, dict) else raw_db_temp
                temp_file = os.path.join(local_db_temp, ".maintenance")
                with open(temp_file, "w") as f:
                    f.write(maintenance_content)
                
                # Transfer to remote
                remote_file = os.path.join(self.live_path, ".maintenance")
                success = ssh_manager.transfer_file(temp_file, remote_file, "push")
                
                # Clean up temporary file
                os.remove(temp_file)
                
                if not success:
                    print("Failed to create .maintenance file on remote environment")
                    return False
                    
                print(".maintenance file created on remote environment")
                return True
            else:
                maintenance_file = os.path.join(self.local_path, ".maintenance")
                with open(maintenance_file, "w") as f:
                    f.write(maintenance_content)
                    
                print(".maintenance file created on local environment")
                return True
                
        except Exception as e:
            print(f"Error creating .maintenance file: {e}")
            return False

    def remove_maintenance_file(self, is_remote=False, dry_run=False):
        """
        Remove the .maintenance file.

        Args:
            is_remote (bool): Whether to remove the file from the remote environment.
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if file removal is successful, False otherwise.
        """
        if dry_run:
            print(f"[DRY RUN] Would remove .maintenance file from {'remote' if is_remote else 'local'} environment")
            return True

        try:
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                remote_file = os.path.join(self.live_path, ".maintenance")
                cmd = f'rm -f "{remote_file}"'
                success, _ = ssh_manager.execute_remote_command(cmd)
                
                if not success:
                    print("Failed to remove .maintenance file from remote environment")
                    return False
                    
                print(".maintenance file removed from remote environment")
                return True
            else:
                maintenance_file = os.path.join(self.local_path, ".maintenance")
                if os.path.exists(maintenance_file):
                    os.remove(maintenance_file)
                    
                print(".maintenance file removed from local environment")
                return True
                
        except Exception as e:
            print(f"Error removing .maintenance file: {e}")
            return False
