import { Command } from '@tauri-apps/plugin-shell';
import type { PrerequisiteCheck } from '$lib/types';
import { termCommand, termStdout, termStderr, termSuccess, termError, termInfo } from '$lib/stores/terminal';
import { PATH_SETUP } from '$lib/services/cli';

/**
 * Run a shell command through a login shell to get the user's full PATH.
 * On macOS, Tauri processes inherit a minimal PATH that doesn't include
 * /usr/local/bin, /opt/homebrew/bin, etc.
 */
async function shellExec(cmd: string): Promise<{ stdout: string; stderr: string; code: number }> {
  const result = await Command.create('exec-sh', ['-c', `${PATH_SETUP}; ${cmd}`]).execute();
  return { stdout: result.stdout, stderr: result.stderr, code: result.code ?? -1 };
}

/**
 * Check whether a single prerequisite command is available on the system.
 * Logs results to the terminal panel.
 */
export async function checkPrerequisite(
  name: string,
  command: string
): Promise<PrerequisiteCheck> {
  try {
    termCommand(`which ${command}`);
    const result = await shellExec(`which ${command} 2>/dev/null`);
    if (result.code === 0 && result.stdout.trim()) {
      const path = result.stdout.trim();
      termStdout(path);
      // Try to get version info
      let version: string | undefined;
      try {
        termCommand(`${path} --version`);
        const versionResult = await shellExec(`"${path}" --version 2>&1 | head -1`);
        if (versionResult.code === 0 && versionResult.stdout.trim()) {
          version = versionResult.stdout.trim();
          termStdout(version);
        }
      } catch {
        // Version check is optional
      }
      termSuccess(`${name}: found at ${path}`);
      return { name, command, found: true, path, version };
    }
    termError(`${name}: not found`);
    if (result.stderr.trim()) termStderr(result.stderr.trim());
    return { name, command, found: false };
  } catch (e) {
    termError(`${name}: error - ${e}`);
    return { name, command, found: false, error: String(e) };
  }
}

/**
 * Check all required prerequisites for wordpress-sync.
 */
export async function checkAllPrerequisites(): Promise<PrerequisiteCheck[]> {
  termInfo('Checking prerequisites...');
  const results = await Promise.all([
    checkPrerequisite('WordPress Sync CLI', 'wordpress-sync'),
    checkPrerequisite('WP-CLI', 'wp'),
    checkPrerequisite('rsync', 'rsync'),
    checkPrerequisite('scp', 'scp'),
    checkPrerequisite('SSH', 'ssh')
  ]);
  const found = results.filter(r => r.found).length;
  termInfo(`Prerequisites check complete: ${found}/${results.length} found`);
  return results;
}
