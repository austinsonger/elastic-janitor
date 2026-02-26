<script>
  import { fetchClusterHealth } from '../lib/api.js';

  let data = $state(null);
  let error = $state(null);

  async function poll() {
    const res = await fetchClusterHealth();
    data = res.data;
    error = res.error;
  }

  $effect(() => {
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  });

  function statusColor(status) {
    if (status === 'green') return '#4caf50';
    if (status === 'yellow') return '#ff9800';
    if (status === 'red') return '#f44336';
    return '#9e9e9e';
  }
</script>

<div class="panel">
  <h2>Cluster Health</h2>
  {#if error}
    <p class="error">{error}</p>
  {:else if data}
    <table>
      <tbody>
        <tr>
          <td class="label">Status</td>
          <td>
            <span class="dot" style="background:{statusColor(data.status)}"></span>
            {data.status?.toUpperCase()}
          </td>
        </tr>
        <tr><td class="label">Cluster</td><td>{data.cluster_name}</td></tr>
        <tr><td class="label">Nodes</td><td>{data.number_of_nodes}</td></tr>
        <tr><td class="label">Data Nodes</td><td>{data.number_of_data_nodes}</td></tr>
        <tr><td class="label">Active Shards</td><td>{data.active_shards}</td></tr>
        <tr><td class="label">Unassigned</td><td class:warn={data.unassigned_shards > 0}>{data.unassigned_shards}</td></tr>
      </tbody>
    </table>
  {:else}
    <p class="loading">Loading...</p>
  {/if}
</div>

<style>
  .panel { background: var(--panel-bg); border-radius: 8px; padding: 1rem 1.25rem; }
  h2 { margin: 0 0 0.75rem; color: var(--accent); font-size: 1rem; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 0.35rem 0; font-size: 0.9rem; }
  .label { color: var(--muted); width: 45%; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .warn { color: #f44336; font-weight: bold; }
  .error { color: #f44336; font-size: 0.85rem; }
  .loading { color: var(--muted); font-size: 0.85rem; }
</style>
