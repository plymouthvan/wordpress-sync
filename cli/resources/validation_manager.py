#!/usr/bin/env python3
"""
Validation Manager for WordPress Sync.

This module performs validation checks after synchronization to ensure everything
is functioning correctly, including core files, database, and accessibility.
"""

import os
import subprocess
import sys
import requests
import warnings
from pathlib import Path
from urllib3.exceptions import InsecureRequestWarning

# Suppress InsecureRequestWarning for validation checks
warnings.simplefilter('ignore', InsecureRequestWarning)


class ValidationManager:
    """Manages validation checks for WordPress Sync."""

    def __init__(self, config):
        """
        Initialize the Validation Manager.

        Args:
            config (dict): Configuration dictionary.
        """
        self.config = config
        self.local_path = config["paths"]["local"]
        self.live_path = config["paths"]["live"]
        self.validation_config = config.get("validation", {})
        
        # Default validation settings if not specified
        if not self.validation_config:
            self.validation_config = {
                "enabled": True,
                "checks": {
                    "core_files": {
                        "enabled": True,
                        "verify_checksums": True,
                        "critical_files": [
                            "wp-config.php",
                            "wp-content/index.php",
                            ".htaccess"
                        ]
                    },
                    "database": {
                        "enabled": True,
                        "verify_core_tables": True,
                        "additional_tables": []
                    },
                    "accessibility": {
                        "homepage": True,
                        "wp_admin": True
                    }
                }
            }

    def run_validation_checks(self, direction, skip_files=False, skip_db=False):
        """
        Run all validation checks based on configuration and synchronization type.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            skip_files (bool): Skip file-related validation checks.
            skip_db (bool): Skip database-related validation checks.

        Returns:
            bool: True if all checks pass, False otherwise.
        """
        if not self.validation_config.get("enabled", True):
            print("Validation checks are disabled in configuration")
            return True

        # Determine target environment
        if direction == "push":
            target_path = self.live_path
            is_remote = True
            target_domain = self.config["domains"]["live"]["https"]
        else:  # pull
            target_path = self.local_path
            is_remote = False
            target_domain = self.config["domains"]["staging"]["https"]

        sync_type = []
        if skip_files:
            sync_type.append("database-only")
        elif skip_db:
            sync_type.append("files-only")
        else:
            sync_type.append("full")
            
        print(f"Running {sync_type[0]} validation checks on {'remote' if is_remote else 'local'} environment...")
        
        all_checks_passed = True
        
        # Core files validation - skip if db_only
        if not skip_files and self.validation_config.get("checks", {}).get("core_files", {}).get("enabled", True):
            print("Validating core files...")
            core_files_passed = self.validate_core_files(target_path, is_remote)
            if not core_files_passed:
                print("Core files validation failed")
                all_checks_passed = False
            else:
                print("Core files validation passed")
        elif skip_files:
            print("Skipping core files validation (database-only synchronization)")
                
        # Database validation - skip if files_only
        if not skip_db and self.validation_config.get("checks", {}).get("database", {}).get("enabled", True):
            print("Validating database...")
            database_passed = self.validate_database(target_path, is_remote)
            if not database_passed:
                print("Database validation failed")
                all_checks_passed = False
            else:
                print("Database validation passed")
        elif skip_db:
            print("Skipping database validation (files-only synchronization)")
                
        # Accessibility validation - always run this
        if self.validation_config.get("checks", {}).get("accessibility", {}).get("homepage", True) or \
           self.validation_config.get("checks", {}).get("accessibility", {}).get("wp_admin", True):
            print("Validating site accessibility...")
            accessibility_passed = self.validate_accessibility(target_domain)
            if not accessibility_passed:
                print("Accessibility validation failed")
                all_checks_passed = False
            else:
                print("Accessibility validation passed")
                
        return all_checks_passed

    def validate_core_files(self, target_path, is_remote=False):
        """
        Validate WordPress core files.

        Args:
            target_path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if validation passes, False otherwise.
        """
        validation_passed = True
        
        # Verify WordPress core checksums
        if self.validation_config.get("checks", {}).get("core_files", {}).get("verify_checksums", True):
            checksums_passed = self._verify_core_checksums(target_path, is_remote)
            if not checksums_passed:
                print("WordPress core checksums verification failed")
                validation_passed = False
                
        # Verify critical files exist
        critical_files = self.validation_config.get("checks", {}).get("core_files", {}).get("critical_files", [])
        if critical_files:
            files_passed = self._verify_critical_files(target_path, critical_files, is_remote)
            if not files_passed:
                print("Critical files verification failed")
                validation_passed = False
                
        return validation_passed

    def _verify_core_checksums(self, path, is_remote=False):
        """
        Verify WordPress core checksums.

        Args:
            path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if checksums match, False otherwise.
        """
        try:
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                cmd = f'wp --path="{path}" core verify-checksums --allow-root'
                success, output = ssh_manager.execute_remote_command(cmd)
                
                if not success:
                    print(f"Failed to verify core checksums on remote server: {output}")
                    return False
                    
                return "success" in output.lower() or "all checksums match" in output.lower()
            else:
                cmd = f'wp --path="{path}" core verify-checksums --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to verify core checksums on local server: {result.stderr}")
                    return False
                    
                return "success" in result.stdout.lower() or "all checksums match" in result.stdout.lower()
                
        except Exception as e:
            print(f"Error verifying core checksums: {e}")
            return False

    def _verify_critical_files(self, path, critical_files, is_remote=False):
        """
        Verify critical files exist.

        Args:
            path (str): Path to WordPress installation.
            critical_files (list): List of critical files to check.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if all critical files exist, False otherwise.
        """
        all_files_exist = True
        
        for file in critical_files:
            file_path = os.path.join(path, file)
            
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                cmd = f'test -f "{file_path}" && echo "exists" || echo "not found"'
                success, output = ssh_manager.execute_remote_command(cmd)
                
                if not success or "not found" in output:
                    print(f"Critical file not found on remote server: {file}")
                    all_files_exist = False
            else:
                if not os.path.isfile(file_path):
                    print(f"Critical file not found on local server: {file}")
                    all_files_exist = False
                    
        return all_files_exist

    def validate_database(self, target_path, is_remote=False):
        """
        Validate WordPress database.

        Args:
            target_path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if validation passes, False otherwise.
        """
        validation_passed = True
        
        # Verify core tables
        if self.validation_config.get("checks", {}).get("database", {}).get("verify_core_tables", True):
            tables_passed = self._verify_core_tables(target_path, is_remote)
            if not tables_passed:
                print("WordPress core tables verification failed")
                validation_passed = False
                
        # Verify additional tables
        additional_tables = self.validation_config.get("checks", {}).get("database", {}).get("additional_tables", [])
        if additional_tables:
            additional_passed = self._verify_additional_tables(target_path, additional_tables, is_remote)
            if not additional_passed:
                print("Additional tables verification failed")
                validation_passed = False
                
        return validation_passed

    def _verify_core_tables(self, path, is_remote=False):
        """
        Verify WordPress core tables exist.

        Args:
            path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if all core tables exist, False otherwise.
        """
        try:
            # Core WordPress tables to check
            core_tables = [
                "wp_commentmeta",
                "wp_comments",
                "wp_links",
                "wp_options",
                "wp_postmeta",
                "wp_posts",
                "wp_terms",
                "wp_term_relationships",
                "wp_term_taxonomy",
                "wp_usermeta",
                "wp_users"
            ]
            
            # Get table prefix
            prefix = self._get_table_prefix(path, is_remote)
            if not prefix:
                print("Failed to get table prefix")
                return False
                
            # Replace 'wp_' with actual prefix
            core_tables = [table.replace("wp_", prefix) for table in core_tables]
            
            # Check if tables exist
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                cmd = f'wp --path="{path}" db tables --allow-root'
                success, output = ssh_manager.execute_remote_command(cmd)
                
                if not success:
                    print(f"Failed to get database tables on remote server: {output}")
                    return False
                    
                existing_tables = output.strip().split("\n")
            else:
                cmd = f'wp --path="{path}" db tables --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to get database tables on local server: {result.stderr}")
                    return False
                    
                existing_tables = result.stdout.strip().split("\n")
                
            # Check if all core tables exist
            missing_tables = [table for table in core_tables if table not in existing_tables]
            if missing_tables:
                print(f"Missing core tables: {', '.join(missing_tables)}")
                return False
                
            return True
            
        except Exception as e:
            print(f"Error verifying core tables: {e}")
            return False

    def _get_table_prefix(self, path, is_remote=False):
        """
        Get WordPress database table prefix.

        Args:
            path (str): Path to WordPress installation.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            str: Table prefix, or None if retrieval failed.
        """
        try:
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                cmd = f'wp --path="{path}" config get table_prefix --allow-root'
                success, output = ssh_manager.execute_remote_command(cmd)
                
                if not success:
                    print(f"Failed to get table prefix on remote server: {output}")
                    return None
                    
                return output.strip()
            else:
                cmd = f'wp --path="{path}" config get table_prefix --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to get table prefix on local server: {result.stderr}")
                    return None
                    
                return result.stdout.strip()
                
        except Exception as e:
            print(f"Error getting table prefix: {e}")
            return None

    def _verify_additional_tables(self, path, additional_tables, is_remote=False):
        """
        Verify additional tables exist.

        Args:
            path (str): Path to WordPress installation.
            additional_tables (list): List of additional tables to check.
            is_remote (bool): Whether the path is on a remote server.

        Returns:
            bool: True if all additional tables exist, False otherwise.
        """
        try:
            # Get table prefix
            prefix = self._get_table_prefix(path, is_remote)
            if not prefix:
                print("Failed to get table prefix")
                return False
                
            # Replace 'wp_' with actual prefix if needed
            tables_to_check = [table.replace("wp_", prefix) if table.startswith("wp_") else table for table in additional_tables]
            
            # Check if tables exist
            if is_remote:
                from resources.ssh_manager import SSHManager
                ssh_manager = SSHManager(self.config)
                
                cmd = f'wp --path="{path}" db tables --allow-root'
                success, output = ssh_manager.execute_remote_command(cmd)
                
                if not success:
                    print(f"Failed to get database tables on remote server: {output}")
                    return False
                    
                existing_tables = output.strip().split("\n")
            else:
                cmd = f'wp --path="{path}" db tables --allow-root'
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Failed to get database tables on local server: {result.stderr}")
                    return False
                    
                existing_tables = result.stdout.strip().split("\n")
                
            # Check if all additional tables exist
            missing_tables = [table for table in tables_to_check if table not in existing_tables]
            if missing_tables:
                print(f"Missing additional tables: {', '.join(missing_tables)}")
                return False
                
            return True
            
        except Exception as e:
            print(f"Error verifying additional tables: {e}")
            return False

    def validate_accessibility(self, target_domain):
        """
        Validate site accessibility.

        Args:
            target_domain (str): Target domain to check.

        Returns:
            bool: True if validation passes, False otherwise.
        """
        validation_passed = True
        
        # Check homepage
        if self.validation_config.get("checks", {}).get("accessibility", {}).get("homepage", True):
            homepage_passed = self._check_url_accessibility(target_domain)
            if not homepage_passed:
                print(f"Homepage accessibility check failed: {target_domain}")
                validation_passed = False
                
        # Check wp-admin
        if self.validation_config.get("checks", {}).get("accessibility", {}).get("wp_admin", True):
            wp_admin_passed = self._check_url_accessibility(f"{target_domain}/wp-admin/")
            if not wp_admin_passed:
                print(f"WP Admin accessibility check failed: {target_domain}/wp-admin/")
                validation_passed = False
                
        return validation_passed

    def _check_url_accessibility(self, url):
        """
        Check if a URL is accessible.

        Args:
            url (str): URL to check.

        Returns:
            bool: True if URL is accessible, False otherwise.
        """
        try:
            # Disable SSL certificate verification for accessibility checks
            # For wp-admin URLs, we need to check the redirect location
            is_wp_admin = '/wp-admin/' in url
            
            # Don't follow redirects so we can check the initial response
            response = requests.get(url, timeout=10, allow_redirects=False, verify=False)
            
            # For homepage or non-admin URLs, 200 is a success
            if not is_wp_admin and response.status_code == 200:
                print(f"URL is accessible: {url}")
                return True
                
            # For wp-admin URLs, 302 is expected (redirect to login)
            if is_wp_admin and response.status_code == 302:
                # Verify it's redirecting to wp-login.php
                location = response.headers.get('location', '')
                if 'wp-login.php' in location and 'redirect_to' in location and 'wp-admin' in location:
                    print(f"WP Admin URL is properly redirecting to login: {url}")
                    return True
                else:
                    print(f"WP Admin URL is redirecting to unexpected location: {location}")
                    return False
            
            print(f"URL is not accessible: {url} (Status code: {response.status_code})")
            return False
            
        except requests.exceptions.RequestException as e:
            print(f"Error checking URL accessibility: {e}")
            return False

    def generate_validation_report(self, direction, skip_files=False, skip_db=False):
        """
        Generate a validation report.

        Args:
            direction (str): Direction of synchronization ('push' or 'pull').
            skip_files (bool): Skip file-related validation checks.
            skip_db (bool): Skip database-related validation checks.

        Returns:
            str: Validation report.
        """
        # Determine target environment
        if direction == "push":
            target_path = self.live_path
            is_remote = True
            target_domain = self.config["domains"]["live"]["https"]
        else:  # pull
            target_path = self.local_path
            is_remote = False
            target_domain = self.config["domains"]["staging"]["https"]

        report = []
        report.append("=== WordPress Synchronization Validation Report ===")
        report.append(f"Target Environment: {'Remote' if is_remote else 'Local'}")
        report.append(f"Target Path: {target_path}")
        report.append(f"Target Domain: {target_domain}")
        report.append("")
        
        # Determine synchronization type for report
        sync_type = "full"
        if skip_files:
            sync_type = "database-only"
        elif skip_db:
            sync_type = "files-only"
        
        report.append(f"Synchronization Type: {sync_type}")
        report.append("")
        
        # Core files validation - skip if db_only
        if not skip_files and self.validation_config.get("checks", {}).get("core_files", {}).get("enabled", True):
            report.append("--- Core Files Validation ---")
            
            # Verify WordPress core checksums
            if self.validation_config.get("checks", {}).get("core_files", {}).get("verify_checksums", True):
                checksums_passed = self._verify_core_checksums(target_path, is_remote)
                report.append(f"Core Checksums: {'PASS' if checksums_passed else 'FAIL'}")
                
            # Verify critical files exist
            critical_files = self.validation_config.get("checks", {}).get("core_files", {}).get("critical_files", [])
            if critical_files:
                files_passed = self._verify_critical_files(target_path, critical_files, is_remote)
                report.append(f"Critical Files: {'PASS' if files_passed else 'FAIL'}")
                
            report.append("")
        elif skip_files:
            report.append("--- Core Files Validation ---")
            report.append("Skipped (database-only synchronization)")
            report.append("")
            
        # Database validation - skip if files_only
        if not skip_db and self.validation_config.get("checks", {}).get("database", {}).get("enabled", True):
            report.append("--- Database Validation ---")
            
            # Verify core tables
            if self.validation_config.get("checks", {}).get("database", {}).get("verify_core_tables", True):
                tables_passed = self._verify_core_tables(target_path, is_remote)
                report.append(f"Core Tables: {'PASS' if tables_passed else 'FAIL'}")
                
            # Verify additional tables
            additional_tables = self.validation_config.get("checks", {}).get("database", {}).get("additional_tables", [])
            if additional_tables:
                additional_passed = self._verify_additional_tables(target_path, additional_tables, is_remote)
                report.append(f"Additional Tables: {'PASS' if additional_passed else 'FAIL'}")
                
            report.append("")
        elif skip_db:
            report.append("--- Database Validation ---")
            report.append("Skipped (files-only synchronization)")
            report.append("")
            
        # Accessibility validation
        if self.validation_config.get("checks", {}).get("accessibility", {}).get("homepage", True) or \
           self.validation_config.get("checks", {}).get("accessibility", {}).get("wp_admin", True):
            report.append("--- Accessibility Validation ---")
            
            # Check homepage
            if self.validation_config.get("checks", {}).get("accessibility", {}).get("homepage", True):
                homepage_passed = self._check_url_accessibility(target_domain)
                report.append(f"Homepage: {'PASS' if homepage_passed else 'FAIL'}")
                
            # Check wp-admin
            if self.validation_config.get("checks", {}).get("accessibility", {}).get("wp_admin", True):
                wp_admin_passed = self._check_url_accessibility(f"{target_domain}/wp-admin/")
                report.append(f"WP Admin: {'PASS' if wp_admin_passed else 'FAIL'}")
                
            report.append("")
            
        return "\n".join(report)
