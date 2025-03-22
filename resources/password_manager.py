#!/usr/bin/env python3
"""
Password Manager for WordPress Sync.

This module handles secure password input and caching for the synchronization tool.
It provides a way to securely prompt for passwords when needed and cache them
for the duration of the session.
"""

from getpass import getpass


class PasswordManager:
    """Manages password input and caching for WordPress Sync."""

    def __init__(self):
        """Initialize the Password Manager."""
        self._sudo_password = None
    
    def get_sudo_password(self, force_prompt=False):
        """
        Get sudo password, prompting user if necessary.
        
        Args:
            force_prompt (bool): If True, always prompt even if password is cached
            
        Returns:
            str: The sudo password, or None if user cancelled
        """
        if not force_prompt and self._sudo_password:
            return self._sudo_password
            
        try:
            self._sudo_password = getpass("Enter sudo password: ")
            return self._sudo_password
        except (KeyboardInterrupt, EOFError):
            print("\nPassword input cancelled")
            return None
