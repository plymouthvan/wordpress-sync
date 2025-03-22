#!/usr/bin/env python3
"""
URL Manager for WordPress Sync.

This module manages URL search-replace operations in the database to ensure
correct URL mapping after synchronization between environments.
"""

import os
import subprocess
import sys
from pathlib import Path


class URLManager:
    """Manages URL search-replace operations for WordPress Sync."""

    def __init__(self, config):
        """
        Initialize the URL Manager.

        Args:
            config (dict): Configuration dictionary.
        """
        self.config = config
        self.local_path = config["paths"]["local"]
        self.live_path = config["paths"]["live"]
        self.staging_domain = config["domains"]["staging"]
        self.live_domain = config["domains"]["live"]

    def replace_urls(self, direction, dry_run=False):
        """
        Replace URLs in the database based on synchronization direction.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if URL replacement is successful, False otherwise.
        """
        if direction == "push":
            # Replace staging URLs with live URLs on the remote server
            target_path = self.live_path
            search_domains = self.staging_domain
            replace_domains = self.live_domain
            is_remote = True
        else:  # pull
            # Replace live URLs with staging URLs on the local server
            target_path = self.local_path
            search_domains = self.live_domain
            replace_domains = self.staging_domain
            is_remote = False

        if dry_run:
            print(f"[DRY RUN] Would replace URLs in {target_path}")
            for protocol in ["http", "https"]:
                search_url = search_domains[protocol]
                replace_url = replace_domains[protocol]
                print(f"[DRY RUN] Would replace {search_url} with {replace_url}")
            return True

        # Perform URL replacements
        success = True
        
        # Replace HTTP URLs
        http_success = self._replace_url(
            target_path,
            search_domains["http"],
            replace_domains["http"],
            is_remote
        )
        if not http_success:
            print(f"Warning: Failed to replace HTTP URLs")
            success = False
            
        # Replace HTTPS URLs
        https_success = self._replace_url(
            target_path,
            search_domains["https"],
            replace_domains["https"],
            is_remote
        )
        if not https_success:
            print(f"Warning: Failed to replace HTTPS URLs")
            success = False
            
        # Replace domain without protocol
        domain_success = self._replace_url(
            target_path,
            search_domains["http"].replace("http://", ""),
            replace_domains["http"].replace("http://", ""),
            is_remote
        )
        if not domain_success:
            print(f"Warning: Failed to replace domain without protocol")
            success = False
            
        # Replace escaped URLs (for JSON data)
        escaped_success = self._replace_url(
            target_path,
            search_domains["https"].replace(":", "\\:").replace("/", "\\/"),
            replace_domains["https"].replace(":", "\\:").replace("/", "\\/"),
            is_remote
        )
        if not escaped_success:
            print(f"Warning: Failed to replace escaped URLs")
            success = False
            
        return success

    def _replace_url(self, path, search_url, replace_url, is_remote=False):
        """
        Replace a specific URL in the database.

        Args:
            path (str): Path to WordPress installation.
            search_url (str): URL to search for.
            replace_url (str): URL to replace with.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if replacement is successful, False otherwise.
        """
        print(f"Replacing {search_url} with {replace_url}")
        
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            cmd = f'wp --path="{path}" search-replace "{search_url}" "{replace_url}" --all-tables --allow-root'
            success, output = ssh_manager.execute_remote_command(cmd)
            
            if not success:
                print(f"Failed to replace URLs on remote server: {output}")
                return False
                
            print(output)
            return True
        else:
            try:
                cmd = f'wp --path="{path}" search-replace "{search_url}" "{replace_url}" --all-tables --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to replace URLs on local server: {result.stderr}")
                    return False
                    
                print(result.stdout)
                return True
                
            except Exception as e:
                print(f"Error replacing URLs: {e}")
                return False

    def validate_urls(self, direction, dry_run=False):
        """
        Validate URLs after replacement.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if validation is successful, False otherwise.
        """
        if dry_run:
            print(f"[DRY RUN] Would validate URLs")
            return True

        if direction == "push":
            # Validate URLs on the remote server
            target_path = self.live_path
            expected_url = self.live_domain["https"]
            is_remote = True
        else:  # pull
            # Validate URLs on the local server
            target_path = self.local_path
            expected_url = self.staging_domain["https"]
            is_remote = False

        # Check site URL
        site_url = self._get_site_url(target_path, is_remote)
        if not site_url:
            print("Failed to get site URL")
            return False
            
        # Check home URL
        home_url = self._get_home_url(target_path, is_remote)
        if not home_url:
            print("Failed to get home URL")
            return False
            
        # Validate URLs
        if expected_url not in site_url or expected_url not in home_url:
            print(f"URL validation failed:")
            print(f"  Expected URL: {expected_url}")
            print(f"  Site URL: {site_url}")
            print(f"  Home URL: {home_url}")
            return False
            
        print(f"URL validation successful:")
        print(f"  Site URL: {site_url}")
        print(f"  Home URL: {home_url}")
        return True

    def _get_site_url(self, path, is_remote=False):
        """
        Get the site URL from WordPress.

        Args:
            path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            str: Site URL, or None if retrieval failed.
        """
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            cmd = f'wp --path="{path}" option get siteurl --allow-root'
            success, output = ssh_manager.execute_remote_command(cmd)
            
            if not success:
                print(f"Failed to get site URL from remote server: {output}")
                return None
                
            return output.strip()
        else:
            try:
                cmd = f'wp --path="{path}" option get siteurl --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to get site URL from local server: {result.stderr}")
                    return None
                    
                return result.stdout.strip()
                
            except Exception as e:
                print(f"Error getting site URL: {e}")
                return None

    def _get_home_url(self, path, is_remote=False):
        """
        Get the home URL from WordPress.

        Args:
            path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            str: Home URL, or None if retrieval failed.
        """
        if is_remote:
            from resources.ssh_manager import SSHManager
            ssh_manager = SSHManager(self.config)
            
            cmd = f'wp --path="{path}" option get home --allow-root'
            success, output = ssh_manager.execute_remote_command(cmd)
            
            if not success:
                print(f"Failed to get home URL from remote server: {output}")
                return None
                
            return output.strip()
        else:
            try:
                cmd = f'wp --path="{path}" option get home --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to get home URL from local server: {result.stderr}")
                    return None
                    
                return result.stdout.strip()
                
            except Exception as e:
                print(f"Error getting home URL: {e}")
                return None
