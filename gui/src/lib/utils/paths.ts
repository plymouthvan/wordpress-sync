import { homeDir, join } from '@tauri-apps/api/path';

/**
 * Expand a tilde (~) path to the full home directory path.
 */
export async function expandTilde(path: string): Promise<string> {
  if (path.startsWith('~/') || path === '~') {
    const home = await homeDir();
    return path.replace('~', home);
  }
  return path;
}

/**
 * Contract a full path back to use tilde notation.
 */
export async function contractToTilde(path: string): Promise<string> {
  const home = await homeDir();
  if (path.startsWith(home)) {
    return path.replace(home, '~/');
  }
  return path;
}

/**
 * Join path segments using the platform separator.
 */
export async function joinPath(...segments: string[]): Promise<string> {
  if (segments.length === 0) return '';
  let result = segments[0];
  for (let i = 1; i < segments.length; i++) {
    result = await join(result, segments[i]);
  }
  return result;
}
