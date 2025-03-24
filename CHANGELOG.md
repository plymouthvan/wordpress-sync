# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2025-03-24

### Added
- New trash directory functionality for safer file operations
  - Files are now moved to a temporary trash directory instead of being directly deleted
  - Added option to save or delete trashed files after operations complete
- New `--no-trash` option to skip backup of deleted/modified files entirely
- Added option to backup destination database before importing source database
- Backup management system in SSHManager

### Changed
- Enhanced database operations with timing capabilities
- Updated documentation with new command options
