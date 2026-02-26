<script>
  import { fetchDashboard } from './lib/api.js';
  import ClusterHealth from './components/ClusterHealth.svelte';
  import StorageByTier from './components/StorageByTier.svelte';
  import NodeMetrics from './components/NodeMetrics.svelte';
  import PerformanceMetrics from './components/PerformanceMetrics.svelte';

  let tab = $state('overview');
  let dashData = $state(null);
  let dashError = $state(null);
  let lastUpdate = $state('');

  async function pollDashboard() {
    const res = await fetchDashboard();
    dashData = res.data;
    dashError = res.error;
    lastUpdate = new Date().toLocaleTimeString();
  }

  $effect(() => {
    pollDashboard();
    const id = setInterval(pollDashboard, 3000);
    return () => clearInterval(id);
  });
</script>

<div class="app">
  <header>
    <h1>Elastic Janitor</h1>
    <span class="updated">Last update: {lastUpdate}</span>
  </header>

  <nav>
    <button class:active={tab === 'overview'} onclick={() => tab = 'overview'}>Overview</button>
    <button class:active={tab === 'realtime'} onclick={() => tab = 'realtime'}>Real-Time Metrics</button>
  </nav>

  <main>
    {#if tab === 'overview'}
      <div class="grid two-col">
        <ClusterHealth />
        <StorageByTier />
      </div>
    {:else}
      {#if dashError}
        <div class="panel"><p class="error">{dashError}</p></div>
      {:else if dashData}
        <div class="grid three-panel">
          <div class="panel">
            <h2>Cluster Status</h2>
            <table>
              <tbody>
                <tr>
                  <td class="label">Status</td>
                  <td>
                    <span class="dot" style="background:{dashData.health.status === 'green' ? '#4caf50' : dashData.health.status === 'yellow' ? '#ff9800' : '#f44336'}"></span>
                    {dashData.health.status?.toUpperCase()}
                  </td>
                </tr>
                <tr><td class="label">Nodes</td><td>{dashData.health.number_of_nodes}</td></tr>
                <tr><td class="label">Active Shards</td><td>{dashData.health.active_shards}</td></tr>
                <tr><td class="label">Unassigned</td><td>{dashData.health.unassigned_shards}</td></tr>
              </tbody>
            </table>
          </div>
          <NodeMetrics nodes={dashData.nodes} />
          <PerformanceMetrics
            totalDocsIndexed={dashData.performance.total_docs_indexed}
            totalQueries={dashData.performance.total_queries}
          />
        </div>
      {:else}
        <div class="panel"><p class="loading">Loading...</p></div>
      {/if}
    {/if}
  </main>
</div>

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117;
    color: #e6edf3;
    --panel-bg: #161b22;
    --accent: #58a6ff;
    --muted: #8b949e;
    --text: #e6edf3;
    --border: #30363d;
  }

  .app { max-width: 960px; margin: 0 auto; padding: 1.5rem; }

  header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 1rem; }
  h1 { font-size: 1.25rem; color: var(--accent); }
  .updated { font-size: 0.8rem; color: var(--muted); }

  nav { display: flex; gap: 0.5rem; margin-bottom: 1.25rem; }
  nav button {
    background: var(--panel-bg); border: 1px solid var(--border); color: var(--muted);
    padding: 0.45rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
    transition: all 0.15s;
  }
  nav button:hover { border-color: var(--accent); color: var(--text); }
  nav button.active { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.08); }

  .grid { display: grid; gap: 1rem; }
  .two-col { grid-template-columns: 1fr 1fr; }
  .three-panel { grid-template-columns: 1fr 1fr; }
  .three-panel > :last-child { grid-column: 1 / -1; }

  @media (max-width: 640px) {
    .two-col, .three-panel { grid-template-columns: 1fr; }
    .three-panel > :last-child { grid-column: auto; }
  }

  /* Inline panel styles for the realtime cluster status */
  .panel { background: var(--panel-bg); border-radius: 8px; padding: 1rem 1.25rem; }
  .panel h2 { margin: 0 0 0.75rem; color: var(--accent); font-size: 1rem; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 0.35rem 0; font-size: 0.9rem; }
  .label { color: var(--muted); width: 45%; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .error { color: #f44336; font-size: 0.85rem; }
  .loading { color: var(--muted); font-size: 0.85rem; }
</style>
