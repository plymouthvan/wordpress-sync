/**
 * Parse a step marker line from CLI output.
 * Returns the step number and whether it was skipped.
 */
export function parseStepMarker(line: string): { step: number; skipped: boolean } | null {
  const match = line.match(/Step\s+(\d+)/i);
  if (!match) return null;
  const step = parseInt(match[1]);
  const skipped = /skip/i.test(line);
  return { step, skipped };
}

/**
 * Parse rsync --info=progress2 output for transfer progress.
 * Format: "1,234,567  45%   12.34MB/s   0:01:23"
 */
export function parseRsyncProgress(
  line: string,
): { percent: number; speed: string; eta: string } | null {
  const match = line.match(
    /[\d,]+\s+(\d+)%\s+([\d.]+\s*\w+\/s)\s+([\d:]+)/,
  );
  if (!match) return null;
  return {
    percent: parseInt(match[1]),
    speed: match[2].trim(),
    eta: match[3],
  };
}

/**
 * Check if a line is an interactive prompt requiring user input.
 */
export function isInteractivePrompt(
  line: string,
): { question: string; type: 'yesno' } | null {
  if (line.includes('(yes/no)') || line.includes('(y/n)')) {
    return { question: line, type: 'yesno' };
  }
  return null;
}

/**
 * Strip ANSI escape codes from a string.
 */
export function stripAnsi(text: string): string {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '');
}
