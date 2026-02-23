import { Command } from '@tauri-apps/plugin-shell';
import { resolveResource } from '@tauri-apps/api/path';
import { termExec, termInfo, termError, termSuccess, terminalOpen } from '$lib/stores/terminal';

/**
 * Common PATH prefix to ensure Homebrew, pipx, MAMP, and other non-standard
 * locations are accessible. On macOS, Tauri .app bundles inherit a minimal
 * PATH that doesn't include /usr/local/bin, /opt/homebrew/bin, etc.
 *
 * Strategy: resolve the user's login shell and source its full PATH, which
 * captures everything from .zshrc / .bash_profile (MAMP, Homebrew, pyenv, nvm,
 * etc.). Falls back to well-known directories if the login shell approach fails.
 */
export const PATH_SETUP = [
  // Resolve the user's login shell (SHELL may not be set in .app context)
  '_LOGIN_SHELL="${SHELL:-$(dscl . -read /Users/$USER UserShell 2>/dev/null | awk \'{print $2}\')}"',
  '_LOGIN_SHELL="${_LOGIN_SHELL:-/bin/zsh}"',
  // Source the full PATH from the user's login shell
  '_FULL_PATH="$($_LOGIN_SHELL -lc \'echo $PATH\' 2>/dev/null)"',
  // Use the login shell PATH if it resolved, otherwise fall back to well-known dirs
  'if [ -n "$_FULL_PATH" ]; then export PATH="$_FULL_PATH"; else export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.pyenv/bin:$HOME/Library/Python/3.12/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.10/bin:$PATH"; fi',
  // Recover SSH agent socket for .app context
  'if [ -z "$SSH_AUTH_SOCK" ]; then export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK 2>/dev/null)"; fi',
  'export PYTHONUNBUFFERED=1',
].join('; ');

/**
 * Resolve the path to the wordpress-sync CLI tool.
 * Uses `which` to locate it on the system PATH.
 */
