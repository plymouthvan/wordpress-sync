/**
 * Centralized keyboard shortcut handling.
 */

export type ShortcutHandler = () => void;

export interface Shortcut {
  key: string;
  meta?: boolean; // Cmd on Mac, Ctrl on other platforms
  ctrl?: boolean;
  shift?: boolean;
  handler: ShortcutHandler;
  description: string;
}

/**
 * Handle a keydown event against a list of registered shortcuts.
 * Returns true if a shortcut matched and was handled.
 */
export function handleKeydown(event: KeyboardEvent, shortcuts: Shortcut[]): boolean {
  const isMac = navigator.platform.includes('Mac');

  for (const shortcut of shortcuts) {
    // meta means Cmd on Mac, Ctrl elsewhere
    const metaMatch = shortcut.meta
      ? (isMac ? event.metaKey : event.ctrlKey)
      : !(isMac ? event.metaKey : false);

    const ctrlMatch = shortcut.ctrl ? event.ctrlKey : !event.ctrlKey || (shortcut.meta && !isMac);
    const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;

    if (
      event.key.toLowerCase() === shortcut.key.toLowerCase() &&
      metaMatch &&
      shiftMatch
    ) {
      // For meta shortcuts on non-Mac, ctrl is already checked via metaMatch
      // For explicit ctrl shortcuts, check ctrlMatch
      if (shortcut.meta && !isMac) {
        // metaMatch already verified ctrlKey
        event.preventDefault();
        shortcut.handler();
        return true;
      }
      if (shortcut.ctrl && !event.ctrlKey) {
        continue;
      }
      if (!shortcut.meta && !shortcut.ctrl && (event.metaKey || event.ctrlKey)) {
        continue;
      }
      event.preventDefault();
      shortcut.handler();
      return true;
    }
  }

  return false;
}

/**
 * Format a shortcut for display (e.g., "Cmd+N" or "Ctrl+N").
 */
export function formatShortcut(shortcut: Shortcut): string {
  const isMac = typeof navigator !== 'undefined' && navigator.platform.includes('Mac');
  const parts: string[] = [];

  if (shortcut.meta) {
    parts.push(isMac ? '\u2318' : 'Ctrl');
  }
  if (shortcut.ctrl) {
    parts.push('Ctrl');
  }
  if (shortcut.shift) {
    parts.push(isMac ? '\u21E7' : 'Shift');
  }

  parts.push(shortcut.key.toUpperCase());
  return parts.join(isMac ? '' : '+');
}
