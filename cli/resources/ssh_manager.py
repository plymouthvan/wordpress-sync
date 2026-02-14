#!/usr/bin/env python3
"""
SSH Manager for WordPress Sync.

This module manages SSH connections and file transfers using rsync and scp.
It handles establishing SSH connections to the server, executing remote commands,
and transferring files between local and remote servers.
"""

import os
import subprocess
import shlex
import sys
from pathlib import Path
from resources.password_manager import PasswordManager


class SSHManager:
    """Manages SSH connections and file transfers for WordPress Sync."""

    def __init__(self, config):
        """
        Initialize the SSH Manager.

        Args:
            config (dict): Configuration dictionary.
        """
        self.config = config
        self.ssh_user = config["ssh"]["user"]
        self.ssh_host = config["ssh"]["host"]
        self.ssh_key_path = config["ssh"]["key_path"]
        self.ssh_port = int(config["ssh"].get("port", 22))
        
        # Initialize sudo user properties if configured
        self.sudo_user = None
        self.sudo_key_path = None
        if "sudo" in config["ssh"]:
            if "user" in config["ssh"]["sudo"]:
                self.sudo_user = config["ssh"]["sudo"]["user"]
            if "key_path" in config["ssh"]["sudo"]:
                self.sudo_key_path = config["ssh"]["sudo"]["key_path"]
            else:
                # If no specific key is provided for sudo user, use the regular SSH key
                self.sudo_key_path = self.ssh_key_path
        
        self.local_path = config["paths"]["local"]
        self.live_path = config["paths"]["live"]
        
        # When running non-interactively (e.g. from a GUI), use BatchMode
        # so SSH/SCP fail fast instead of hanging waiting for a passphrase.
        self.non_interactive = config.get("_non_interactive", False)
        
        self.rsync_options = self._build_rsync_options()
        self.password_manager = PasswordManager()

    def _build_rsync_options(self):
        """
        Build rsync options from configuration.

        Returns:
            list: List of rsync options.
        """
        options = []

        # Basic options
        options.append("-avz")  # Archive mode, verbose, compress

        # Progress
        if self.config["rsync"].get("progress", True):
            options.append("--progress")
            # Add info=progress2 for better progress reporting
            options.append("--info=progress2")

        # Delete
        if self.config["rsync"].get("delete", True):
            options.extend(["--delete", "--delete-after"])

        # Verbose
        if self.config["rsync"].get("verbose", True):
            options.append("--verbose")

        # Compress
        if not self.config["rsync"].get("compress", True):
            options.remove("-avz")
            options.append("-av")

        # File permissions
        chmod_files = self.config["rsync"].get("chmod_files", "664")
        chmod_dirs = self.config["rsync"].get("chmod_dirs", "775")
        options.append(f"--chmod=F{chmod_files},D{chmod_dirs}")

        # Backup options - only add if not explicitly disabled
        if not self.config.get("no_trash", False):
            # Get the backup directory path
            backup_dir = self._get_backup_dir(self.config)
            if backup_dir:
                options.append("--backup")
                options.append(f"--backup-dir={backup_dir}")

        # Excludes
        excludes = self.config["rsync"].get("excludes", [])
        for exclude in excludes:
            options.append(f"--exclude={exclude}")
        
        # Ensure rsync uses the specified SSH key and port
        remote_shell = f"ssh -i {self.ssh_key_path} -p {self.ssh_port}"
        if self.non_interactive:
            remote_shell += " -o BatchMode=yes -o ConnectTimeout=30"
        options.extend(["-e", remote_shell])
        
        # Add --itemize-changes if requested (runtime flag from CLI)
        if self.config.get("_itemize_changes", False):
            options.append("--itemize-changes")
        
        # Append any extra rsync args passed via CLI (runtime flag)
        extra_args = self.config.get("_extra_rsync_args", "")
        if extra_args:
            options.extend(shlex.split(extra_args))
        
        return options

    def test_connection(self):
        """
        Test SSH connection to the server.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            cmd = [
                "ssh",
                "-i", self.ssh_key_path,
                "-p", str(self.ssh_port),
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=5",
                f"{self.ssh_user}@{self.ssh_host}",
                "echo 'Connection successful'"
            ]
            
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                print(f"SSH connection test failed: {result.stderr}")
                return False
                
            return True
            
        except Exception as e:
            print(f"Error testing SSH connection: {e}")
            return False

    def execute_remote_command(self, command, dry_run=False, sudo_password=None, command_collector=None):
        """
        Execute a command on the remote server.

        Args:
            command (str): Command to execute.
            dry_run (bool): If True, only print the command without executing.
            sudo_password (str, optional): Password for sudo commands if needed.
            command_collector (CommandCollector, optional): Collector for command-only mode.

        Returns:
            tuple: (success, output) where success is a boolean and output is the command output.
        """
        # Check if the command contains sudo
        is_sudo_command = command.strip().startswith("sudo")
        
        # Add to command collector if provided
        if command_collector:
            if is_sudo_command and sudo_password:
                # For sudo commands with password, show a sanitized version
                sudo_cmd = command.replace("sudo ", "sudo -S ")
                ssh_cmd = f"echo \"PASSWORD\" | ssh -i {self.ssh_key_path} -p {self.ssh_port} {self.ssh_user}@{self.ssh_host} \"{sudo_cmd}\""
                command_collector.add_command(
                    ssh_cmd,
                    f"Execute sudo command with password: {command}",
                    "remote"
                )
            else:
                # Standard SSH command
                ssh_cmd = f"ssh -i {self.ssh_key_path} -p {self.ssh_port} {self.ssh_user}@{self.ssh_host} '{command}'"
                command_collector.add_command(
                    ssh_cmd,
                    f"Execute remote command: {command}",
                    "remote"
                )
            return True, "[COMMAND ONLY] Command execution simulated"
            
        if dry_run:
            print(f"[DRY RUN] Would execute remote command: {command}")
            return True, "[DRY RUN] Command execution simulated"

        try:
            # If it's a sudo command and we have a password, use a different approach
            if is_sudo_command and sudo_password:
                # Use sshpass if sudo password is provided
                print(f"Executing sudo command with password...")
                
                # Modify the sudo command to use -S option to read password from stdin
                sudo_cmd = command.replace("sudo ", "sudo -S ")
                
                # Create a full command that pipes the password to sudo
                batch_opt = " -o BatchMode=yes" if self.non_interactive else ""
                full_cmd = f'echo "{sudo_password}" | ssh -i {self.ssh_key_path} -p {self.ssh_port}{batch_opt} {self.ssh_user}@{self.ssh_host} "{sudo_cmd}"'
                
                # Execute the command using shell=True to handle the pipe
                result = subprocess.run(
                    full_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    shell=True
                )
                
                if result.returncode != 0:
                    print(f"Remote sudo command failed: {result.stderr}")
                    return False, result.stderr
                    
                return True, result.stdout
            
            # Standard SSH command execution
            cmd = [
                "ssh",
                "-i", self.ssh_key_path,
                "-p", str(self.ssh_port),
            ]
            
            # In non-interactive mode, fail fast instead of prompting for passphrase
            if self.non_interactive:
                cmd.extend(["-o", "BatchMode=yes", "-o", "ConnectTimeout=30"])
            
            # Add -t flag for pseudo-terminal allocation if it's a sudo command
            if is_sudo_command:
                cmd.append("-t")
                # Modify the sudo command to use -S option to read password from stdin if needed
                command = command.replace("sudo ", "sudo -S ")
            
            cmd.extend([
                f"{self.ssh_user}@{self.ssh_host}",
                command
            ])
            
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                print(f"Remote command failed: {result.stderr}")
                return False, result.stderr
                
            return True, result.stdout
            
        except Exception as e:
            print(f"Error executing remote command: {e}")
            return False, str(e)
            
    def execute_as_sudo_user(self, command, dry_run=False, command_collector=None, sudo_password=None):
        """
        Execute a command on the remote server as the sudo user.
        
        This method is used when a separate sudo user is configured in the config file.
        It will connect to the server as the sudo user directly, rather than using
        the regular user with sudo privileges.

        Args:
            command (str): Command to execute.
            dry_run (bool): If True, only print the command without executing.
            command_collector (CommandCollector, optional): Collector for command-only mode.
            sudo_password (str, optional): Password for sudo commands if needed.

        Returns:
            tuple: (success, output) where success is a boolean and output is the command output.
        """
        if not self.sudo_user:
            # If no sudo user is configured, fall back to regular user with sudo
            return self.execute_remote_command(f"sudo {command}", dry_run, sudo_password, command_collector)
            
        # Add to command collector if provided
        if command_collector:
            # For command collector mode, always show the command without sudo
            ssh_cmd = f"ssh -i {self.sudo_key_path} -p {self.ssh_port} {self.sudo_user}@{self.ssh_host} '{command}'"
            command_collector.add_command(
                ssh_cmd,
                f"Execute as sudo user '{self.sudo_user}': {command}",
                "remote"
            )
            return True, "[COMMAND ONLY] Command execution simulated"
            
        if dry_run:
            print(f"[DRY RUN] Would execute command as sudo user {self.sudo_user}: {command}")
            return True, "[DRY RUN] Command execution simulated"

        # First try to execute the command directly (without sudo)
        try:
            print(f"Executing command as sudo user {self.sudo_user}...")
            
            # Build SSH command to execute as sudo user
            cmd = [
                "ssh",
                "-i", self.sudo_key_path,
                "-p", str(self.ssh_port),
                f"{self.sudo_user}@{self.ssh_host}",
                command
            ]
            
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # Command failed, it might need sudo
                print(f"Direct command execution as sudo user failed: {result.stderr}")
                print(f"Trying with sudo for user {self.sudo_user}...")
                
                # Check if sudo requires password
                if not sudo_password:
                    # First try without password (in case NOPASSWD sudo is configured)
                    check_cmd = "sudo -n true 2>/dev/null && echo 'NOPASSWD' || echo 'PASSWORD'"
                    check_result = subprocess.run(
                        ["ssh", "-i", self.sudo_key_path, "-p", str(self.ssh_port), f"{self.sudo_user}@{self.ssh_host}", check_cmd],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if check_result.returncode == 0 and "NOPASSWD" in check_result.stdout:
                        print(f"NOPASSWD sudo is available for user {self.sudo_user}.")
                    else:
                        print(f"Sudo password required for user {self.sudo_user}. Please enter it below.")
                        sudo_password = self.password_manager.get_sudo_password()
                        if not sudo_password:
                            print("No password provided. Cannot proceed.")
                            return False, "No password provided"
                
                # Try with sudo
                if sudo_password:
                    # Use sudo with password
                    sudo_cmd = f"sudo -S {command}"
                    full_cmd = f'echo "{sudo_password}" | ssh -i {self.sudo_key_path} -p {self.ssh_port} {self.sudo_user}@{self.ssh_host} "{sudo_cmd}"'
                    
                    sudo_result = subprocess.run(
                        full_cmd,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                        shell=True
                    )
                else:
                    # Use sudo without password
                    sudo_cmd = f"sudo {command}"
                    sudo_result = subprocess.run(
                        ["ssh", "-i", self.sudo_key_path, "-p", str(self.ssh_port), f"{self.sudo_user}@{self.ssh_host}", sudo_cmd],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                
                if sudo_result.returncode != 0:
                    print(f"Sudo command execution as sudo user failed: {sudo_result.stderr}")
                    
                    # Fall back to regular user with sudo as a last resort
                    print("Falling back to regular user with sudo...")
                    return self.execute_remote_command(f"sudo {command}", dry_run, sudo_password, command_collector)
                
                return True, sudo_result.stdout
            
            return True, result.stdout
            
        except Exception as e:
            print(f"Error executing command as sudo user: {e}")
            
            # Fall back to regular user with sudo on exception
            print("Falling back to regular user with sudo due to error...")
            return self.execute_remote_command(f"sudo {command}", dry_run, sudo_password, command_collector)

    def _get_backup_dir(self, config):
        """
        Get the backup directory path based on configuration and direction.
        
        Returns:
            str: Path to the backup directory, or None if backup is disabled.
        """
        # Check if backup is configured
        if "backup" not in config or not config["backup"].get("enabled", True):
            return None
            
        # Get the backup directory from config or use default
        backup_dir = config["backup"].get("directory", "../.trash")
        
        # Determine the base path based on direction
        if hasattr(self, 'direction') and self.direction:
            base_path = self.live_path if self.direction == "push" else self.local_path
        else:
            # If direction is not set yet, we'll determine it later
            base_path = None
            
        # If base_path is available, resolve the backup directory path
        if base_path:
            # If backup_dir is relative, make it relative to the base path
            if not os.path.isabs(backup_dir):
                backup_dir = os.path.normpath(os.path.join(os.path.dirname(base_path), backup_dir))
                
        return backup_dir
        
    def _ensure_backup_dir_exists(self, direction):
        """
        Ensure the backup directory exists.
        
        Args:
            direction (str): Direction of transfer ('push' or 'pull').
            
        Returns:
            bool: True if successful, False otherwise.
        """
        backup_dir = self._get_backup_dir(self.config)
        if not backup_dir:
            return True  # Backup is disabled, nothing to do
            
        try:
            print(f"Ensuring backup directory exists: {backup_dir}")
            
            if direction == "push":
                # For push, the backup directory is on the remote server
                # First check if the directory exists
                check_cmd = f"test -d {backup_dir} && echo 'EXISTS' || echo 'NOT_EXISTS'"
                success, output = self.execute_remote_command(check_cmd)
                
                if not success:
                    print(f"Failed to check if backup directory exists: {output}")
                    return False
                    
                if "EXISTS" not in output:
                    # Directory doesn't exist, create it
                    mkdir_cmd = f"mkdir -p {backup_dir}"
                    success, output = self.execute_remote_command(mkdir_cmd)
                    
                    if not success:
                        print(f"Failed to create backup directory: {output}")
                        return False
                        
                    print(f"Created backup directory on remote server: {backup_dir}")
            else:
                # For pull, the backup directory is on the local system
                if not os.path.exists(backup_dir):
                    os.makedirs(backup_dir, exist_ok=True)
                    print(f"Created backup directory on local system: {backup_dir}")
                    
            return True
            
        except Exception as e:
            print(f"Error ensuring backup directory exists: {e}")
            return False

    def transfer_files(self, direction, dry_run=False, sudo_password=None, command_collector=None):
        """
        Transfer files between local and remote servers using rsync.

        Args:
            direction (str): Direction of transfer ('push' or 'pull').
            dry_run (bool): If True, perform a dry run without making changes.
            sudo_password (str, optional): Password for sudo commands if needed.

        Returns:
            bool: True if transfer is successful, False otherwise.
        """
        try:
            # Store the direction for use in other methods
            self.direction = direction
            
            # Clean up files at destination before sync
            if not dry_run:
                self._cleanup_destination_files(direction, sudo_password=sudo_password)
                
            # Ensure backup directory exists if backup is enabled
            if not self.config.get("no_trash", False) and not dry_run:
                self._ensure_backup_dir_exists(direction)
            
            # Build rsync command
            rsync_cmd = ["rsync"]
            
            # Add options
            rsync_cmd.extend(self.rsync_options)
            
            # Add dry run flag if needed
            # The dry_run parameter passed to this method takes precedence over the config
            # This ensures that when the main script sets dry_run=False after user confirmation,
            # the actual transfer will happen regardless of the config setting
            if dry_run:
                rsync_cmd.append("--dry-run")
                
            # Set source and destination based on direction
            # Ensure paths end with trailing slash for proper rsync directory handling
            local_path = self.local_path if self.local_path.endswith('/') else f"{self.local_path}/"
            live_path = self.live_path if self.live_path.endswith('/') else f"{self.live_path}/"
            
            if direction == "push":
                source = local_path
                dest = f"{self.ssh_user}@{self.ssh_host}:{live_path}"
            else:  # pull
                source = f"{self.ssh_user}@{self.ssh_host}:{live_path}"
                dest = local_path
                
            # Add source and destination to command
            rsync_cmd.append(source)
            rsync_cmd.append(dest)
            
            # Add to command collector if provided
            if command_collector:
                rsync_cmd_str = ' '.join(shlex.quote(arg) for arg in rsync_cmd)
                command_collector.add_command(
                    rsync_cmd_str,
                    f"Transfer files {'from local to remote' if direction == 'push' else 'from remote to local'}",
                    "both"
                )
                return True
            
            # Execute rsync command with real-time output streaming
            print(f"Executing: {' '.join(rsync_cmd)}")
            
            # Use Popen to stream output in real-time
            process = subprocess.Popen(
                rsync_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Stream stdout and stderr in real-time
            stdout_lines = []
            stderr_lines = []
            
            # Function to handle output streams
            def process_stream(stream, lines_list):
                for line in iter(stream.readline, ''):
                    if not line:
                        break
                    print(line.rstrip())
                    lines_list.append(line)
            
            # Process stdout and stderr
            import threading
            stdout_thread = threading.Thread(target=process_stream, args=(process.stdout, stdout_lines))
            stderr_thread = threading.Thread(target=process_stream, args=(process.stderr, stderr_lines))
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            return_code = process.wait()
            
            # Wait for threads to complete
            stdout_thread.join()
            stderr_thread.join()
            
            # Close file descriptors
            process.stdout.close()
            process.stderr.close()
            
            if return_code != 0:
                stderr_output = ''.join(stderr_lines)
                print(f"File transfer failed: {stderr_output}")
                return False
                
            return True
            
        except Exception as e:
            print(f"Error transferring files: {e}")
            return False

    def set_permissions(self, sudo_password=None, command_collector=None):
        """
        Set file permissions on the remote server.

        Args:
            sudo_password (str, optional): Password for sudo commands if needed.

        Returns:
            bool: True if permissions are set successfully, False otherwise.
        """
        if "ownership" not in self.config:
            print("Skipping permission setting: No ownership configuration found.")
            return True
            
        try:
            user = self.config["ownership"]["user"]
            group = self.config["ownership"]["group"]
            
            print("Setting file permissions on remote server...")
            
            # Check if we have a dedicated sudo user configured
            if self.sudo_user:
                print(f"Using dedicated sudo user '{self.sudo_user}' for permission operations...")
                
                # Set ownership
                print("Setting ownership...")
                chown_cmd = f"chown -R {user}:{group} {self.live_path}"
                success, output = self.execute_as_sudo_user(chown_cmd, command_collector=command_collector, sudo_password=sudo_password)
                if not success and not command_collector:
                    print(f"Failed to set ownership: {output}")
                    return False
                
                # Set directory permissions
                print("Setting directory permissions...")
                chmod_dirs_cmd = f"find {self.live_path} -type d -exec chmod 755 {{}} \\;"
                success, output = self.execute_as_sudo_user(chmod_dirs_cmd, command_collector=command_collector, sudo_password=sudo_password)
                if not success and not command_collector:
                    print(f"Failed to set directory permissions: {output}")
                    return False
                    
                # Set file permissions
                print("Setting file permissions...")
                chmod_files_cmd = f"find {self.live_path} -type f -exec chmod 644 {{}} \\;"
                success, output = self.execute_as_sudo_user(chmod_files_cmd, command_collector=command_collector, sudo_password=sudo_password)
                if not success and not command_collector:
                    print(f"Failed to set file permissions: {output}")
                    return False
                
            else:
                # No dedicated sudo user, use regular user with sudo
                # If sudo_password is not provided, try to prompt for it
                if not sudo_password:
                    # First try without password (in case NOPASSWD sudo is configured)
                    print("Checking if sudo password is required...")
                    check_cmd = "sudo -n true 2>/dev/null && echo 'NOPASSWD' || echo 'PASSWORD'"
                    success, check_output = self.execute_remote_command(check_cmd)
                    
                    if success and "NOPASSWD" in check_output:
                        print("NOPASSWD sudo is available, no password needed.")
                    else:
                        print("Sudo password required. Please enter it below.")
                        sudo_password = self.password_manager.get_sudo_password()
                        if not sudo_password:
                            print("No password provided. Cannot proceed.")
                            print("You can also configure NOPASSWD sudo by adding this line to /etc/sudoers using visudo:")
                            print(f"{self.ssh_user} ALL=(ALL) NOPASSWD: ALL")
                            return False
                
                # Set ownership
                print("Setting ownership...")
                chown_cmd = f"sudo chown -R {user}:{group} {self.live_path}"
                success, output = self.execute_remote_command(chown_cmd, sudo_password=sudo_password)
                if not success:
                    print(f"Failed to set ownership: {output}")
                    return False
                
                # Set directory permissions
                print("Setting directory permissions...")
                chmod_dirs_cmd = f"sudo find {self.live_path} -type d -exec chmod 755 {{}} \\;"
                success, output = self.execute_remote_command(chmod_dirs_cmd, sudo_password=sudo_password)
                if not success:
                    print(f"Failed to set directory permissions: {output}")
                    return False
                    
                # Set file permissions
                print("Setting file permissions...")
                chmod_files_cmd = f"sudo find {self.live_path} -type f -exec chmod 644 {{}} \\;"
                success, output = self.execute_remote_command(chmod_files_cmd, sudo_password=sudo_password)
                if not success:
                    print(f"Failed to set file permissions: {output}")
                    return False
            
            print("File permissions set successfully.")
            return True
            
        except Exception as e:
            print(f"Error setting permissions: {e}")
            return False

    def _cleanup_destination_files(self, direction, sudo_password=None, command_collector=None):
        """
        Clean up specified files from the destination before sync.
        
        This helps ensure that directories can be properly deleted by rsync
        by removing files that are excluded from transfer but should be
        deleted from the destination.
        
        Args:
            direction (str): Direction of transfer ('push' or 'pull').
            sudo_password (str, optional): Password for sudo commands if needed.
            
        Returns:
            bool: True if cleanup is successful, False otherwise.
        """
        # Check if cleanup_files is defined in config
        cleanup_files = self.config["rsync"].get("cleanup_files", [])
        if not cleanup_files:
            return True
            
        try:
            print("Cleaning up destination files before sync...")
            
            # Determine destination path based on direction
            if direction == "push":
                # Destination is remote
                for file_pattern in cleanup_files:
                    print(f"Cleaning up {file_pattern} files on remote server...")
                    # Use find to locate and delete files matching the pattern
                    # Check if we have permission to delete files directly
                    test_cmd = f"test -w {self.live_path} && echo 'WRITABLE' || echo 'NOT_WRITABLE'"
                    success, test_output = self.execute_remote_command(test_cmd)
                    
                    # Check if we have a dedicated sudo user configured
                    if self.sudo_user:
                        print(f"Using dedicated sudo user '{self.sudo_user}' for cleanup...")
                        cmd = f"find {self.live_path} -name '{file_pattern}' -type f -delete"
                        success, output = self.execute_as_sudo_user(cmd, sudo_password=sudo_password, command_collector=command_collector)
                    elif success and "WRITABLE" in test_output:
                        # We have write permission, use regular find command
                        cmd = f"find {self.live_path} -name '{file_pattern}' -type f -delete"
                        success, output = self.execute_remote_command(cmd)
                    else:
                        # We don't have write permission, use sudo with regular user
                        if not sudo_password:
                            # Try to check if NOPASSWD sudo is available
                            check_cmd = "sudo -n true 2>/dev/null && echo 'NOPASSWD' || echo 'PASSWORD'"
                            success, check_output = self.execute_remote_command(check_cmd)
                            
                            if not (success and "NOPASSWD" in check_output):
                                # Need password - prompt for it
                                print("Sudo password required for cleanup. Please enter it below.")
                                sudo_password = self.password_manager.get_sudo_password()
                                if not sudo_password:
                                    print("No password provided. Skipping cleanup.")
                                    continue
                        
                        cmd = f"sudo find {self.live_path} -name '{file_pattern}' -type f -delete"
                        success, output = self.execute_remote_command(cmd, sudo_password=sudo_password)
                    
                    if not success:
                        print(f"Warning: Failed to clean up {file_pattern} files: {output}")
                        # Try alternative approach if sudo failed
                        if "sudo" in cmd:
                            print("Trying alternative approach without sudo...")
                            alt_cmd = f"find {self.live_path} -name '{file_pattern}' -type f -print0 | xargs -0 rm -f 2>/dev/null || true"
                            self.execute_remote_command(alt_cmd)
            else:
                # Destination is local
                for file_pattern in cleanup_files:
                    print(f"Cleaning up {file_pattern} files on local system...")
                    # Use find to locate and delete files matching the pattern
                    cmd = f"find {self.local_path} -name '{file_pattern}' -type f -delete"
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
                        print(f"Warning: Failed to clean up {file_pattern} files: {result.stderr}")
                        
            return True
            
        except Exception as e:
            print(f"Error during pre-sync cleanup: {e}")
            return False
            
    def transfer_file(self, source_path, dest_path, direction, dry_run=False, command_collector=None):
        """
        Transfer a single file between local and remote servers using scp.

        Args:
            source_path (str): Source file path.
            dest_path (str): Destination file path.
            direction (str): Direction of transfer ('push' or 'pull').
            dry_run (bool): If True, only print the command without executing.

        Returns:
            bool: True if transfer is successful, False otherwise.
        """
        if dry_run:
            print(f"[DRY RUN] Would transfer file from {source_path} to {dest_path}")
            return True

        try:
            # Build scp command
            scp_cmd = ["scp", "-i", self.ssh_key_path, "-P", str(self.ssh_port)]
            if self.non_interactive:
                scp_cmd.extend(["-o", "BatchMode=yes", "-o", "ConnectTimeout=30"])
            
            # Set source and destination based on direction
            if direction == "push":
                source = source_path
                dest = f"{self.ssh_user}@{self.ssh_host}:{dest_path}"
            else:  # pull
                source = f"{self.ssh_user}@{self.ssh_host}:{source_path}"
                dest = dest_path
                
            # Add source and destination to command
            scp_cmd.append(source)
            scp_cmd.append(dest)
            
            # Add to command collector if provided
            if command_collector:
                scp_cmd_str = ' '.join(scp_cmd)
                command_collector.add_command(
                    scp_cmd_str,
                    f"Transfer single file {'to remote' if direction == 'push' else 'from remote'}: {source_path} to {dest_path}",
                    "both"
                )
                return True
            
            # Execute scp command
            print(f"Executing: {' '.join(scp_cmd)}")
            result = subprocess.run(
                scp_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                print(f"File transfer failed: {result.stderr}")
                return False
                
            return True
            
        except Exception as e:
            print(f"Error transferring file: {e}")
            return False
