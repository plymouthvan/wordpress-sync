<script lang="ts">
  import { selectedSite } from '$lib/stores/sites';
  import { settings } from '$lib/stores/settings';
  import {
    syncState,
    resetSyncState,
    appendLogLine,
    updateStepStatus,
  } from '$lib/stores/sync';
  import type { SyncStep, DiffEntry } from '$lib/types';
  import { createDryRunCommand, createSyncCommand, createBackupCommand, type SyncOptions, type BackupOptions } from '$lib/services/cli';
  import { getSiteConfigPath, loadSiteConfig, normalizeBackupConfig, normalizeDbTempConfig } from '$lib/services/config';
  import type { SiteConfig } from '$lib/types';
  import { saveHistoryEntry } from '$lib/services/history';
  import { refreshSiteList } from '$lib/stores/sites';
  import { parseItemizeChanges } from '$lib/utils/diffParser';
  import { parseRsyncProgress, parseStepMarker, isInteractivePrompt, stripAnsi } from '$lib/utils/outputParser';
  import { termCommand, termStdout, termStderr, termError, termInfo, termSuccess, terminalOpen } from '$lib/stores/terminal';
  import { checkLatestHasContents, deleteLatestContents, archiveLatestContents, resolveDbBackupDir } from '$lib/services/backup';
  import { getSudoPassword } from '$lib/services/keychain';
  import DiffViewer from '$lib//../components/sync/DiffViewer.svelte';
  import StepTracker from '$lib//../components/sync/StepTracker.svelte';
  import LogOutput from '$lib//../components/sync/LogOutput.svelte';
  import ConfirmDialog from '$lib//../components/sync/ConfirmDialog.svelte';

  // Props
  interface Props {
    initialDirection?: 'push' | 'pull';
    onNavigate?: (view: string) => void;
  }
  let { initialDirection, onNavigate }: Props = $props();

  // View state machine
  type PanelPhase =
    | 'options'
    | 'dry-run'
    | 'diff-viewer'
    | 'syncing'
    | 'complete';

  let phase: PanelPhase = $state('options');
  let siteName = $derived($selectedSite ?? 'No site selected');
  let appSettings = $derived($settings);
  let currentSyncState = $derived($syncState);

  // Pre-sync options — initialDirection prop takes precedence when set
  let direction: 'push' | 'pull' = $state(initialDirection ?? 'pull');
  let lastInitialDirection: string | undefined = initialDirection;
  $effect(() => {
    if (initialDirection !== lastInitialDirection) {
      lastInitialDirection = initialDirection;
      if (initialDirection) direction = initialDirection;
    }
  });

  // Fallback: when no initialDirection is provided, load direction from site config
  let configDirectionLoaded = false;
  $effect(() => {
    const site = $selectedSite;
    if (!initialDirection && site && phase === 'options' && !configDirectionLoaded) {
      configDirectionLoaded = true;
      loadSiteConfig(site).then((cfg) => {
        if (cfg?.operation?.direction && (cfg.operation.direction === 'push' || cfg.operation.direction === 'pull')) {
          direction = cfg.operation.direction;
        }
      }).catch(() => {
        // Ignore — keep default 'pull'
      });
    }
  });
  let syncType: 'full' | 'files-only' | 'db-only' = $state('full');
  let skipDryRun = $state(false);
  let skipValidation = $state(false);
  let skipWpCheck = $state(false);
  let noBackup = $state(false);

  // Site config for backup status
  let siteConfig = $state<SiteConfig | null>(null);
  let siteConfigLoading = $state(false);
  let siteConfigLoaded = false;

  // Derived backup status from config
  let fileBackupEnabled = $derived(siteConfig?.backup?.enabled ?? false);
  let dbBackupEnabled = $derived(siteConfig?.backup?.database?.enabled ?? false);
  let backupConfigured = $derived(fileBackupEnabled || dbBackupEnabled);

  // Manual backup state
  let backupInProgress = $state(false);
  let backupResult = $state<{ success: boolean; message: string } | null>(null);

  // Load site config when site changes
  $effect(() => {
    const site = $selectedSite;
    if (site && !siteConfigLoaded) {
      siteConfigLoaded = true;
      siteConfigLoading = true;
      loadSiteConfig(site).then((cfg) => {
        siteConfig = normalizeDbTempConfig(normalizeBackupConfig(cfg));
        siteConfigLoading = false;
      }).catch(() => {
        siteConfigLoading = false;
      });
    }
  });

  async function takeBackupNow() {
    if (!siteConfig || !$selectedSite || backupInProgress) return;

    backupInProgress = true;
    backupResult = null;
    terminalOpen.set(true);

    const location = direction === 'push' ? 'remote' as const : 'local' as const;
    const backupDir = resolveDbBackupDir(siteConfig, location);
    const filenameFormat = siteConfig.backup?.database?.filename_format || 'manual-backup-%Y%m%d-%H%M%S.sql';

    const opts: BackupOptions = {
      direction,
      ssh: siteConfig.ssh,
      paths: siteConfig.paths,
      backupDir,
      filenameFormat,
    };

    const target = direction === 'push' ? 'remote (live)' : 'local';
    termInfo(`Taking manual database backup of ${target} site...`);

    try {
      const cmd = createBackupCommand(opts);
      const result = await cmd.execute();
      const output = (result.stdout + '\n' + result.stderr).trim();

      if (result.code === 0 && output.includes('BACKUP_SUCCESS:')) {
        const backupPath = output.split('BACKUP_SUCCESS:').pop()?.trim() ?? '';
        const msg = `Database backup saved to: ${backupPath}`;
        termSuccess(msg);
        backupResult = { success: true, message: msg };
      } else {
        const errMsg = output || `Backup failed with exit code ${result.code}`;
        termError(`Backup failed: ${errMsg}`);
        backupResult = { success: false, message: errMsg };
      }
    } catch (e) {
      const errMsg = String(e);
      termError(`Backup failed: ${errMsg}`);
      backupResult = { success: false, message: errMsg };
    }

    backupInProgress = false;
  }

  // Dry run results
  let dryRunOutput: string[] = $state([]);
  let dryRunEntries: DiffEntry[] = $state([]);
  let dryRunError: string | null = $state(null);

  // Sync execution state
  let syncSteps: SyncStep[] = $state([]);
  let logLines: string[] = $state([]);
  let rsyncProgress: { percent: number; speed: string; eta: string } | null =
    $state(null);
  let syncStartTime: number | null = $state(null);
  let syncEndTime: number | null = $state(null);
  let syncResult: 'success' | 'failed' | 'cancelled' | null = $state(null);
  let activeChild: any = $state(null);

  // Interactive prompt
  let pendingPrompt: { question: string; type: 'yesno' } | null = $state(null);

  /**
   * If the site is a push with a sudo user, fetch the stored password from Keychain.
   * Returns null if not applicable or no password stored.
   */
  async function fetchSudoPasswordIfNeeded(): Promise<string | null> {
    if (direction !== 'push') return null;
    const sudoUser = siteConfig?.ssh?.sudo?.user;
    if (!sudoUser) return null;
    try {
      const password = await getSudoPassword($selectedSite ?? '');
      if (password) {
        termInfo(`Sudo password found in Keychain for "${$selectedSite}" (user: ${sudoUser})`);
      } else {
        termInfo(`No sudo password in Keychain for "${$selectedSite}". Ownership step may be skipped.`);
      }
      return password;
    } catch (e) {
      console.error('Failed to fetch sudo password from Keychain:', e);
      return null;
    }
  }

  // Stall detection timers (tiered: info first, then error, no repeats)
  let dryRunStallTimer: ReturnType<typeof setInterval> | null = null;
  let dryRunStallTier = 0; // 0=none, 1=info (2min), 2=error (5min)
  let syncStallTimer: ReturnType<typeof setInterval> | null = null;
  let syncStallTier = 0; // 0=none, 1=info (5min), 2=error (15min)

  // Computed
  let durationStr = $derived.by(() => {
    if (!syncStartTime) return '';
    const end = syncEndTime ?? Date.now();
    const seconds = Math.floor((end - syncStartTime) / 1000);
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  });

  let filesTransferred = $derived.by(() => {
    // Count from log lines that look like rsync transfer lines
    return logLines.filter(
      (l) => l.includes('<f') || l.includes('>f') || l.includes('cf'),
    ).length;
  });

  // =============================
  // Actions
  // =============================

  async function startSync() {
    if (!$selectedSite) return;

    resetSyncState();
    dryRunOutput = [];
    dryRunEntries = [];
    dryRunError = null;
    logLines = [];
    syncSteps = [];
    rsyncProgress = null;
    syncResult = null;
    syncStartTime = null;
    syncEndTime = null;

    if (skipDryRun) {
      // Go directly to syncing
      phase = 'syncing';
      await executeFullSync();
    } else {
      // Run dry run first
      phase = 'dry-run';
      await executeDryRun();
    }
  }

  function buildSyncOpts(sudoPasswordStdin = false): SyncOptions {
    return {
      direction,
      syncType,
      skipValidation,
      skipWpCheck,
      noBackup,
      sudoPasswordStdin,
    };
  }

  async function executeDryRun() {
    const cliPath = appSettings.cli_path;
    if (!cliPath || !$selectedSite) {
      dryRunError = 'CLI path not configured or no site selected.';
      return;
    }

    // Fetch sudo password before spawning (for push syncs with sudo user)
    const sudoPassword = await fetchSudoPasswordIfNeeded();
    const useSudoStdin = sudoPassword !== null;

    try {
      const configPath = await getSiteConfigPath($selectedSite);
      dryRunOutput = ['Starting dry run...'];

      const cmd = createDryRunCommand(cliPath, configPath, buildSyncOpts(useSudoStdin));
      let stdoutBuf = '';
      let stderrBuf = '';
      let lastOutputTime = Date.now();

      // Batching: accumulate lines, flush to UI on a throttle
      let pendingLines: string[] = [];
      let flushTimer: ReturnType<typeof setTimeout> | null = null;
      const FLUSH_INTERVAL = 250; // ms — update UI max 4x/sec

      function flushPendingLines() {
        if (pendingLines.length > 0) {
          dryRunOutput = [...dryRunOutput, ...pendingLines];
          pendingLines = [];
        }
        flushTimer = null;
      }

      function scheduleFlush() {
        if (!flushTimer) {
          flushTimer = setTimeout(flushPendingLines, FLUSH_INTERVAL);
        }
      }

      terminalOpen.set(true);
      termCommand(`wordpress-sync --config "${configPath}" --itemize-changes --non-interactive`);

      // Set up output handlers BEFORE spawning
      cmd.stdout.on('data', (data: string) => {
        const line = stripAnsi(data);
        stdoutBuf += line + '\n';
        pendingLines.push(line);
        scheduleFlush();
        lastOutputTime = Date.now();
        dryRunStallTier = 0;

        // Safety net: if the CLI somehow still prompts despite --non-interactive,
        // detect and auto-respond "no" to prevent hanging.
        const prompt = isInteractivePrompt(line);
        if (prompt && activeChild) {
          try {
            activeChild.write('no\n');
            termInfo(`Auto-responded "no" to unexpected prompt: ${prompt.question}`);
          } catch {
            // Process may have exited
          }
        }
      });

      cmd.stderr.on('data', (data: string) => {
        const line = stripAnsi(data);
        stderrBuf += line + '\n';
        pendingLines.push(`[stderr] ${line}`);
        scheduleFlush();
        lastOutputTime = Date.now();
        dryRunStallTier = 0;
      });

      // Handle process exit - fire-and-forget, no await blocking
      cmd.on('close', (payload: { code: number | null; signal: number | null }) => {
        activeChild = null;
        if (dryRunStallTimer) clearInterval(dryRunStallTimer);
        // Flush any remaining buffered lines
        if (flushTimer) clearTimeout(flushTimer);
        flushPendingLines();

        const code = payload.code ?? -1;

        if (code !== 0) {
          dryRunError = stderrBuf.trim() || `Process exited with code ${code}`;
          termError(`Dry run exited with code ${code}`);
          return;
        }

        termSuccess('Dry run complete');

        // Parse itemize-changes output
        dryRunEntries = parseItemizeChanges(stdoutBuf);

        if (dryRunEntries.length > 0) {
          phase = 'diff-viewer';
        } else {
          dryRunOutput = [...dryRunOutput, '', 'No changes detected.'];
        }
      });

      // Spawn the process
      const child = await cmd.spawn();
      activeChild = child;

      // If we have a sudo password, pipe it to stdin immediately after spawn.
      // The CLI reads one line from stdin (--sudo-password-stdin) before processing.
      if (useSudoStdin && sudoPassword) {
        try {
          await child.write(sudoPassword + '\n');
        } catch (e) {
          console.error('Failed to write sudo password to stdin:', e);
          termError('Failed to send sudo password to CLI process.');
        }
      }

      // Stall detection: tiered notices for long-running operations.
      // Tier 1 (2 min): informational — remote may be slow.
      // Tier 2 (5 min): warning — connection may have dropped.
      dryRunStallTier = 0;
      dryRunStallTimer = setInterval(() => {
        if (!activeChild) return;
        const elapsed = Date.now() - lastOutputTime;
        const elapsedMin = Math.floor(elapsed / 60_000);
        if (dryRunStallTier < 2 && elapsed > 300_000) {
          dryRunStallTier = 2;
          pendingLines.push('', `[warning] No output for ${elapsedMin} minutes. The process may be waiting for input or the connection may have dropped.`);
          flushPendingLines();
          termError(`No output for ${elapsedMin} minutes — the process may need input or the SSH connection may have dropped.`);
        } else if (dryRunStallTier < 1 && elapsed > 120_000) {
          dryRunStallTier = 1;
          pendingLines.push('', `[waiting] No output for ${elapsedMin} minutes — the remote server may be slow to respond.`);
          flushPendingLines();
          termInfo(`No output for ${elapsedMin} minutes — the remote server may be slow to respond.`);
        }
      }, 30_000);

    } catch (e) {
      dryRunError = String(e);
      termError(`Dry run failed: ${e}`);
    }
  }

  async function handleDiffProceed(selected: DiffEntry[]) {
    // User confirmed the diff, proceed to actual sync
    phase = 'syncing';
    await executeFullSync();
  }

  function handleDiffCancel() {
    phase = 'options';
  }

  async function executeFullSync() {
    const cliPath = appSettings.cli_path;
    if (!cliPath || !$selectedSite) return;

    // Fetch sudo password before spawning (for push syncs with sudo user)
    const sudoPassword = await fetchSudoPasswordIfNeeded();
    const useSudoStdin = sudoPassword !== null;

    syncStartTime = Date.now();
    // These match the CLI's 12-step sequence exactly.
    // The CLI always prints "Step N: ..." for each.
    syncSteps = [
      { name: 'Enabling maintenance mode', status: 'pending' },       // Step 1
      { name: 'Exporting database from source', status: 'pending' },  // Step 2
      { name: 'Transferring files', status: 'pending' },              // Step 3
      { name: 'Setting file permissions', status: 'pending' },        // Step 4
      { name: 'Importing database to target', status: 'pending' },    // Step 5
      { name: 'Updating URLs', status: 'pending' },                   // Step 6
      { name: 'Clearing cache', status: 'pending' },                  // Step 7
      { name: 'Managing plugins', status: 'pending' },                // Step 8
      { name: 'Running validation checks', status: 'pending' },       // Step 9
      { name: 'Disabling maintenance mode', status: 'pending' },      // Step 10
      { name: 'Reviewing backed up files', status: 'pending' },       // Step 11
      { name: 'Cleaning up temporary files', status: 'pending' },     // Step 12
    ];

    // Mark first step as active
    syncSteps[0].status = 'in_progress';

    try {
      const configPath = await getSiteConfigPath($selectedSite);
      const cmd = createSyncCommand(cliPath, configPath, buildSyncOpts(useSudoStdin));

      terminalOpen.set(true);
      termCommand(`wordpress-sync --config "${configPath}" --no-dry-run --non-interactive`);

      // Batching for log lines to avoid overwhelming the UI
      let pendingSyncLines: string[] = [];
      let syncFlushTimer: ReturnType<typeof setTimeout> | null = null;
      let lastSyncOutputTime = Date.now();

      function flushSyncLines() {
        if (pendingSyncLines.length > 0) {
          logLines = [...logLines, ...pendingSyncLines];
          pendingSyncLines = [];
        }
        syncFlushTimer = null;
      }

      function scheduleSyncFlush() {
        if (!syncFlushTimer) {
          syncFlushTimer = setTimeout(flushSyncLines, 250);
        }
      }

      // Set up output handlers BEFORE spawning
      cmd.stdout.on('data', (data: string) => {
        const line = stripAnsi(data);
        pendingSyncLines.push(line);
        scheduleSyncFlush();
        appendLogLine(line);

        // Check for step markers
        const stepInfo = parseStepMarker(line);
        if (stepInfo !== null && stepInfo.step > 0 && stepInfo.step <= syncSteps.length) {
          const idx = stepInfo.step - 1;
          // Mark previous steps as completed
          for (let i = 0; i < idx; i++) {
            if (syncSteps[i].status !== 'failed') {
              syncSteps[i] = { ...syncSteps[i], status: 'completed' };
            }
          }
          if (stepInfo.skipped) {
            // Skipped steps go straight to completed
            syncSteps[idx] = { ...syncSteps[idx], status: 'completed', output: 'Skipped' };
          } else {
            syncSteps[idx] = { ...syncSteps[idx], status: 'in_progress' };
          }
          syncSteps = [...syncSteps]; // trigger reactivity
        }

        // Check for rsync progress
        const progress = parseRsyncProgress(line);
        if (progress) {
          rsyncProgress = progress;
        }

        // Track output time for stall detection; reset tier so the next
        // quiet period gets its own fresh set of tiered notices.
        lastSyncOutputTime = Date.now();
        syncStallTier = 0;

        // Check for interactive prompts — show dialog for user to decide
        // unless the prompt is unexpected (safety net: auto-respond)
        const prompt = isInteractivePrompt(line);
        if (prompt) {
          // With --non-interactive the CLI shouldn't prompt, but if it does,
          // auto-respond with the safe default to prevent hanging.
          if (activeChild) {
            try {
              activeChild.write('no\n');
              termInfo(`Auto-responded "no" to unexpected prompt: ${prompt.question}`);
            } catch {
              // Process may have exited
            }
          }
        }
      });

      cmd.stderr.on('data', (data: string) => {
        const line = stripAnsi(data);
        pendingSyncLines.push(`[stderr] ${line}`);
        scheduleSyncFlush();
        appendLogLine(line);
        lastSyncOutputTime = Date.now();
        syncStallTier = 0;
      });

      cmd.on('close', (payload: { code: number | null; signal: number | null }) => {
        syncEndTime = Date.now();
        activeChild = null;
        if (syncStallTimer) { clearInterval(syncStallTimer); syncStallTimer = null; }
        // Flush any remaining buffered lines
        if (syncFlushTimer) clearTimeout(syncFlushTimer);
        flushSyncLines();

        const code = payload.code;
        if (code === 0) {
          syncResult = 'success';
          termSuccess('Sync completed successfully');
          // Mark all remaining steps as completed
          syncSteps = syncSteps.map((s) =>
            s.status === 'pending' || s.status === 'in_progress'
              ? { ...s, status: 'completed' }
              : s,
          );
        } else {
          syncResult = 'failed';
          termError(`Sync failed with code ${code}`);
          // Mark current in-progress step as failed
          syncSteps = syncSteps.map((s) =>
            s.status === 'in_progress' ? { ...s, status: 'failed' } : s,
          );
        }

        phase = 'complete';

        // Save sync history entry (fire-and-forget async)
        const completedAt = new Date().toISOString();
        const startedAt = syncStartTime ? new Date(syncStartTime).toISOString() : completedAt;
        const durationSeconds = syncStartTime ? Math.floor((Date.now() - syncStartTime) / 1000) : 0;
        const _siteName = $selectedSite ?? 'unknown';
        const _direction = direction;
        const _syncType = syncType;
        const _code = code;
        const _logSnapshot = logLines.join('\n');
        // Capture values for async closures
        const _noBackup = noBackup;
        const _siteConfig = siteConfig;

        (async () => {
          try {
            const cfg = await loadSiteConfig(_siteName);
            await saveHistoryEntry({
              id: `${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
              site_name: _siteName,
              direction: _direction,
              sync_type: _syncType,
              started_at: startedAt,
              completed_at: completedAt,
              duration_seconds: durationSeconds,
              status: _code === 0 ? 'success' : 'failed',
              exit_code: _code ?? -1,
              log: _logSnapshot,
              config_snapshot: cfg,
            });
            await refreshSiteList();
          } catch (histErr) {
            console.error('Failed to save history:', histErr);
          }
        })();

        // Post-sync backup cleanup prompt (only on success, when backup is enabled)
        if (_code === 0 && !_noBackup && _siteConfig?.backup?.cleanup_prompt) {
          (async () => {
            try {
              const cfg = _siteConfig!;
              const { hasContents, fileCount } = await checkLatestHasContents(cfg, _direction);
              if (!hasContents) return;

              const dest = _direction === 'push' ? 'remote server' : 'local system';
              const { ask } = await import('@tauri-apps/plugin-dialog');

              // Ask whether to delete or archive
              const shouldDelete = await ask(
                `${fileCount} file(s) were backed up on the ${dest} during sync.\n\nDelete them now, or keep them as an archive?`,
                {
                  title: 'Cleanup Backed-up Files',
                  okLabel: 'Delete',
                  cancelLabel: 'Keep (Archive)',
                }
              );

              if (shouldDelete) {
                termInfo('Cleaning up backed-up files...');
                const result = await deleteLatestContents(cfg, _direction);
                if (result.success) {
                  const verb = result.trashed ? 'Moved to Trash' : 'Deleted';
                  termSuccess(`${verb} backed-up files`);
                } else {
                  termError(`Cleanup failed: ${result.error}`);
                }
              } else {
                termInfo('Archiving backed-up files...');
                const result = await archiveLatestContents(cfg, _direction);
                if (result.success) {
                  termSuccess(`Archived to: ${result.archivePath}`);
                } else {
                  termError(`Archive failed: ${result.error}`);
                }
              }
            } catch (cleanupErr) {
              console.error('Cleanup prompt failed:', cleanupErr);
            }
          })();
        }
      });

      // Spawn after all event handlers are attached
      const child = await cmd.spawn();
      activeChild = child;

      // If we have a sudo password, pipe it to stdin immediately after spawn.
      // The CLI reads one line from stdin (--sudo-password-stdin) before processing.
      if (useSudoStdin && sudoPassword) {
        try {
          await child.write(sudoPassword + '\n');
        } catch (e) {
          console.error('Failed to write sudo password to stdin:', e);
          termError('Failed to send sudo password to CLI process.');
        }
      }

      // Stall detection: tiered notices for long-running operations.
      // Many sync steps (chmod on thousands of files, SCP of large DBs, DB import)
      // produce no output for several minutes — that's normal.
      // Tier 1 (5 min): informational — normal for large sites.
      // Tier 2 (15 min): warning — something may actually be wrong.
      syncStallTier = 0;
      syncStallTimer = setInterval(() => {
        if (!activeChild) return;
        const elapsed = Date.now() - lastSyncOutputTime;
        const elapsedMin = Math.floor(elapsed / 60_000);
        if (syncStallTier < 2 && elapsed > 900_000) {
          syncStallTier = 2;
          pendingSyncLines.push('', `[warning] No output for ${elapsedMin} minutes. The SSH connection may have dropped, or the process may need input.`);
          flushSyncLines();
          termError(`No output for ${elapsedMin} minutes — the SSH connection may have dropped or the process may need input.`);
        } else if (syncStallTier < 1 && elapsed > 300_000) {
          syncStallTier = 1;
          pendingSyncLines.push('', `[waiting] No output for ${elapsedMin} minutes — this is normal for large file permission changes or database operations.`);
          flushSyncLines();
          termInfo(`No output for ${elapsedMin} minutes — this is normal for large sites. Still working...`);
        }
      }, 60_000);
    } catch (e) {
      syncEndTime = Date.now();
      syncResult = 'failed';
      logLines = [...logLines, `Error: ${String(e)}`];
      termError(`Sync failed: ${e}`);
      phase = 'complete';
    }
  }

  async function cancelDryRun() {
    if (dryRunStallTimer) {
      clearInterval(dryRunStallTimer);
      dryRunStallTimer = null;
    }
    if (activeChild) {
      try {
        await activeChild.kill();
      } catch {
        // Process may have already exited
      }
      activeChild = null;
    }
    dryRunError = 'Dry run cancelled.';
    termInfo('Dry run cancelled by user');
  }

  async function cancelSync() {
    if (syncStallTimer) { clearInterval(syncStallTimer); syncStallTimer = null; }
    if (activeChild) {
      await activeChild.kill();
      activeChild = null;
    }
    syncEndTime = Date.now();
    syncResult = 'cancelled';
    syncSteps = syncSteps.map((s) =>
      s.status === 'in_progress'
        ? { ...s, status: 'failed', output: 'Cancelled' }
        : s,
    );
    phase = 'complete';

    // Save cancelled sync to history
    const completedAt = new Date().toISOString();
    const startedAt = syncStartTime ? new Date(syncStartTime).toISOString() : completedAt;
    const durationSeconds = syncStartTime ? Math.floor((Date.now() - syncStartTime) / 1000) : 0;
    try {
      const siteConfig = await loadSiteConfig($selectedSite ?? '');
      await saveHistoryEntry({
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
        site_name: $selectedSite ?? 'unknown',
        direction,
        sync_type: syncType,
        started_at: startedAt,
        completed_at: completedAt,
        duration_seconds: durationSeconds,
        status: 'cancelled',
        exit_code: -1,
        log: logLines.join('\n'),
        config_snapshot: siteConfig,
      });
      await refreshSiteList();
    } catch (histErr) {
      console.error('Failed to save history:', histErr);
    }
  }

  function handlePromptResponse(answer: boolean) {
    if (activeChild && pendingPrompt) {
      activeChild.write(answer ? 'yes\n' : 'no\n');
      pendingPrompt = null;
    }
  }

  function returnToOptions() {
    if (dryRunStallTimer) {
      clearInterval(dryRunStallTimer);
      dryRunStallTimer = null;
    }
    dryRunStallTier = 0;
    if (syncStallTimer) {
      clearInterval(syncStallTimer);
      syncStallTimer = null;
    }
    syncStallTier = 0;
    phase = 'options';
    resetSyncState();
    logLines = [];
    syncSteps = [];
    dryRunEntries = [];
    dryRunOutput = [];
    dryRunError = null;
    rsyncProgress = null;
    syncResult = null;
    syncStartTime = null;
    syncEndTime = null;
  }

  async function copyLog() {
    const text = logLines.join('\n');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback: ignore
    }
  }

  async function saveLog() {
    try {
      const { save } = await import('@tauri-apps/plugin-dialog');
      const { writeTextFile } = await import('@tauri-apps/plugin-fs');
      const path = await save({
        defaultPath: `sync-log-${Date.now()}.txt`,
        filters: [{ name: 'Text', extensions: ['txt', 'log'] }],
      });
      if (path) {
        await writeTextFile(path, logLines.join('\n'));
      }
    } catch (e) {
      console.error('Failed to save log:', e);
    }
  }
</script>

<div class="view-container">
  <!-- Header always visible -->
  <header class="view-header">
    <div class="header-top">
      <button class="back-btn" onclick={() => onNavigate?.('dashboard')} title="Back to Dashboard">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="14" y1="8" x2="2" y2="8" />
          <polyline points="7,3 2,8 7,13" />
        </svg>
      </button>
      <h2>Sync Panel</h2>
      {#if phase !== 'options'}
        <div class="header-badge">
          <span class="direction-badge" class:push={direction === 'push'} class:pull={direction === 'pull'}>
            {#if direction === 'push'}
              Push {'\u2192'}
            {:else}
              {'\u2190'} Pull
            {/if}
          </span>
          <span class="sync-type-badge">{syncType}</span>
        </div>
      {/if}
    </div>
    <p class="subtitle">
      {#if $selectedSite}
        {#if direction === 'push'}
          Pushing local changes to <strong>{siteName}</strong>
        {:else}
          Pulling from <strong>{siteName}</strong> to local
        {/if}
      {:else}
        No site selected
      {/if}
    </p>
  </header>

  <!-- ===== State 1: Pre-sync Options ===== -->
  {#if phase === 'options'}
    <div class="options-panel">
      <!-- Direction -->
      <div class="option-group">
        <span class="option-label">Direction</span>
        <div class="radio-group">
          <label class="radio-option" class:selected={direction === 'pull'}>
            <input type="radio" bind:group={direction} value="pull" />
            <span class="radio-icon">{'\u2190'}</span>
            Pull (Live to Local)
          </label>
          <label class="radio-option" class:selected={direction === 'push'}>
            <input type="radio" bind:group={direction} value="push" />
            <span class="radio-icon">{'\u2192'}</span>
            Push (Local to Live)
          </label>
        </div>
      </div>

      <!-- Sync Type -->
      <div class="option-group">
        <span class="option-label">Sync Type</span>
        <div class="radio-group">
          <label class="radio-option" class:selected={syncType === 'full'}>
            <input type="radio" bind:group={syncType} value="full" />
            Full Sync
          </label>
          <label class="radio-option" class:selected={syncType === 'files-only'}>
            <input type="radio" bind:group={syncType} value="files-only" />
            Files Only
          </label>
          <label class="radio-option" class:selected={syncType === 'db-only'}>
            <input type="radio" bind:group={syncType} value="db-only" />
            Database Only
          </label>
        </div>
      </div>

      <!-- Options -->
      <div class="option-group">
        <span class="option-label">Options</span>
        <div class="checkbox-group">
          <label class="checkbox-option">
            <input type="checkbox" bind:checked={skipDryRun} />
            Skip Dry Run
          </label>
          <label class="checkbox-option">
            <input type="checkbox" bind:checked={skipValidation} />
            Skip Validation
          </label>
          <label class="checkbox-option">
            <input type="checkbox" bind:checked={skipWpCheck} />
            Skip WP Check
          </label>
          <label class="checkbox-option">
            <input type="checkbox" bind:checked={noBackup} />
            Skip File Backup (no safety copies)
          </label>
        </div>
      </div>

      <!-- Safety & Backup Panel -->
      <div class="safety-panel" class:push={direction === 'push'} class:pull={direction === 'pull'}>
        <div class="safety-header">
          <span class="safety-icon" class:push={direction === 'push'}>
            {#if direction === 'push'}!{:else}i{/if}
          </span>
          <div class="safety-text">
            {#if direction === 'push'}
              <strong>Push will overwrite files and database on the live server.</strong>
              <p>The destination (live) will be modified. Verify your backup settings below.</p>
            {:else}
              <strong>Pull will overwrite your local files and database.</strong>
              <p>The destination (local) will be modified. Verify your backup settings below.</p>
            {/if}
          </div>
        </div>

        <!-- Backup Status Indicators -->
        <div class="backup-status-section">
          <div class="backup-status-row">
            <div class="backup-indicator" class:enabled={fileBackupEnabled} class:disabled={!fileBackupEnabled}>
              <span class="indicator-icon">{fileBackupEnabled ? '\u2713' : '\u2717'}</span>
              <span class="indicator-label">File Backup</span>
              <span class="indicator-value">{fileBackupEnabled ? 'Enabled' : 'Disabled'}</span>
              {#if noBackup && fileBackupEnabled}
                <span class="indicator-override">Overridden by "Skip File Backup" option above</span>
              {/if}
            </div>
            <div class="backup-indicator" class:enabled={dbBackupEnabled} class:disabled={!dbBackupEnabled}>
              <span class="indicator-icon">{dbBackupEnabled ? '\u2713' : '\u2717'}</span>
              <span class="indicator-label">Database Backup</span>
              <span class="indicator-value">{dbBackupEnabled ? 'Auto before DB reset' : 'Disabled'}</span>
            </div>
          </div>

          {#if !backupConfigured}
            <p class="backup-warning-text">
              No automatic backups are configured. Consider enabling them before syncing.
            </p>
          {/if}

          <div class="backup-actions">
            <button
              class="btn btn-backup"
              onclick={() => onNavigate?.(`config:${$selectedSite}:backup`)}
              title="Open Backup settings"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M8.5 1.5l2 2L4 10H2v-2l6.5-6.5z" />
              </svg>
              Backup Settings
            </button>
            <button
              class="btn btn-backup-now"
              onclick={takeBackupNow}
              disabled={backupInProgress || !$selectedSite}
              title="Export the destination database right now before syncing"
            >
              {#if backupInProgress}
                <span class="mini-spinner"></span>
                Backing up...
              {:else}
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M6 1v7M3 5l3 3 3-3" />
                  <line x1="2" y1="10" x2="10" y2="10" />
                </svg>
                Backup DB Now
              {/if}
            </button>
          </div>

          {#if backupResult}
            <div class="backup-result" class:success={backupResult.success} class:error={!backupResult.success}>
              <span>{backupResult.success ? '\u2713' : '\u2717'}</span>
              <span class="backup-result-text">{backupResult.message}</span>
            </div>
          {/if}
        </div>
      </div>

      <button
        class="btn btn-primary start-btn"
        disabled={!$selectedSite}
        onclick={startSync}
      >
        {skipDryRun ? 'Start Sync' : 'Start Dry Run'}
      </button>
    </div>

  <!-- ===== State 2: Dry Run in Progress ===== -->
  {:else if phase === 'dry-run'}
    <div class="dry-run-panel">
      {#if !dryRunError && dryRunEntries.length === 0}
        <div class="loading-section">
          <div class="spinner"></div>
          <p>Running dry run...</p>
        </div>
      {/if}

      {#if dryRunError}
        <div class="error-banner">
          <span class="error-icon">{'\u2717'}</span>
          <div>
            <strong>Dry run failed</strong>
            <p>{dryRunError}</p>
          </div>
        </div>
      {/if}

      <LogOutput lines={dryRunOutput} />

      <div class="dry-run-actions">
        {#if activeChild}
          <button class="btn btn-danger" onclick={cancelDryRun}>
            Cancel
          </button>
        {:else}
          <button class="btn btn-secondary" onclick={returnToOptions}>
            Back
          </button>
        {/if}
        {#if dryRunEntries.length === 0 && !dryRunError && dryRunOutput.length > 1 && !activeChild}
          <p class="no-changes-msg">No changes detected. Nothing to sync.</p>
        {/if}
      </div>
    </div>

  <!-- ===== State 3: Diff Viewer ===== -->
  {:else if phase === 'diff-viewer'}
    <div class="diff-panel">
      <DiffViewer
        entries={dryRunEntries}
        onproceed={handleDiffProceed}
        oncancel={handleDiffCancel}
      />
    </div>

  <!-- ===== State 4: Sync in Progress ===== -->
  {:else if phase === 'syncing'}
    <div class="sync-progress-panel">
      <StepTracker steps={syncSteps} />

      {#if rsyncProgress}
        <div class="progress-section">
          <div class="progress-bar-container">
            <div
              class="progress-bar-fill"
              style="width: {rsyncProgress.percent}%"
            ></div>
          </div>
          <div class="progress-info">
            <span>{rsyncProgress.percent}%</span>
            <span>{rsyncProgress.speed}</span>
            <span>ETA: {rsyncProgress.eta}</span>
          </div>
        </div>
      {/if}

      <LogOutput lines={logLines} />

      <div class="sync-actions">
        <button class="btn btn-danger" onclick={cancelSync}>
          Cancel Sync
        </button>
      </div>
    </div>

  <!-- ===== State 5: Complete ===== -->
  {:else if phase === 'complete'}
    <div class="complete-panel">
      <!-- Result Banner -->
      {#if syncResult === 'success'}
        <div class="result-banner success">
          <span class="result-icon">{'\u2713'}</span>
          <div>
            <strong>Sync Completed Successfully</strong>
            <p>Duration: {durationStr} | Files: {filesTransferred}</p>
          </div>
        </div>
      {:else if syncResult === 'failed'}
        <div class="result-banner error">
          <span class="result-icon">{'\u2717'}</span>
          <div>
            <strong>Sync Failed</strong>
            <p>Duration: {durationStr} | Check the log for details.</p>
          </div>
        </div>
      {:else if syncResult === 'cancelled'}
        <div class="result-banner warning">
          <span class="result-icon">!</span>
          <div>
            <strong>Sync Cancelled</strong>
            <p>The sync was stopped before completion.</p>
          </div>
        </div>
      {/if}

      <!-- Log output -->
      <LogOutput lines={logLines} />

      <!-- Actions -->
      <div class="complete-actions">
        <button class="btn btn-secondary" onclick={copyLog}>
          Copy Log
        </button>
        <button class="btn btn-secondary" onclick={saveLog}>
          Save Log
        </button>
        <button class="btn btn-primary" onclick={returnToOptions}>
          Return to Dashboard
        </button>
      </div>
    </div>
  {/if}

  <!-- Interactive Prompt Dialog -->
  {#if pendingPrompt}
    <ConfirmDialog
      message={pendingPrompt.question}
      confirmLabel="Yes"
      cancelLabel="No"
      onconfirm={() => handlePromptResponse(true)}
      oncancel={() => handlePromptResponse(false)}
    />
  {/if}
</div>

<style>
  .view-container {
    padding: 32px;
    max-width: 960px;
  }

  .view-header {
    margin-bottom: 24px;
  }

  .back-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .back-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .header-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 4px;
  }

  .view-header h2 {
    font-size: 24px;
    font-weight: 600;
  }

  .header-badge {
    display: flex;
    gap: 6px;
  }

  .direction-badge,
  .sync-type-badge {
    padding: 2px 10px;
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .direction-badge.push {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }

  .direction-badge.pull {
    background: rgba(34, 197, 94, 0.15);
    color: var(--success);
  }

  .sync-type-badge {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 14px;
  }

  /* ===== Options Panel ===== */
  .options-panel {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .option-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .option-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .radio-group {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .radio-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s ease;
  }

  .radio-option:hover {
    border-color: var(--text-muted);
  }

  .radio-option.selected {
    border-color: var(--accent);
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .radio-option input {
    display: none;
  }

  .radio-icon {
    font-size: 16px;
    font-weight: 700;
  }

  .checkbox-group {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .checkbox-option {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .checkbox-option input {
    width: 15px;
    height: 15px;
    accent-color: var(--accent);
    cursor: pointer;
  }

  /* ===== Safety & Backup Panel ===== */
  .safety-panel {
    border-radius: var(--radius-md);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .safety-panel.push {
    background: rgba(234, 179, 8, 0.08);
    border: 1px solid rgba(234, 179, 8, 0.25);
  }

  .safety-panel.pull {
    background: rgba(59, 130, 246, 0.06);
    border: 1px solid rgba(59, 130, 246, 0.2);
  }

  .safety-header {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  .safety-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    font-weight: 700;
    font-size: 13px;
    flex-shrink: 0;
    background: rgba(59, 130, 246, 0.15);
    color: var(--accent);
  }

  .safety-icon.push {
    background: rgba(234, 179, 8, 0.2);
    color: var(--warning);
  }

  .safety-text {
    font-size: 13px;
    line-height: 1.4;
  }

  .safety-text strong {
    display: block;
    margin-bottom: 2px;
  }

  .safety-panel.push .safety-text {
    color: var(--warning);
  }

  .safety-panel.pull .safety-text {
    color: var(--text-secondary);
  }

  .safety-text p {
    font-size: 12px;
    opacity: 0.85;
  }

  .backup-status-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .backup-status-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .backup-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.04);
  }

  .backup-indicator.enabled .indicator-icon {
    color: var(--success);
    font-weight: 700;
  }

  .backup-indicator.disabled .indicator-icon {
    color: var(--error);
    font-weight: 700;
  }

  .indicator-label {
    font-weight: 600;
    color: var(--text-primary);
  }

  .indicator-value {
    color: var(--text-muted);
    font-size: 11px;
  }

  .indicator-override {
    color: var(--warning);
    font-size: 11px;
    font-style: italic;
    margin-left: auto;
  }

  .backup-warning-text {
    font-size: 12px;
    color: var(--error);
    font-weight: 500;
    padding: 0 2px;
  }

  .backup-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-backup,
  .btn-backup-now {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-backup {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .btn-backup:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .btn-backup-now {
    background: rgba(34, 197, 94, 0.12);
    color: var(--success);
  }

  .btn-backup-now:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.22);
  }

  .btn-backup-now:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .mini-spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 1.5px solid var(--border-color);
    border-top-color: var(--success);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .backup-result {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    font-size: 12px;
    line-height: 1.4;
  }

  .backup-result.success {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  .backup-result.error {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }

  .backup-result-text {
    word-break: break-all;
  }

  .start-btn {
    align-self: flex-start;
    padding: 10px 24px;
    font-size: 14px;
  }

  .btn {
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-primary {
    background: var(--accent);
    color: #fff;
  }

  .btn-primary:hover {
    background: var(--accent-hover);
  }

  .btn-secondary {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .btn-secondary:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .btn-danger {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }

  .btn-danger:hover {
    background: rgba(239, 68, 68, 0.25);
  }

  /* ===== Dry Run Panel ===== */
  .dry-run-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .loading-section {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    color: var(--text-secondary);
    font-size: 14px;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .error-banner {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-md);
    color: var(--error);
    font-size: 13px;
  }

  .error-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(239, 68, 68, 0.2);
    font-weight: 700;
    flex-shrink: 0;
  }

  .dry-run-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .no-changes-msg {
    font-size: 13px;
    color: var(--text-muted);
    font-style: italic;
  }

  /* ===== Sync Progress Panel ===== */
  .sync-progress-panel {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .progress-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .progress-bar-container {
    height: 6px;
    background: var(--bg-input);
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-bar-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .progress-info {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .sync-actions {
    display: flex;
    justify-content: flex-end;
  }

  /* ===== Complete Panel ===== */
  .complete-panel {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .result-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-radius: var(--radius-md);
    font-size: 14px;
  }

  .result-banner.success {
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: var(--success);
  }

  .result-banner.error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: var(--error);
  }

  .result-banner.warning {
    background: rgba(234, 179, 8, 0.1);
    border: 1px solid rgba(234, 179, 8, 0.3);
    color: var(--warning);
  }

  .result-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 18px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .result-banner.success .result-icon {
    background: rgba(34, 197, 94, 0.2);
  }

  .result-banner.error .result-icon {
    background: rgba(239, 68, 68, 0.2);
  }

  .result-banner.warning .result-icon {
    background: rgba(234, 179, 8, 0.2);
  }

  .result-banner strong {
    display: block;
    margin-bottom: 2px;
  }

  .result-banner p {
    font-size: 12px;
    opacity: 0.8;
  }

  .complete-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
</style>
