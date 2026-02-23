<script lang="ts">
  import { onMount } from 'svelte';
  import { open } from '@tauri-apps/plugin-dialog';
  import type { SiteConfig } from '$lib/types';
  import { termExec, termInfo, terminalOpen } from '$lib/stores/terminal';
  import { storeSudoPassword, getSudoPassword, deleteSudoPassword } from '$lib/services/keychain';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
    siteName?: string;
  }

  let { config, onchange, siteName }: Props = $props();
  let testing = $state(false);
  let testResult = $state<'idle' | 'success' | 'error'>('idle');

  // Whether to show the sudo SSH key override field
  // Auto-open if a custom sudo key is already configured (and differs from the main key)
  let showSudoKeyOverride = $state(false);
  $effect(() => {
    const sudoKey = config.ssh.sudo?.key_path;
    const mainKey = config.ssh.key_path;
    if (sudoKey && sudoKey !== mainKey) {
      showSudoKeyOverride = true;
    }
  });

  // Sudo password state (stored in macOS Keychain, not in YAML config)
  let sudoPasswordValue = $state('');
  let sudoPasswordStored = $state(false);
  let sudoPasswordVisible = $state(false);
  let sudoPasswordSaving = $state(false);
  let sudoPasswordMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load Keychain state on mount
  onMount(async () => {
    if (siteName) {
      try {
        const existing = await getSudoPassword(siteName);
        if (existing) {
          sudoPasswordStored = true;
          // Don't populate the field with the real password — show placeholder
        }
      } catch {
        // Keychain not available — not fatal
      }
    }
  });

  async function saveSudoPassword() {
    if (!siteName || !sudoPasswordValue) return;
    sudoPasswordSaving = true;
    sudoPasswordMessage = null;
    try {
      await storeSudoPassword(siteName, sudoPasswordValue);
      sudoPasswordStored = true;
      sudoPasswordValue = '';
      sudoPasswordVisible = false;
      sudoPasswordMessage = { type: 'success', text: 'Saved to Keychain' };
      setTimeout(() => { sudoPasswordMessage = null; }, 3000);
    } catch (e) {
      sudoPasswordMessage = { type: 'error', text: `Failed: ${e}` };
    }
    sudoPasswordSaving = false;
  }

  async function clearSudoPassword() {
    if (!siteName) return;
    try {
      await deleteSudoPassword(siteName);
      sudoPasswordStored = false;
      sudoPasswordValue = '';
      sudoPasswordMessage = { type: 'success', text: 'Removed from Keychain' };
      setTimeout(() => { sudoPasswordMessage = null; }, 3000);
    } catch (e) {
      sudoPasswordMessage = { type: 'error', text: `Failed: ${e}` };
    }
  }

  function update<K extends keyof SiteConfig['ssh']>(key: K, value: SiteConfig['ssh'][K]) {
    onchange({ ...config, ssh: { ...config.ssh, [key]: value } });
  }

  function updateSudo(key: 'user' | 'key_path', value: string) {
    onchange({
      ...config,
      ssh: {
        ...config.ssh,
        sudo: { ...config.ssh.sudo, [key]: value }
      }
    });
  }

  async function browseKeyPath() {
    const selected = await open({
      multiple: false,
      title: 'Select SSH Key',
      directory: false
    });
    if (selected) {
      update('key_path', selected as string);
    }
  }

  async function browseSudoKeyPath() {
    const selected = await open({
      multiple: false,
      title: 'Select Sudo SSH Key',
      directory: false
    });
    if (selected) {
      updateSudo('key_path', selected as string);
    }
  }

  async function testConnection() {
    const { user, host, port, key_path } = config.ssh;
    if (!user || !host) {
      termInfo('SSH user and host are required to test connection.');
      terminalOpen.set(true);
      return;
    }

    testing = true;
    testResult = 'idle';
    terminalOpen.set(true);

    // Build SSH command
    const parts = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=accept-new'];
    if (key_path) parts.push('-i', `"${key_path}"`);
    if (port && port !== 22) parts.push('-p', String(port));
    parts.push(`${user}@${host}`, 'echo "Connection successful"');

    const displayCmd = `ssh ${user}@${host}${port !== 22 ? ` -p ${port}` : ''} echo "Connection successful"`;
    const actualCmd = parts.join(' ');

    const result = await termExec(displayCmd, actualCmd);
    testResult = result.code === 0 ? 'success' : 'error';
    testing = false;

    // Reset status indicator after 5 seconds
    setTimeout(() => { testResult = 'idle'; }, 5000);
  }
