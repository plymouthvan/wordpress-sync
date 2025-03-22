#!/usr/bin/env python3
"""
Command Collector for WordPress Sync.

This module collects and formats commands that would be executed during a synchronization
when the --command-only flag is used. It provides a way to see all commands that
would be run without actually executing them.
"""


class CommandCollector:
    """Collects and formats commands for WordPress Sync."""

    def __init__(self):
        """Initialize the Command Collector."""
        self.commands = []
        self.current_section = None

    def add_command(self, command, description, environment="both", user=None):
        """
        Add a command to the collection.

        Args:
            command (str): The command that would be executed.
            description (str): Description of what the command does.
            environment (str): Where the command would run ('local', 'remote', or 'both').
            user (str, optional): The user context that would execute the command.
        """
        self.commands.append({
            "section": self.current_section,
            "command": command,
            "description": description,
            "environment": environment,
            "user": user
        })

    def set_section(self, section):
        """
        Set the current section for subsequent commands.

        Args:
            section (str): The section name.
        """
        self.current_section = section

    def format_commands(self):
        """
        Format all collected commands into a readable string.

        Returns:
            str: Formatted commands with sections and descriptions.
        """
        if not self.commands:
            return "No commands would be executed."

        output = []
        output.append("\n=== WordPress Sync Commands ===\n")
        output.append("Legend:")
        output.append("  [local] - Commands that run on your local machine")
        output.append("  [remote] - Commands that run on the remote server")
        output.append("  [User] - The user context for command execution")
        output.append("  ")
        output.append("Note: All indented lines are executable commands\n")
        
        current_section = None
        current_env = None
        
        for cmd in self.commands:
            # Start a new section if needed
            if cmd["section"] != current_section:
                current_section = cmd["section"]
                output.append(f"\n=== {current_section} ===\n")
                current_env = None  # Reset environment tracking for new section
            
            # Add description with indentation
            output.append(f"# {cmd['description']}")
            
            # Format command with environment and user context
            env = cmd["environment"]
            user = cmd.get('user', '')
            
            # For comments or informational lines
            if cmd["command"].startswith("#"):
                output.append(f"{cmd['command']}")
                continue
                
            # Format the command with environment and user context
            if env != "both":
                # Add environment header if it changed
                if current_env != env:
                    output.append(f"\n{env.upper()} COMMANDS:")
                    current_env = env
                
                # Format the command with user context on one line and the command on the next
                if user:
                    output.append(f"  [{user}]")
                    output.append(f"    {cmd['command']}")
                else:
                    output.append(f"  {cmd['command']}")
            else:
                # For "both" environment commands that aren't comments
                output.append(f"{cmd['command']}")
            
            # Add a blank line after each command for better readability
            output.append("")
        
        return "\n".join(output)
