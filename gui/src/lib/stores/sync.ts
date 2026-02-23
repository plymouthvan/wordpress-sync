import { writable } from 'svelte/store';
import type { SyncStep, DiffEntry } from '$lib/types';

export interface SyncState {
  active: boolean;
  siteName: string | null;
  direction: 'push' | 'pull' | null;
  steps: SyncStep[];
  logOutput: string;
  dryRunResults: DiffEntry[];
  startedAt: string | null;
  error: string | null;
}

const INITIAL_STATE: SyncState = {
  active: false,
  siteName: null,
  direction: null,
  steps: [],
  logOutput: '',
  dryRunResults: [],
  startedAt: null,
  error: null
};

/**
 * Store holding the state of the current sync operation.
 */
export const syncState = writable<SyncState>({ ...INITIAL_STATE });

/**
 * Reset the sync state to its initial values.
 */
export function resetSyncState(): void {
  syncState.set({ ...INITIAL_STATE });
}

/**
 * Append a line to the sync log output.
 */
export function appendLogLine(line: string): void {
  syncState.update((state) => ({
    ...state,
    logOutput: state.logOutput + line + '\n'
  }));
}

/**
 * Update the status of a specific sync step.
 */
export function updateStepStatus(
  stepName: string,
  status: SyncStep['status'],
  output?: string
): void {
  syncState.update((state) => ({
    ...state,
    steps: state.steps.map((step) =>
      step.name === stepName ? { ...step, status, output: output ?? step.output } : step
    )
  }));
}
