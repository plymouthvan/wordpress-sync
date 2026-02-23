/**
 * Health check service for per-site environment diagnostics.
 */

import { executeCommand } from './cli';
import type { SiteConfig } from '$lib/types';

export interface HealthCheckResult {
  name: string;
  status: 'pending' | 'running' | 'passed' | 'failed';
  output?: string;
  error?: string;
  command?: string;
}

/**
 * Run a single health check by executing the given command.
 */
export async function runHealthCheck(
  name: string,
  command: string
): Promise<HealthCheckResult> {
  try {
    const result = await executeCommand(command);
    return {
      name,
      command,
      status: result.code === 0 ? 'passed' : 'failed',
      output: result.stdout,
      error: result.stderr || undefined,
    };
  } catch (e) {
    return { name, command, status: 'failed', error: String(e) };
  }
}

/**
 * Build an SSH command prefix for a given site config.
 */
function sshPrefix(config: SiteConfig): string {
  const { user, host, port, key_path } = config.ssh;
  const parts = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5'];
  if (key_path) {
    parts.push('-i', `"${key_path}"`);
  }
  if (port && port !== 22) {
    parts.push('-p', String(port));
  }
  parts.push(`${user}@${host}`);
  return parts.join(' ');
}

/**
 * Build the full list of health checks for a site.
 * Returns check definitions with name and command string.
 */
export function buildHealthChecks(
  config: SiteConfig
): Array<{ name: string; command: string }> {
  const ssh = sshPrefix(config);
  const localPath = config.paths.local;
  const livePath = config.paths.live;

  return [
    {
      name: 'SSH Connectivity',
      command: `${ssh} echo ok`,
    },
    {
      name: 'WP-CLI (local)',
      command: 'which wp && wp --info',
    },
    {
      name: 'WP-CLI (remote)',
      command: `${ssh} "which wp && wp --info"`,
    },
    {
      name: 'Local WP Installed',
      command: `wp --path="${localPath}" core is-installed`,
    },
    {
      name: 'Remote WP Installed',
      command: `${ssh} "wp --path=\\"${livePath}\\" core is-installed"`,
    },
    {
      name: 'Local Path Valid',
      command: `test -d "${localPath}" && test -f "${localPath}/wp-config.php"`,
    },
    {
      name: 'Remote Path Valid',
      command: `${ssh} "test -d \\"${livePath}\\" && test -f \\"${livePath}/wp-config.php\\""`,
    },
    {
      name: 'rsync Available',
      command: 'which rsync',
    },
    {
      name: 'scp Available',
      command: 'which scp',
    },
    {
      name: 'Local Disk Space',
      command: `df -h "${localPath}"`,
    },
    {
      name: 'Remote Disk Space',
      command: `${ssh} "df -h \\"${livePath}\\""`,
    },
  ];
}
