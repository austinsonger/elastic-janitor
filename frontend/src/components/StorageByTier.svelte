<script>
  import { fetchStorage, bytesToHuman } from '../lib/api.js';

  let data = $state(null);
  let error = $state(null);

  async function poll() {
    const res = await fetchStorage();
    data = res.data;
    error = res.error;
  }

  $effect(() => {
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  });

  function tierColor(name) {
    const colors = { hot: '#f44336', warm: '#ff9800', cold: '#2196f3', frozen: '#9c27b0' };
    return colors[name] || '#9e9e9e';
  }
</script>

<div class="panel">
  <h2>Storage by Tier</h2>
  {#if error}
    <p class="error">{error}</p>
  {:else if data}
    {#if data.tiers.length === 0}
      <p class="loading">No tier data available</p>
    {:else}
      <table>
        <thead>
          <tr><th>Tier</th><th class="right">Size</th></tr>
        </thead>
        <tbody>
          {#each data.tiers as tier}
            <tr>
              <td>
                <span class="dot" style="background:{tierColor(tier.name)}"></span>
                {tier.name.charAt(0).toUpperCase() + tier.name.slice(1)}
              </td>
              <td class="right">{bytesToHuman(tier.size_bytes)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {:else}
    <p class="loading">Loading...</p>
  {/if}
</div>

<style>
  .panel { background: var(--panel-bg); border-radius: 8px; padding: 1rem 1.25rem; }
  h2 { margin: 0 0 0.75rem; color: var(--accent); font-size: 1rem; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; color: var(--muted); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
  th.right, td.right { text-align: right; }
  td { padding: 0.35rem 0; font-size: 0.9rem; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .error { color: #f44336; font-size: 0.85rem; }
  .loading { color: var(--muted); font-size: 0.85rem; }
</style>
