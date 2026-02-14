# Indexing Performance Monitor Enhancement

## Overview
Enhanced the "Indexing Performance Monitor" feature to provide actionable, specific recommendations when bottlenecks are detected, replacing the generic warning message with detailed analysis and remediation steps.

## Changes Made

### File Modified
- `janitor/operations/performance_monitoring.py`

### Key Enhancements

#### 1. Enhanced Data Collection
- Added collection of node resource metrics (CPU, heap usage)
- Calculate rejection rates as percentages for better analysis
- Track thread pool configuration (queue size, thread count)
- Collect indexing throughput data per index

#### 2. New Helper Function: `_display_indexing_recommendations()`
A comprehensive recommendation engine that analyzes bottleneck data and provides:

**Severity-Based Categorization:**
- **Critical** (>100k rejections): Immediate action required
- **Important** (>1k rejections): Short-term action needed  
- **Warning** (>0 rejections): Monitoring recommended

**Root Cause Analysis:**
- Identifies cluster-wide vs. node-specific issues
- Detects high-throughput indices (>15,000 docs/sec)
- Analyzes resource constraints (CPU, heap)

**Actionable Recommendations Include:**

1. **Specific Thread Pool Settings**
   - Calculated recommendations based on node resources
   - Exact Elasticsearch API commands with values
   - Example: `PUT /_cluster/settings` with optimal thread pool sizes

2. **Bulk Indexing Optimization**
   - Batch size recommendations (5-15 MB per request)
   - Python code examples with retry logic
   - Concurrent request tuning

3. **Index-Level Settings**
   - Disable refresh during bulk operations
   - Replica management during indexing
   - Restore settings after completion

4. **Monitoring & Verification**
   - Commands to check thread pool stats
   - Track rejection rates
   - Monitor cluster health
   - Verify indexing performance improvements

5. **Preventive Actions (Long-term)**
   - Cluster scaling recommendations
   - Index Lifecycle Management (ILM) setup
   - Shard strategy optimization
   - Mapping and analysis review

#### 3. Enhanced Bottleneck Table
Added "Rejection Rate" column showing percentage of rejected requests for better visibility.

## Example Output

### Before Enhancement
```
⚠️  Bottlenecks detected! Consider increasing thread pool sizes or reducing indexing rate.
```

### After Enhancement
```
📊 Detailed Bottleneck Analysis & Recommendations

╔══════════════════════════════════════════════════════════════════════════════╗
║                      💡 Actionable Recommendations                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  🚨 CRITICAL ACTIONS (Immediate)                                             ║
║                                                                              ║
║  • Node 'es-node-1' (write pool): 150,000 rejections (2.5% rejection rate)  ║
║    → Increase write thread pool size:                                       ║
║      PUT /_cluster/settings                                                  ║
║      {                                                                       ║
║        "persistent": {                                                       ║
║          "thread_pool.write.size": 12,                                      ║
║          "thread_pool.write.queue_size": 2000                               ║
║        }                                                                     ║
║      }                                                                       ║
║                                                                              ║
║  🔍 ROOT CAUSE ANALYSIS                                                      ║
║                                                                              ║
║  • Issue Type: CLUSTER-WIDE bottleneck                                      ║
║    2 out of 3 nodes are experiencing rejections.                            ║
║    This indicates the entire cluster is under-provisioned.                  ║
║                                                                              ║
║  • High-Throughput Indices Detected:                                        ║
║    - logs-2024.01.15: 18,500 docs/sec                                      ║
║    - metrics-prod: 22,000 docs/sec                                          ║
║                                                                              ║
║  📦 BULK INDEXING OPTIMIZATION                                               ║
║  [... detailed bulk optimization recommendations ...]                        ║
║                                                                              ║
║  ⚙️  INDEX-LEVEL SETTINGS                                                    ║
║  [... index settings recommendations ...]                                    ║
║                                                                              ║
║  📈 MONITORING & VERIFICATION                                                ║
║  [... monitoring commands ...]                                               ║
║                                                                              ║
║  🛡️  PREVENTIVE ACTIONS (Long-term)                                          ║
║  [... long-term recommendations ...]                                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## Technical Details

### Data Flow
1. Fetch indexing stats and node stats (thread_pool, os, jvm)
2. Analyze thread pools for write/bulk rejections
3. Calculate rejection rates and categorize by severity
4. Collect node resource information
5. Identify high-throughput indices
6. Generate context-aware recommendations
7. Display in formatted Rich panel

### Recommendation Logic
- Thread pool size: Based on heap size (heap_gb * 2) + current threads + 4
- Queue size: Double current size or minimum 1000
- Resource constraint detection: CPU >80% or Heap >85%
- Cluster-wide issue: >50% of nodes affected
- High-throughput threshold: >15,000 docs/sec

## Benefits

1. **Actionable**: Provides exact commands and settings to fix issues
2. **Context-Aware**: Recommendations based on actual node resources and load
3. **Prioritized**: Critical, important, and preventive actions clearly separated
4. **Educational**: Explains root causes and long-term strategies
5. **Comprehensive**: Covers immediate fixes, monitoring, and prevention

## Testing Recommendations

To test this feature:
1. Run the Indexing Performance Monitor on a cluster with bottlenecks
2. Verify the recommendations panel appears with detailed analysis
3. Check that rejection rates are calculated correctly
4. Ensure thread pool recommendations are appropriate for node resources
5. Validate that high-throughput indices are identified correctly

## Future Enhancements

Potential improvements:
- Historical trend analysis of rejection rates
- Automated application of recommendations (with confirmation)
- Integration with alerting systems
- Machine learning-based capacity planning
- Export recommendations to runbook format

