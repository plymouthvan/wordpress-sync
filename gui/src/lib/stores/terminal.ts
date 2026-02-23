import { writable, get } from 'svelte/store';

export interface TerminalLine {
  id: number;
  timestamp: Date;
  type: 'command' | 'stdout' | 'stderr' | 'info' | 'success' | 'error';
  text: string;
}

let nextId = 0;

/**
 * Store holding all terminal output lines.
 */
export const terminalLines = writable<TerminalLine[]>([]);

/**
 * Whether the terminal panel is open/visible.
 */
export const terminalOpen = writable(false);

/**
 * Badge count of unread lines since last panel open.
 */
export const terminalUnread = writable(0);

/**
 * Whether any command is currently running.
 */
export const terminalBusy = writable(false);

// ---- Batching infrastructure ----
// Accumulate lines in a buffer and flush to the store on a throttle
// to avoid overwhelming the UI with per-line reactive updates.
let pendingTermLines: TerminalLine[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
const FLUSH_INTERVAL = 250; // ms — update UI max 4x/sec

function flushPending(): void {
  if (pendingTermLines.length > 0) {
    const batch = pendingTermLines;
    pendingTermLines = [];
    terminalLines.update((lines) => [...lines, ...batch]);
    if (!get(terminalOpen)) {
      terminalUnread.update((n) => n + batch.length);
    }
  }
  flushTimer = null;
}

function scheduleFlush(): void {
  if (!flushTimer) {
    flushTimer = setTimeout(flushPending, FLUSH_INTERVAL);
  }
}

/**
 * Append a line to the terminal log (batched).
 */
export function termLog(type: TerminalLine['type'], text: string): void {
  const line: TerminalLine = { id: nextId++, timestamp: new Date(), type, text };
  pendingTermLines.push(line);
  scheduleFlush();
}

/**
 * Immediately flush any pending terminal lines to the store.
 * Call this after a process finishes to ensure all output is visible.
 */
export function termFlush(): void {
  if (flushTimer) clearTimeout(flushTimer);
  flushPending();
}

/**
 * Log a command being executed (shown with $ prefix styling).
 * Commands flush immediately so they're visible right away.
 */
export function termCommand(cmd: string): void {
  termLog('command', cmd);
  termFlush();
}

/**
 * Log standard output.
 */
export function termStdout(text: string): void {
  if (text.trim()) termLog('stdout', text);
}

/**
 * Log standard error.
 */
export function termStderr(text: string): void {
  if (text.trim()) termLog('stderr', text);
}

/**
 * Log an informational message.
 */
export function termInfo(text: string): void {
  termLog('info', text);
  termFlush();
}

/**
 * Log a success message.
 */
export function termSuccess(text: string): void {
  termLog('success', text);
  termFlush();
}

/**
 * Log an error message.
 */
export function termError(text: string): void {
  termLog('error', text);
  termFlush();
}

/**
 * Clear all terminal lines.
 */
export function termClear(): void {
  pendingTermLines = [];
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = null;
  terminalLines.set([]);
  terminalUnread.set(0);
}

/**
 * Mark all lines as read (reset unread counter).
 */
export function termMarkRead(): void {
  terminalUnread.set(0);
}

/**
 * Execute a shell command and log everything to the terminal.
 * Returns the result.
 */
export async function termExec(
  displayCmd: string,
  actualCmd: string
): Promise<{ stdout: string; stderr: string; code: number }> {
  const { Command } = await import('@tauri-apps/plugin-shell');
  const { PATH_SETUP } = await import('$lib/services/cli');

  termCommand(displayCmd);
  terminalBusy.set(true);

  try {
    const result = await Command.create('exec-sh', [
      '-c',
      `${PATH_SETUP}; ${actualCmd}`
    ]).execute();

    const code = result.code ?? -1;

    if (result.stdout.trim()) {
      for (const line of result.stdout.trim().split('\n')) {
        termStdout(line);
      }
    }
    if (result.stderr.trim()) {
      for (const line of result.stderr.trim().split('\n')) {
        termStderr(line);
      }
    }

    if (code === 0) {
      termSuccess(`Command exited with code 0`);
    } else {
      termError(`Command exited with code ${code}`);
    }

    termFlush();
    terminalBusy.set(false);
    return { stdout: result.stdout, stderr: result.stderr, code };
  } catch (e) {
    termError(`Command failed: ${e}`);
    termFlush();
    terminalBusy.set(false);
    return { stdout: '', stderr: String(e), code: -1 };
  }
}
