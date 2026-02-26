<script>
  import { formatNumber } from '../lib/api.js';

  let { totalDocsIndexed = 0, totalQueries = 0 } = $props();
</script>

<div class="panel">
  <h2>Performance Metrics</h2>
  <div class="metrics">
    <div class="metric">
      <span class="value">{formatNumber(totalDocsIndexed)}</span>
      <span class="label">Total Docs Indexed</span>
    </div>
    <div class="metric">
      <span class="value">{formatNumber(totalQueries)}</span>
      <span class="label">Total Queries</span>
    </div>
  </div>
</div>

<style>
  .panel { background: var(--panel-bg); border-radius: 8px; padding: 1rem 1.25rem; }
  h2 { margin: 0 0 0.75rem; color: var(--accent); font-size: 1rem; }
  .metrics { display: flex; gap: 2rem; }
  .metric { display: flex; flex-direction: column; }
  .value { font-size: 1.5rem; font-weight: 700; color: var(--text); }
  .label { font-size: 0.8rem; color: var(--muted); margin-top: 0.2rem; }
</style>