export async function resolveCliPath(): Promise<string | null> {
  try {
    const result = await Command.create('exec-sh', [
      '-c',
      `${PATH_SETUP}; which wordpress-sync 2>/dev/null`
    ]).execute();
    if (result.code === 0 && result.stdout.trim()) {
      return result.stdout.trim();
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Locate the CLI source directory.
 * First checks the bundled resources inside the .app bundle,
 * then falls back to walking up from the binary for dev mode.
 */
export async function findCliSourceDir(): Promise<string | null> {
  // 1. Check for CLI bundled inside the .app Resources directory
  try {
    const bundledCliDir = await resolveResource('cli');
    const checkBundled = await Command.create('exec-sh', [
      '-c',
      `test -f "${bundledCliDir}/pyproject.toml" && echo "${bundledCliDir}"`
    ]).execute();
    if (checkBundled.code === 0 && checkBundled.stdout.trim()) {
      return checkBundled.stdout.trim();
    }
  } catch {
    // resolveResource may fail in dev mode; fall through
  }

  // 2. Dev-mode fallback: walk up from $PWD / binary location
  try {
    const script = `
      # Try to find the cli dir by walking up from common locations
      for base in "$PWD" "$(dirname "$(which gui 2>/dev/null)")" ; do
        dir="$base"
        for i in 1 2 3 4 5; do
          if [ -f "$dir/cli/pyproject.toml" ]; then
            echo "$dir/cli"
            exit 0
          fi
          dir="$(dirname "$dir")"
        done
      done
      # Also try from the repo root if we can find a .git directory
      dir="$PWD"
      for i in 1 2 3 4 5 6; do
        if [ -d "$dir/.git" ] && [ -f "$dir/cli/pyproject.toml" ]; then
          echo "$dir/cli"
          exit 0
        fi
        dir="$(dirname "$dir")"
      done
      exit 1
    `;
    const result = await Command.create('exec-sh', ['-c', `${PATH_SETUP}; ${script}`]).execute();
    if (result.code === 0 && result.stdout.trim()) {
      return result.stdout.trim();
    }
  } catch {
    // fall through
  }
  return null;
}

/**
 * Check which Python package manager is available.
 * Returns 'pipx', 'pip3', 'pip', or null.
 */
export async function findPythonInstaller(): Promise<{ tool: string; path: string } | null> {
  for (const tool of ['pipx', 'pip3', 'pip']) {
    try {
      const result = await Command.create('exec-sh', [
        '-c',
        `${PATH_SETUP}; which ${tool} 2>/dev/null`
      ]).execute();
      if (result.code === 0 && result.stdout.trim()) {
        return { tool, path: result.stdout.trim() };
      }
    } catch {
      // try next
    }
  }
  return null;
}

/**
 * Install the wordpress-sync CLI from the local cli/ directory.
 * Logs all output to the terminal panel.
 */
export async function installCli(): Promise<boolean> {
  terminalOpen.set(true);
  termInfo('Installing wordpress-sync CLI...');

  // Step 1: Locate the CLI source
  const cliDir = await findCliSourceDir();
  if (!cliDir) {
    termError('Could not locate the CLI source directory (cli/).');
    termError('Expected to find pyproject.toml in a sibling cli/ directory.');
    return false;
  }
  termInfo(`Found CLI source at: ${cliDir}`);

  // Step 2: Find a Python package manager
  const installer = await findPythonInstaller();
  if (!installer) {
    termError('No Python package manager found (pipx, pip3, or pip).');
    termError('Please install Python 3.8+ and pip, then try again.');
    return false;
  }
  termInfo(`Using ${installer.tool} (${installer.path})`);

  // Step 3: Install
  let installCmd: string;
  let displayCmd: string;

  if (installer.tool === 'pipx') {
    installCmd = `"${installer.path}" install "${cliDir}"`;
    displayCmd = `pipx install "${cliDir}"`;
  } else {
    // pip/pip3: use --user to avoid needing sudo, --break-system-packages for modern distros
    installCmd = `"${installer.path}" install --user --break-system-packages "${cliDir}"`;
    displayCmd = `${installer.tool} install --user "${cliDir}"`;
  }

  const result = await termExec(displayCmd, installCmd);

  if (result.code === 0) {
    // Verify installation
    const verifyPath = await resolveCliPath();
    if (verifyPath) {
      termSuccess(`wordpress-sync installed successfully at ${verifyPath}`);
      return true;
    } else {
      // pip --user installs to ~/.local/bin which may need PATH
      termInfo('Install succeeded but wordpress-sync not yet on PATH. Checking ~/.local/bin...');
      const checkResult = await Command.create('exec-sh', [
        '-c',
        `${PATH_SETUP}; test -f "$HOME/.local/bin/wordpress-sync" && echo "$HOME/.local/bin/wordpress-sync"`
      ]).execute();
      if (checkResult.code === 0 && checkResult.stdout.trim()) {
        termSuccess(`wordpress-sync installed at ${checkResult.stdout.trim()}`);
        return true;
      }
      termError('Installation appeared to succeed but wordpress-sync binary not found on PATH.');
      return false;
    }
  } else {
    termError('CLI installation failed. Check the terminal output above for details.');
    return false;
  }
}

/**
 * Get the version of the wordpress-sync CLI tool.
 */
export async function getCliVersion(cliPath: string): Promise<string | null> {
  try {
    const result = await Command.create('exec-sh', [
      '-c',
      `${PATH_SETUP}; "${cliPath}" --version`
    ]).execute();
    if (result.code === 0) {
      return result.stdout.trim();
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Build CLI flags from sync options.
 */
function buildCliFlags(opts: {
  direction?: 'push' | 'pull';
  syncType?: 'full' | 'files-only' | 'db-only';
  skipValidation?: boolean;
  skipWpCheck?: boolean;
  noBackup?: boolean;
  skipFinalCleanup?: boolean;
  noDryRun?: boolean;
  itemizeChanges?: boolean;
  nonInteractive?: boolean;
  sudoPasswordStdin?: boolean;
}): string {
  const flags: string[] = [];
  if (opts.direction) flags.push(`--direction ${opts.direction}`);
  if (opts.syncType === 'files-only') flags.push('--files-only');
  if (opts.syncType === 'db-only') flags.push('--db-only');
  if (opts.skipValidation) flags.push('--skip-validation');
  if (opts.skipWpCheck) flags.push('--skip-wp-check');
  if (opts.noBackup) flags.push('--no-backup');
  if (opts.skipFinalCleanup) flags.push('--skip-final-cleanup');
  if (opts.noDryRun) flags.push('--no-dry-run');
  if (opts.itemizeChanges) flags.push('--itemize-changes');
  if (opts.nonInteractive) flags.push('--non-interactive');
  if (opts.sudoPasswordStdin) flags.push('--sudo-password-stdin');
  return flags.join(' ');
}

export interface SyncOptions {
  direction?: 'push' | 'pull';
  syncType?: 'full' | 'files-only' | 'db-only';
  skipValidation?: boolean;
  skipWpCheck?: boolean;
  noBackup?: boolean;
  /** When true, the CLI will read the sudo password from stdin before processing. */
  sudoPasswordStdin?: boolean;
}

/**
 * Create a Command for a dry-run sync.
 * Returns the Command object so the caller can spawn() it and
 * stream output. The CLI defaults to dry-run mode.
 */
export function createDryRunCommand(cliPath: string, configPath: string, opts: SyncOptions = {}) {
  const flags = buildCliFlags({ ...opts, itemizeChanges: true, nonInteractive: true });
  return Command.create('exec-sh', [
    '-c',
    `${PATH_SETUP}; "${cliPath}" --config "${configPath}" ${flags}`
  ]);
}

/**
 * Create a Command for a full (non-dry-run) sync.
 * Returns the Command object so the caller can spawn() it and
 * stream output.
 */
export function createSyncCommand(cliPath: string, configPath: string, opts: SyncOptions = {}) {
  const flags = buildCliFlags({
    ...opts,
    noDryRun: true,
    nonInteractive: true,
    skipFinalCleanup: true,
    sudoPasswordStdin: opts.sudoPasswordStdin,
  });
  return Command.create('exec-sh', [
    '-c',
    `${PATH_SETUP}; "${cliPath}" --config "${configPath}" ${flags}`
  ]);
}

/**
 * Build the shell command string for a manual database backup.
 * Backs up the *destination* (the site that will be overwritten):
 *   - push → remote/live DB
 *   - pull → local DB
 */
export interface BackupOptions {
  direction: 'push' | 'pull';
  ssh: { user: string; host: string; port: number; key_path: string };
  paths: { local: string; live: string };
  backupDir: string;
  filenameFormat: string;
}

export function createBackupCommand(opts: BackupOptions) {
  const timestamp = new Date().toISOString().replace(/[T:]/g, '-').replace(/\..+$/, '');
  const filename = opts.filenameFormat
    ? opts.filenameFormat
        .replace(/%Y/g, new Date().getFullYear().toString())
        .replace(/%m/g, String(new Date().getMonth() + 1).padStart(2, '0'))
        .replace(/%d/g, String(new Date().getDate()).padStart(2, '0'))
        .replace(/%H/g, String(new Date().getHours()).padStart(2, '0'))
        .replace(/%M/g, String(new Date().getMinutes()).padStart(2, '0'))
        .replace(/%S/g, String(new Date().getSeconds()).padStart(2, '0'))
    : `manual-backup-${timestamp}.sql`;

  if (opts.direction === 'push') {
    // Backup remote/live DB via SSH
    const sshKey = opts.ssh.key_path ? `-i "${opts.ssh.key_path}"` : '';
    const sshPort = opts.ssh.port && opts.ssh.port !== 22 ? `-p ${opts.ssh.port}` : '';
    const sshOpts = `${sshKey} ${sshPort} -o BatchMode=yes -o ConnectTimeout=30`.trim();
    const remoteDir = opts.backupDir.startsWith('/')
      ? opts.backupDir
      : `${opts.paths.live}/${opts.backupDir}`;
    const remoteFile = `${remoteDir}/${filename}`;
    const remoteCmd = `mkdir -p "${remoteDir}" && cd "${opts.paths.live}" && wp db export "${remoteFile}" --allow-root 2>&1 && echo "BACKUP_SUCCESS:${remoteFile}"`;
    const fullCmd = `ssh ${sshOpts} ${opts.ssh.user}@${opts.ssh.host} '${remoteCmd}'`;
    return Command.create('exec-sh', ['-c', `${PATH_SETUP}; ${fullCmd}`]);
  } else {
    // Backup local DB
    const localDir = opts.backupDir.startsWith('/')
      ? opts.backupDir
      : `${opts.paths.local}/${opts.backupDir}`;
    const localFile = `${localDir}/${filename}`;
    const localCmd = `mkdir -p "${localDir}" && cd "${opts.paths.local}" && wp db export "${localFile}" 2>&1 && echo "BACKUP_SUCCESS:${localFile}"`;
    return Command.create('exec-sh', ['-c', `${PATH_SETUP}; ${localCmd}`]);
  }
}

/**
 * Legacy wrapper: execute dry run and collect all output.
 * WARNING: This blocks until the process exits. Use createDryRunCommand + spawn for streaming.
 */
export async function executeSyncDryRun(
  cliPath: string,
  configPath: string
): Promise<{ stdout: string; stderr: string; code: number }> {
  try {
    const cmd = createDryRunCommand(cliPath, configPath);
    const result = await cmd.execute();
    return {
      stdout: result.stdout,
      stderr: result.stderr,
      code: result.code ?? -1
    };
  } catch (e) {
    return {
      stdout: '',
      stderr: String(e),
      code: -1
    };
  }
}

/**
 * Legacy wrapper: create a spawn command for full sync.
 */
export function spawnSync(cliPath: string, configPath: string) {
  return createSyncCommand(cliPath, configPath);
}

/**
 * Execute an arbitrary CLI command and return the result.
 */
export async function executeCommand(
  command: string,
  args: string[] = []
): Promise<{ stdout: string; stderr: string; code: number }> {
  try {
    const result = await Command.create('exec-sh', [
      '-c',
      `${PATH_SETUP}; ${[command, ...args].join(' ')}`
    ]).execute();
    return {
      stdout: result.stdout,
      stderr: result.stderr,
      code: result.code ?? -1
    };
  } catch (e) {
    return {
      stdout: '',
      stderr: String(e),
      code: -1
    };
  }
}
