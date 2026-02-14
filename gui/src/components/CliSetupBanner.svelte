<script lang="ts">
  import { resolveCliPath, installCli, getCliVersion } from '$lib/services/cli';
  import { settings, persistSettings } from '$lib/stores/settings';
  import { onMount } from 'svelte';

  let status = $state<'checking' | 'missing' | 'installing' | 'installed' | 'failed'>('checking');
  let cliPath = $state('');
  let cliVersion = $state('');
  let dismissed = $state(false);

  onMount(async () => {
    await checkCli();
  });

  async function checkCli() {
    status = 'checking';
    const path = await resolveCliPath();
    if (path) {
      cliPath = path;
      const version = await getCliVersion(path);
      cliVersion = version ?? '';
      status = 'installed';
      // Persist to settings
      await persistSettings({ ...$settings, cli_path: path, cli_version: cliVersion });
    } else {
      status = 'missing';
    }
  }

  async function handleInstall() {
    status = 'installing';
    const success = await installCli();
    if (success) {
      // Re-check to get the path
      await checkCli();
    } else {
      status = 'failed';
    }
  }
</script>

{#if !dismissed && status !== 'installed'}
  <div class="cli-banner" class:error={status === 'failed'}>
    {#if status === 'checking'}
      <div class="banner-content">
        <span class="banner-icon spinner-icon"></span>
        <span class="banner-text">Checking for wordpress-sync CLI...</span>
      </div>
    {:else if status === 'missing'}
      <div class="banner-content">
        <span class="banner-icon warn-icon">!</span>
        <div class="banner-body">
          <span class="banner-text"><strong>wordpress-sync CLI not found.</strong> It's required for sync operations.</span>
          <div class="banner-actions">
            <button class="btn-install" onclick={handleInstall}>Install Now</button>
            <button class="btn-dismiss" onclick={() => { dismissed = true; }}>Dismiss</button>
          </div>
        </div>
      </div>
    {:else if status === 'installing'}
      <div class="banner-content">
        <span class="banner-icon spinner-icon"></span>
        <span class="banner-text">Installing wordpress-sync CLI... (see Terminal panel below)</span>
      </div>
    {:else if status === 'failed'}
      <div class="banner-content">
        <span class="banner-icon error-icon">x</span>
        <div class="banner-body">
          <span class="banner-text"><strong>CLI installation failed.</strong> Check the Terminal panel for details.</span>
          <div class="banner-actions">
            <button class="btn-install" onclick={handleInstall}>Retry</button>
            <button class="btn-dismiss" onclick={() => { dismissed = true; }}>Dismiss</button>
          </div>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .cli-banner {
    padding: 12px 24px;
    background: rgba(59, 130, 246, 0.08);
    border-bottom: 1px solid rgba(59, 130, 246, 0.2);
    flex-shrink: 0;
  }

  .cli-banner.error {
    background: rgba(239, 68, 68, 0.08);
    border-bottom-color: rgba(239, 68, 68, 0.2);
  }

  .banner-content {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }

  .banner-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .banner-text {
    font-size: 13px;
    color: var(--text-primary);
    line-height: 1.4;
  }

  .banner-icon {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-size: 12px;
    font-weight: 700;
    margin-top: 1px;
  }

  .warn-icon {
    background: var(--warning);
    color: #000;
  }

  .error-icon {
    background: var(--error);
    color: #fff;
  }

  .spinner-icon {
    border: 2px solid var(--border-color);
    border-top-color: var(--accent);
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .banner-actions {
    display: flex;
    gap: 8px;
  }

  .btn-install {
    padding: 6px 16px;
    background: var(--accent);
    color: #fff;
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 600;
    transition: background 0.15s ease;
  }

  .btn-install:hover {
    background: var(--accent-hover);
  }

  .btn-dismiss {
    padding: 6px 16px;
    background: transparent;
    color: var(--text-muted);
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 500;
    transition: all 0.15s ease;
  }

  .btn-dismiss:hover {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }
</style>
