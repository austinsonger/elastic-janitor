<script>
  import { bytesToHuman } from '../lib/api.js';

  let { nodes = [] } = $props();

  function cpuColor(pct) {
    if (pct >= 80) return '#f44336';
    if (pct >= 60) return '#ff9800';
    return '#4caf50';
  }

  function heapColor(pct) {
    if (pct >= 85) return '#f44336';
    if (pct >= 70) return '#ff9800';
    return '#4caf50';
  }
</script>

<div class="panel">
  <h2>Node Metrics</h2>
  {#if nodes.length === 0}
    <p class="loading">No node data</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Node</th>
          <th class="right">CPU</th>
          <th class="right">Heap</th>
        </tr>
      </thead>
      <tbody>
        {#each nodes as node}
          <tr>
            <td class="node-name" title={node.name}>{node.name}</td>
            <td class="right" style="color:{cpuColor(node.cpu_percent)}">{node.cpu_percent}%</td>
            <td class="right">
              <span style="color:{heapColor(node.heap_percent)}">{node.heap_percent.toFixed(0)}%</span>
              <span class="sub">({node.heap_used_human})</span>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .panel { background: var(--panel-bg); border-radius: 8px; padding: 1rem 1.25rem; }
  h2 { margin: 0 0 0.75rem; color: var(--accent); font-size: 1rem; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; color: var(--muted); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
  th.right, td.right { text-align: right; }
  td { padding: 0.4rem 0; font-size: 0.9rem; }
  .node-name { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sub { color: var(--muted); font-size: 0.8rem; margin-left: 4px; }
  .loading { color: var(--muted); font-size: 0.85rem; }
</style>
