<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import type { SiteConfig } from '$lib/types';
  import { termExec, termInfo, terminalOpen } from '$lib/stores/terminal';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();
  let testing = $state(false);
  let testResult = $state<'idle' | 'success' | 'error'>('idle');

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
    <span class="separator-label">Sudo (Optional)</span>
  </div>

  <div class="field">
    <label for="sudo-user">Sudo User</label>
    <input
      id="sudo-user"
      type="text"
      value={config.ssh.sudo?.user ?? ''}
      oninput={(e) => updateSudo('user', e.currentTarget.value)}
      placeholder="Optional sudo user"
    />
  </div>

  <div class="field">
    <label for="sudo-key">Sudo Key Path</label>
    <div class="input-with-button">
      <input
        id="sudo-key"
        type="text"
        value={config.ssh.sudo?.key_path ?? ''}
        oninput={(e) => updateSudo('key_path', e.currentTarget.value)}
        placeholder="Optional sudo key"
      />
      <button type="button" class="btn-browse" onclick={browseSudoKeyPath}>Browse</button>
    </div>
  </div>
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
</style>
