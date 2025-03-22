#!/usr/bin/env python3
"""
Plugin Manager for WordPress Sync.

This module handles WordPress plugin activation and deactivation during the synchronization process.
It ensures that specific plugins are activated or deactivated on the target environment
based on the configuration.
"""

import os
import subprocess
import sys


class PluginManager:
    """Manages WordPress plugin operations for WordPress Sync."""

    def __init__(self, config):
        """
        Initialize the Plugin Manager.

        Args:
            config (dict): Configuration dictionary.
        """
        self.config = config
        self.local_path = config["paths"]["local"]
        self.live_path = config["paths"]["live"]
        
        # Check if plugins configuration exists
        self.plugins_config = config.get("plugins", {})
        self.has_plugin_config = bool(self.plugins_config)

    def manage_plugins(self, direction, dry_run=False):
        """
        Manage plugins based on the synchronization direction.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if plugin management is successful, False otherwise.
        """
        if not self.has_plugin_config:
            print("No plugin configuration found. Skipping plugin management.")
            return True

        if direction == "push":
            # When pushing, manage plugins on the live environment
            target_path = self.live_path
            target_env = "live"
            is_remote = True
        else:  # pull
            # When pulling, manage plugins on the local environment
            target_path = self.local_path
            target_env = "local"
            is_remote = False

        # Get plugin lists for the target environment
        plugins_to_activate = self.plugins_config.get(target_env, {}).get("activate", [])
        plugins_to_deactivate = self.plugins_config.get(target_env, {}).get("deactivate", [])

        if not plugins_to_activate and not plugins_to_deactivate:
            print(f"No plugins configured for {target_env} environment. Skipping plugin management.")
            return True

        if dry_run:
            print(f"[DRY RUN] Would manage plugins on {target_env} environment:")
            if plugins_to_activate:
                print(f"  - Would activate: {', '.join(plugins_to_activate)}")
            if plugins_to_deactivate:
                print(f"  - Would deactivate: {', '.join(plugins_to_deactivate)}")
            return True

        # Activate plugins
        if plugins_to_activate:
            print(f"Activating plugins on {target_env} environment: {', '.join(plugins_to_activate)}")
            success = self._activate_plugins(target_path, plugins_to_activate, is_remote)
            if not success:
                print(f"Warning: Failed to activate some plugins on {target_env} environment")

        # Deactivate plugins
        if plugins_to_deactivate:
            print(f"Deactivating plugins on {target_env} environment: {', '.join(plugins_to_deactivate)}")
            success = self._deactivate_plugins(target_path, plugins_to_deactivate, is_remote)
            if not success:
                print(f"Warning: Failed to deactivate some plugins on {target_env} environment")

        return True

    def _activate_plugins(self, path, plugins, is_remote=False):
        """
        Activate WordPress plugins.

        Args:
            path (str): Path to WordPress installation.
            plugins (list): List of plugin slugs to activate.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if activation is successful, False otherwise.
        """
        return self._manage_plugin_state(path, plugins, "activate", is_remote)

    def _deactivate_plugins(self, path, plugins, is_remote=False):
        """
        Deactivate WordPress plugins.

        Args:
            path (str): Path to WordPress installation.
            plugins (list): List of plugin slugs to deactivate.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if deactivation is successful, False otherwise.
        """
        return self._manage_plugin_state(path, plugins, "deactivate", is_remote)

    def _manage_plugin_state(self, path, plugins, action, is_remote=False):
        """
        Manage WordPress plugin state (activate or deactivate).

        Args:
            path (str): Path to WordPress installation.
            plugins (list): List of plugin slugs to manage.
            action (str): Action to perform ('activate' or 'deactivate').
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if the operation is successful, False otherwise.
        """
        if not plugins:
            return True

        # Join plugin slugs with spaces for the WP-CLI command
        plugin_list = " ".join(plugins)
        
        # Build the WP-CLI command
        cmd = f'wp --path="{path}" plugin {action} {plugin_list} --allow-root'
        
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            success, output = ssh_manager.execute_remote_command(cmd)
            
            if not success:
                print(f"Failed to {action} plugins on remote server: {output}")
                return False
                
            print(f"Successfully {action}d plugins on remote server")
        else:
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to {action} plugins: {result.stderr}")
                    return False
                    
                print(f"Successfully {action}d plugins")
                
            except Exception as e:
                print(f"Error {action}ing plugins: {e}")
                return False

        return True
