<script lang="ts">
  import type { SiteConfig } from '$lib/types';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  function updateDomain(env: 'staging' | 'live', protocol: 'http' | 'https', value: string) {
    const other = protocol === 'https' ? 'http' : 'https';
    const currentOther = config.domains[env][other];
    const newEnvDomains = { ...config.domains[env], [protocol]: value };

    // Auto-fill: if the other field is empty or matches the auto-generated pattern, update it
    if (protocol === 'https' && value) {
      const autoHttp = value.replace(/^https:\/\//, 'http://');
      if (!currentOther || currentOther === autoHttp.replace('http://', 'https://').replace('https://', 'http://') || currentOther === '') {
        newEnvDomains[other] = autoHttp;
      }
    } else if (protocol === 'http' && value) {
      const autoHttps = value.replace(/^http:\/\//, 'https://');
      if (!currentOther || currentOther === autoHttps.replace('https://', 'http://').replace('http://', 'https://') || currentOther === '') {
        newEnvDomains[other] = autoHttps;
      }
    }

    onchange({
      ...config,
      domains: { ...config.domains, [env]: newEnvDomains }
    });
  }
</script>

<div class="domains-grid">
  <div class="domain-group">
    <h4 class="group-label">Staging</h4>
    <div class="field">
      <label for="staging-https">HTTPS URL</label>
      <input
        id="staging-https"
        type="text"
        value={config.domains.staging.https}
        oninput={(e) => updateDomain('staging', 'https', e.currentTarget.value)}
        placeholder="https://staging.example.com"
      />
    </div>
    <div class="field">
      <label for="staging-http">HTTP URL</label>
      <input
        id="staging-http"
        type="text"
        value={config.domains.staging.http}
        oninput={(e) => updateDomain('staging', 'http', e.currentTarget.value)}
        placeholder="http://staging.example.com"
      />
    </div>
  </div>

  <div class="domain-group">
    <h4 class="group-label">Live</h4>
    <div class="field">
      <label for="live-https">HTTPS URL</label>
      <input
        id="live-https"
        type="text"
        value={config.domains.live.https}
        oninput={(e) => updateDomain('live', 'https', e.currentTarget.value)}
        placeholder="https://example.com"
      />
    </div>
    <div class="field">
      <label for="live-http">HTTP URL</label>
      <input
        id="live-http"
        type="text"
        value={config.domains.live.http}
        oninput={(e) => updateDomain('live', 'http', e.currentTarget.value)}
        placeholder="http://example.com"
      />
    </div>
  </div>
</div>

<style>
  .domains-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    padding-top: 12px;
  }

  .domain-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .group-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border-color);
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
</style>
