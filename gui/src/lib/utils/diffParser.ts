import type { DiffEntry } from '$lib/types';

/**
 * Parse rsync --itemize-changes output into structured DiffEntry objects.
 *
 * Rsync itemize format: YXcstpoguax[f] path/to/file
 *   Y = update type (<, >, c, h, ., *)
 *   X = file type (f, d, L, D, S)
 *   Attribute flags (9 in older rsync, 10 in rsync 3.2+):
 *     c = checksum, s = size, t = time, p = perms, o = owner, g = group,
 *     u/n/b = access/create time, a = ACL, x = xattr, f = fflags (rsync 3.2+)
 *   Each position can be: the letter (changed), '.' (unchanged),
 *     '+' (newly created), ' ' (not checked), '?' (unknown)
 *
 * The total prefix is always YX + 9 or 10 attribute chars = 11 or 12 chars,
 * followed by a single space, then the file path. Attribute positions may
 * contain literal spaces, so we parse by position rather than splitting on
 * whitespace.
 */
export function parseItemizeChanges(output: string): DiffEntry[] {
  const entries: DiffEntry[] = [];
  const lines = output.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // *deleting pattern
    if (trimmed.startsWith('*deleting')) {
      const path = trimmed.replace(/^\*deleting\s+/, '');
      entries.push({
        path,
        type: path.endsWith('/') ? 'directory' : 'file',
        change: 'deleted',
        selected: true,
      });
      continue;
    }

    // Must start with a valid Y (update type) and X (file type)
    if (trimmed.length < 13) continue;
    const Y = trimmed[0]; // update type
    const X = trimmed[1]; // file type
    if (!'<>ch.'.includes(Y)) continue;
    if (!'fdLDS'.includes(X)) continue;

    // Extract attribute flags and path.
    // Rsync 3.2+ uses 10 attribute positions (12-char prefix),
    // older versions use 9 (11-char prefix). Try 12-char first.
    let flags: string;
    let path: string;
    if (trimmed[12] === ' ' && trimmed.length > 13) {
      // 10 attribute flags (rsync 3.2+): prefix is 12 chars
      flags = trimmed.substring(2, 12);
      path = trimmed.substring(13);
    } else if (trimmed[11] === ' ' && trimmed.length > 12) {
      // 9 attribute flags (older rsync): prefix is 11 chars
      flags = trimmed.substring(2, 11);
      path = trimmed.substring(12);
    } else {
      continue;
    }

    // Skip unchanged items (Y='.', all attribute flags are dots or spaces)
    if (Y === '.' && /^[. ]+$/.test(flags)) continue;

    const isNew = /^\++$/.test(flags);
    const isDirectory = X === 'd';

    entries.push({
      path: path.replace(/\/$/, ''), // normalize trailing slash
      type: isDirectory ? 'directory' : 'file',
      change: isNew ? 'added' : 'modified',
      selected: true,
    });
  }

  return entries;
}
