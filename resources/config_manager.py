#!/usr/bin/env python3
"""
Configuration Manager for WordPress Sync.

This module handles loading and validating configuration settings from the YAML configuration file.
It ensures all required settings are present and provides default values where appropriate.
"""

import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML module not found. Please install it using 'pip install pyyaml'.")
    sys.exit(1)


class ConfigManager:
    """Manages configuration loading and validation for WordPress Sync."""

    def __init__(self, config_path="config/config.yaml"):
        """
        Initialize the ConfigManager.

        Args:
            config_path (str): Path to the configuration file.
        """
        self.config_path = config_path
        self.config = None
        self.required_fields = {
            "ssh": ["user", "host"],
            "paths": ["local", "live", "db_temp"],
            "domains": {
                "staging": ["http", "https"],
                "live": ["http", "https"]
            }
        }

    def load_config(self):
        """
        Load and validate the configuration file.

        Returns:
            dict: The validated configuration.

        Raises:
            FileNotFoundError: If the configuration file is not found.
            ValueError: If the configuration is invalid.
        """
        # Check if config file exists
        if not os.path.isfile(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        # Load YAML configuration
        try:
            with open(self.config_path, 'r') as config_file:
                self.config = yaml.safe_load(config_file)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")

        # Validate configuration
        self._validate_config()

        # Set default values
        self._set_defaults()

        return self.config

    def _validate_config(self):
        """
        Validate the configuration to ensure all required fields are present.

        Raises:
            ValueError: If any required field is missing.
        """
        if not self.config:
            raise ValueError("Configuration is empty")

        # Check required top-level sections
        for section in self.required_fields:
            if section not in self.config:
                raise ValueError(f"Missing required section in configuration: {section}")

            # Check required fields in each section
            if isinstance(self.required_fields[section], list):
                for field in self.required_fields[section]:
                    if field not in self.config[section]:
                        raise ValueError(f"Missing required field in {section} section: {field}")
            elif isinstance(self.required_fields[section], dict):
                for subsection, fields in self.required_fields[section].items():
                    if subsection not in self.config[section]:
                        raise ValueError(f"Missing required subsection in {section}: {subsection}")
                    for field in fields:
                        if field not in self.config[section][subsection]:
                            raise ValueError(f"Missing required field in {section}.{subsection}: {field}")

        # Validate paths
        for path_key in ["local", "live"]:
            path = self.config["paths"][path_key]
            if not path.endswith('/'):
                self.config["paths"][path_key] = path + '/'

        # Validate operation direction
        if "operation" in self.config and "direction" in self.config["operation"]:
            direction = self.config["operation"]["direction"]
            if direction not in ["push", "pull"]:
                raise ValueError(f"Invalid operation direction: {direction}. Must be 'push' or 'pull'.")

        return True

    def _set_defaults(self):
        """Set default values for optional configuration fields."""
        # Default operation direction
        if "operation" not in self.config:
            self.config["operation"] = {}
        if "direction" not in self.config["operation"]:
            self.config["operation"]["direction"] = "push"

        # Default SSH key path
        if "key_path" not in self.config["ssh"]:
            self.config["ssh"]["key_path"] = os.path.expanduser("~/.ssh/id_rsa")

        # Default database filename
        if "db_filename" not in self.config["paths"]:
            self.config["paths"]["db_filename"] = "wordpress-sync-database.sql"

        # Default rsync settings
        if "rsync" not in self.config:
            self.config["rsync"] = {}
        rsync_defaults = {
            "dry_run": True,
            "delete": True,
            "progress": True,
            "verbose": True,
            "compress": True,
            "chmod_files": "664",
            "chmod_dirs": "775",
            "excludes": [".DS_Store", "wp-config.php"]
        }
        for key, value in rsync_defaults.items():
            if key not in self.config["rsync"]:
                self.config["rsync"][key] = value

        # Default validation settings
        if "validation" not in self.config:
            self.config["validation"] = {"enabled": True}
        elif "enabled" not in self.config["validation"]:
            self.config["validation"]["enabled"] = True

        # Default ownership settings
        if "ownership" not in self.config:
            if "user" in self.config["ssh"]:
                self.config["ownership"] = {
                    "user": self.config["ssh"]["user"],
                    "group": self.config["ssh"]["user"]
                }

        return self.config

    def get_source_path(self, direction):
        """
        Get the source path based on synchronization direction.

        Args:
            direction (str): Synchronization direction ('push' or 'pull').

        Returns:
            str: Source path.
        """
        return self.config["paths"]["local"] if direction == "push" else self.config["paths"]["live"]

    def get_target_path(self, direction):
        """
        Get the target path based on synchronization direction.

        Args:
            direction (str): Synchronization direction ('push' or 'pull').

        Returns:
            str: Target path.
        """
        return self.config["paths"]["live"] if direction == "push" else self.config["paths"]["local"]

    def get_source_domain(self, direction):
        """
        Get the source domain based on synchronization direction.

        Args:
            direction (str): Synchronization direction ('push' or 'pull').

        Returns:
            dict: Source domain configuration.
        """
        return self.config["domains"]["staging"] if direction == "push" else self.config["domains"]["live"]

    def get_target_domain(self, direction):
        """
        Get the target domain based on synchronization direction.

        Args:
            direction (str): Synchronization direction ('push' or 'pull').

        Returns:
            dict: Target domain configuration.
        """
        return self.config["domains"]["live"] if direction == "push" else self.config["domains"]["staging"]