</script>

<div class="form-grid">
  <div class="field">
    <label for="ssh-user">SSH User</label>
    <input
      id="ssh-user"
      type="text"
      value={config.ssh.user}
      oninput={(e) => update('user', e.currentTarget.value)}
      placeholder="root"
    />
  </div>

  <div class="field">
    <label for="ssh-host">SSH Host</label>
    <input
      id="ssh-host"
      type="text"
      value={config.ssh.host}
      oninput={(e) => update('host', e.currentTarget.value)}
      placeholder="example.com"
    />
  </div>

  <div class="field">
    <label for="ssh-port">SSH Port</label>
    <input
      id="ssh-port"
      type="number"
      value={config.ssh.port}
      oninput={(e) => update('port', parseInt(e.currentTarget.value) || 22)}
      placeholder="22"
    />
  </div>

  <div class="field full-width">
    <label for="ssh-key">SSH Key Path</label>
    <div class="input-with-button">
      <input
        id="ssh-key"
        type="text"
        value={config.ssh.key_path}
        oninput={(e) => update('key_path', e.currentTarget.value)}
        placeholder="~/.ssh/id_rsa"
      />
      <button type="button" class="btn-browse" onclick={browseKeyPath}>Browse</button>
    </div>
  </div>

  <div class="field full-width action-row">
    <button type="button" class="btn-action" onclick={testConnection} disabled={testing}>
      {#if testing}
        Testing...
      {:else}
        Test Connection
      {/if}
    </button>
    {#if testResult === 'success'}
      <span class="result-badge success">Connected</span>
    {:else if testResult === 'error'}
      <span class="result-badge error">Failed</span>
    {/if}
  </div>

  <div class="field-separator full-width">
    <span class="separator-label">Elevated Permissions (Optional)</span>
  </div>

  <div class="field full-width">
    <label for="sudo-user">Sudo User</label>
    <input
      id="sudo-user"
      type="text"
      value={config.ssh.sudo?.user ?? ''}
      oninput={(e) => updateSudo('user', e.currentTarget.value)}
      placeholder="e.g. admin-user"
    />
    <span class="field-hint">
      A separate SSH user with sudo privileges, used for chown/chmod after file transfers.
      Leave blank if the primary SSH user already has the necessary permissions.
    </span>
  </div>

  {#if config.ssh.sudo?.user}
    <!-- SSH Key override (collapsed by default) -->
    <div class="field full-width">
      {#if showSudoKeyOverride}
        <label for="sudo-key">SSH Key for Sudo User</label>
        <div class="input-with-button">
          <input
            id="sudo-key"
            type="text"
            value={config.ssh.sudo?.key_path ?? ''}
            oninput={(e) => updateSudo('key_path', e.currentTarget.value)}
            placeholder={config.ssh.key_path || '~/.ssh/id_rsa'}
          />
          <button type="button" class="btn-browse" onclick={browseSudoKeyPath}>Browse</button>
          <button
            type="button"
            class="btn-browse"
            onclick={() => { showSudoKeyOverride = false; updateSudo('key_path', ''); }}
            title="Use the same key as the primary SSH user"
          >
            Reset
          </button>
        </div>
        <span class="field-hint">
          This key is used to authenticate as the sudo user via SSH.
          Click Reset to inherit the primary SSH key above.
        </span>
      {:else}
        <button
          type="button"
          class="btn-link"
          onclick={() => { showSudoKeyOverride = true; }}
        >
          Use a different SSH key for this user
        </button>
        <span class="field-hint">
          By default, the sudo user authenticates with the same SSH key as the primary user ({config.ssh.key_path || '~/.ssh/id_rsa'}).
        </span>
      {/if}
    </div>

    <!-- Sudo Password (Keychain) -->
    <div class="field full-width sudo-password-field">
      <label for="sudo-password">Sudo Password</label>
      {#if sudoPasswordStored}
        <div class="stored-password-row">
          <span class="stored-badge">Stored in Keychain</span>
          <button type="button" class="btn-sm btn-danger" onclick={clearSudoPassword}>Remove</button>
          {#if sudoPasswordMessage}
            <span class="inline-message" class:success={sudoPasswordMessage.type === 'success'} class:error={sudoPasswordMessage.type === 'error'}>
              {sudoPasswordMessage.text}
            </span>
          {/if}
        </div>
      {:else}
        <div class="input-with-button">
          <input
            id="sudo-password"
            type={sudoPasswordVisible ? 'text' : 'password'}
            bind:value={sudoPasswordValue}
            placeholder="Enter password, then save to Keychain"
          />
          <button
            type="button"
            class="btn-browse"
            onclick={() => { sudoPasswordVisible = !sudoPasswordVisible; }}
            title={sudoPasswordVisible ? 'Hide' : 'Show'}
          >
            {sudoPasswordVisible ? 'Hide' : 'Show'}
          </button>
          <button
            type="button"
            class="btn-action btn-save-pw"
            onclick={saveSudoPassword}
            disabled={!sudoPasswordValue || sudoPasswordSaving || !siteName}
          >
            {sudoPasswordSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
        {#if sudoPasswordMessage}
          <span class="inline-message" class:success={sudoPasswordMessage.type === 'success'} class:error={sudoPasswordMessage.type === 'error'}>
            {sudoPasswordMessage.text}
          </span>
        {/if}
      {/if}
      <span class="field-hint">
        Required if this user needs a password for sudo. Not needed if NOPASSWD is configured in sudoers.
        Stored securely in the macOS Keychain -- never written to config files.
      </span>
    </div>
  {/if}
</div>

<style>
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    padding-top: 12px;
  }

  .full-width {
    grid-column: 1 / -1;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .field input {
    width: 100%;
  }

  .input-with-button {
    display: flex;
    gap: 8px;
  }

  .input-with-button input {
    flex: 1;
  }

  .btn-browse {
    padding: 8px 16px;
    background: var(--bg-hover);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    transition: all 0.15s ease;
  }

  .btn-browse:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .btn-action {
    padding: 8px 20px;
    background: var(--accent);
    color: #fff;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 600;
    transition: background 0.15s ease;
    width: auto;
    align-self: flex-start;
  }

  .btn-action:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .btn-action:disabled {
    opacity: 0.6;
    cursor: wait;
  }

  .action-row {
    flex-direction: row !important;
    align-items: center;
    gap: 12px !important;
  }

  .result-badge {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: var(--radius-sm);
  }

  .result-badge.success {
    color: var(--success);
    background: rgba(34, 197, 94, 0.1);
  }

  .result-badge.error {
    color: var(--error);
    background: rgba(239, 68, 68, 0.1);
  }

  .field-separator {
    border-top: 1px solid var(--border-color);
    padding-top: 12px;
    margin-top: 4px;
  }

  .separator-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .sudo-password-field {
    padding: 12px 14px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
  }

  .stored-password-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .stored-badge {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: var(--radius-sm);
    color: var(--success);
    background: rgba(34, 197, 94, 0.1);
  }

  .btn-sm {
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-danger {
    color: var(--error);
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.2);
  }

  .btn-danger:hover {
    background: rgba(239, 68, 68, 0.15);
  }

  .btn-save-pw {
    padding: 8px 16px;
    font-size: 13px;
  }

  .inline-message {
    font-size: 12px;
    font-weight: 500;
  }

  .inline-message.success {
    color: var(--success);
  }

  .inline-message.error {
    color: var(--error);
  }

  .field-hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
    margin-top: 2px;
  }

  .btn-link {
    background: none;
    border: none;
    color: var(--accent);
    font-size: 12px;
    font-weight: 500;
    padding: 0;
    cursor: pointer;
    text-align: left;
  }

  .btn-link:hover {
    text-decoration: underline;
  }
</style>
