/**
 * Theme management utilities.
 */

export type Theme = 'light' | 'dark' | 'system';

/**
 * Apply the given theme preference to the document root.
 * - 'light' or 'dark': sets data-theme attribute for manual override.
 * - 'system': removes data-theme, letting prefers-color-scheme take effect.
 */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;

  if (theme === 'system') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', theme);
  }
}

/**
 * Detect the current system theme preference.
 */
export function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Get the effective theme (resolved from 'system' to actual value).
 */
export function getEffectiveTheme(theme: Theme): 'light' | 'dark' {
  return theme === 'system' ? getSystemTheme() : theme;
}

/**
 * Listen for system theme changes and invoke a callback.
 * Returns a cleanup function to remove the listener.
 */
export function onSystemThemeChange(callback: (theme: 'light' | 'dark') => void): () => void {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const handler = (e: MediaQueryListEvent) => {
    callback(e.matches ? 'dark' : 'light');
  };
  mediaQuery.addEventListener('change', handler);
  return () => mediaQuery.removeEventListener('change', handler);
}
