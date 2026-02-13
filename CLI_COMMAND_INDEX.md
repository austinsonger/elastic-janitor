# Elastic Janitor CLI - Command Index

Quick alphabetical index of all commands. For detailed documentation, see CLI_COMMAND_LIBRARY.md.

---

## A

- `aws analyze-fields` - Analyze field structure from AWS sources
- `aws detect-issues` - Detect common AWS ingestion issues
- `aws health-check` - Check Firehose/Forwarder health
- `aws quality-metrics` - Generate AWS data quality metrics
- `aws quick-fix` - Apply quick fixes for AWS issues
- `aws troubleshoot-pipeline` - Troubleshoot AWS pipelines

## B

- `bulk config export` - Export cluster configurations
- `bulk config import` - Import cluster configurations
- `bulk dry-run` - Manage global dry-run mode
- `bulk history` - View operation history
- `bulk index` - Batch index operations
- `bulk rollback` - Rollback operations
- `bulk schedule` - Manage scheduled jobs

## C

- `cleanup duplicates` - Detect/remove duplicate documents
- `cleanup fields` - Remove fields from documents
- `cleanup gaps` - Detect time-series gaps
- `cleanup mappings` - Clean unused mappings
- `cleanup orphaned-docs` - Clean orphaned documents
- `cleanup wildcard-delete` - Delete indices by wildcard
- `cluster health` - Cluster health overview
- `cluster nodes` - Node information
- `cluster stats` - Cluster statistics

## D

- `dashboard` - Real-time monitoring dashboard
- `dashboard cluster` - Cluster-focused dashboard
- `dashboard export` - Export dashboard data
- `dashboard indices` - Index-focused dashboard
- `dashboard performance` - Performance dashboard
- `datastream clean` - Clean old backing indices
- `datastream clean-standalone` - Clean standalone indices
- `datastream clone` - Clone data stream
- `datastream lifecycle` - View lifecycle status
- `datastream preview` - Preview data stream structure
- `datastream reindex` - Reindex backing indices
- `datastream rotate` - Rotate write index
- `datastream stats` - Data stream statistics
- `dry-run disable` - Disable dry-run mode
- `dry-run enable` - Enable dry-run mode
- `dry-run status` - Check dry-run status

## I

- `index alias` - Manage index aliases
- `index duplicates` - Detect duplicate indices
- `index health` - Index health dashboard
- `index largest` - List largest indices
- `index migrate` - Migrate between tiers
- `index optimize` - Optimize index segments
- `index rollover` - Check rollover status
- `index settings` - View index settings
- `index shards` - Shard analysis

## P

- `performance hotspots` - Detect performance hot spots
- `performance indexing` - Monitor indexing performance
- `performance nodes` - Monitor node resources
- `performance search` - Search performance dashboard
- `performance slow-queries` - Analyze slow queries
- `performance timeline` - Cluster health timeline
- `pipeline clone` - Clone ingest pipeline
- `pipeline delete` - Delete pipelines
- `pipeline edit` - Edit pipeline with version control
- `pipeline emergency-rollback` - Emergency rollback
- `pipeline export` - Export pipelines
- `pipeline history` - View version history
- `pipeline import` - Import pipelines
- `pipeline list` - List ingest pipelines
- `pipeline rollback` - Rollback pipeline
- `pipeline view` - View pipeline details
- `policy ilm assign` - Assign ILM policy
- `policy ilm delete` - Delete ILM policies
- `policy ilm effectiveness` - Policy effectiveness report
- `policy ilm list` - List ILM policies
- `policy ilm simulate` - Simulate ILM policy
- `policy ilm view` - View ILM policy details

## Q

- `quality cardinality` - Analyze field cardinality
- `quality missing-fields` - Analyze missing fields
- `quality null-stats` - Null value statistics
- `quality resolve-conflicts` - Resolve mapping conflicts
- `quality type-inconsistency` - Detect type inconsistencies

## S

- `snapshot analyze` - Analyze snapshot sizes
- `snapshot cleanup` - Automated snapshot cleanup
- `snapshot compare` - Compare snapshots
- `snapshot copy` - Copy between repositories
- `snapshot delete` - Delete old snapshots
- `snapshot list` - List snapshots
- `snapshot repo list` - List repositories
- `snapshot restore` - Restore snapshot
- `snapshot slm delete` - Delete SLM policies
- `snapshot slm list` - List SLM policies
- `snapshot verify` - Verify repository
- `storage cleanup-empty` - Clean empty indices
- `storage compression` - Compression analysis
- `storage cost` - Cost estimator
- `storage forecast` - Storage forecast
- `storage sparse` - Detect sparse indices
- `storage tiers` - Tier distribution report

## T

- `template component delete` - Delete component templates
- `template component edit` - Edit component template
- `template component export` - Export component templates
- `template component import` - Import component templates
- `template component list` - List component templates
- `template component rollback` - Rollback component template
- `template component view` - View component template
- `template conflicts` - Detect template conflicts
- `template dependencies` - View resource dependencies
- `template index delete` - Delete index templates
- `template index edit` - Edit index template
- `template index export` - Export index templates
- `template index import` - Import index templates
- `template index list` - List index templates
- `template index rollback` - Rollback index template
- `template index view` - View index template
- `template inheritance` - View template inheritance
- `template rollback-deps` - Rollback with dependencies
- `template unused` - Find unused templates

---

## Command Count by Category

| Category | Commands | Percentage |
|----------|----------|------------|
| Template & Policy Management | 35 | 23% |
| Snapshot & Backup | 15 | 10% |
| Index Management | 9 | 6% |
| Data Stream Management | 8 | 5% |
| Performance & Monitoring | 6 | 4% |
| Storage & Cost Optimization | 6 | 4% |
| Bulk Operations & Automation | 6 | 4% |
| Advanced Cleanup | 6 | 4% |
| AWS Ingestion Management | 6 | 4% |
| Data Quality & Validation | 5 | 3% |
| Dashboard & Stats | 5 | 3% |
| Cluster Health & Diagnostics | 3 | 2% |
| Global Dry-Run Mode | 3 | 2% |
| **Total** | **113** | **100%** |

---

## Most Used Commands (Estimated)

1. `cluster health` - Daily health checks
2. `datastream clean` - Regular cleanup
3. `index largest` - Capacity planning
4. `snapshot delete` - Backup management
5. `dashboard` - Monitoring
6. `dry-run enable/disable` - Safety
7. `pipeline edit` - Configuration changes
8. `storage cost` - Cost optimization
9. `performance slow-queries` - Performance tuning
10. `quality missing-fields` - Data quality

---

## Commands by Use Case

### Daily Operations
- `cluster health`
- `dashboard`
- `datastream clean`
- `snapshot delete`
- `storage cleanup-empty`

### Troubleshooting
- `index health`
- `performance slow-queries`
- `performance hotspots`
- `aws detect-issues`
- `quality type-inconsistency`

### Configuration Management
- `template index list/view/edit`
- `pipeline edit/rollback`
- `policy ilm list/view`
- `bulk config export/import`

### Cost Optimization
- `storage cost`
- `storage forecast`
- `storage tiers`
- `index migrate`
- `storage compression`

### Data Quality
- `quality missing-fields`
- `quality null-stats`
- `quality cardinality`
- `cleanup duplicates`
- `quality resolve-conflicts`

---

**For detailed command documentation, see CLI_COMMAND_LIBRARY.md**

