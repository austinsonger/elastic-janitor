# Elastic Janitor CLI Command Library

**Version:** 1.0  
**Last Updated:** 2026-02-13

---

## Table of Contents

1. [Introduction](#introduction)
2. [Global Options](#global-options)
3. [Command Naming Convention](#command-naming-convention)
4. [Configuration](#configuration)
5. [Index Management Commands](#1-index-management-commands)
6. [Data Stream Management Commands](#2-data-stream-management-commands)
7. [Template & Policy Management Commands](#3-template--policy-management-commands)
8. [Snapshot & Backup Management Commands](#4-snapshot--backup-management-commands)
9. [Cluster Health & Diagnostics Commands](#5-cluster-health--diagnostics-commands)
10. [Storage & Cost Optimization Commands](#6-storage--cost-optimization-commands)
11. [Performance & Monitoring Commands](#7-performance--monitoring-commands)
12. [Bulk Operations & Automation Commands](#8-bulk-operations--automation-commands)
13. [Advanced Cleanup Commands](#9-advanced-cleanup-commands)
14. [Data Quality & Validation Commands](#10-data-quality--validation-commands)
15. [AWS Ingestion Management Commands](#11-aws-ingestion-management-commands)
16. [Data Quality & Governance Commands](#12-data-quality--governance-commands)
17. [Performance Tuning Commands](#13-performance-tuning-commands)
18. [Dashboard & Stats Commands](#14-dashboard--stats-commands)
19. [Global Dry-Run Mode Commands](#15-global-dry-run-mode-commands)
20. [Error Handling](#error-handling)
21. [Exit Codes](#exit-codes)

---

## Introduction

The Elastic Janitor CLI provides a comprehensive command-line interface for managing, monitoring, and optimizing Elasticsearch clusters. All commands follow a consistent structure and support common flags for safety and flexibility.

---

## Global Options

All commands support the following global options:

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--dry-run` | `-d` | Preview changes without executing | `false` |
| `--verbose` | `-v` | Enable verbose output | `false` |
| `--output` | `-o` | Output format: `json`, `table`, `yaml`, `csv` | `table` |
| `--help` | `-h` | Display help for command | - |
| `--config` | `-c` | Path to configuration file | `~/.elastic-janitor/config.yaml` |
| `--url` | | Elasticsearch cluster URL | From config |
| `--api-key` | | Elasticsearch API key | From config |
| `--no-color` | | Disable colored output | `false` |
| `--quiet` | `-q` | Suppress non-error output | `false` |

---

## Command Naming Convention

Commands follow the pattern:

```bash
elastic-janitor <category> <action> [options]
```

Or using the short alias:

```bash
ej <category> <action> [options]
```

**Categories:**
- `index` - Index management
- `datastream` or `ds` - Data stream management
- `template` or `tpl` - Template management
- `policy` - Policy management
- `snapshot` or `snap` - Snapshot management
- `cluster` - Cluster health and diagnostics
- `storage` - Storage optimization
- `performance` or `perf` - Performance monitoring
- `bulk` - Bulk operations
- `cleanup` - Advanced cleanup
- `quality` or `dq` - Data quality
- `aws` - AWS ingestion management
- `governance` - Data quality and governance
- `tuning` - Performance tuning
- `dashboard` or `dash` - Dashboard and stats

---

## Configuration

### Configuration File

Default location: `~/.elastic-janitor/config.yaml`

```yaml
elasticsearch:
  url: "https://your-cluster:9243"
  api_key: "your-api-key"
  timeout: 30
  verify_ssl: true

settings:
  protect_system: true
  default_retention_days: 90
  max_delete_limit: 5000
  dry_run_mode: false

output:
  default_format: table
  color: true
  verbose: false

version_control:
  enable_dependency_tracking: true
  max_dependency_depth: 2
  max_versions_per_resource: 20
```

### Environment Variables

```bash
export ELASTIC_URL="https://your-cluster:9243"
export ELASTIC_API_KEY="your-api-key"
export ELASTIC_JANITOR_DRY_RUN=true
export ELASTIC_JANITOR_VERBOSE=true
```

---

## 1. Index Management Commands

### 1.1 Index Health Dashboard

**Command:** `elastic-janitor index health`

**Description:** Display comprehensive health dashboard for all indices including status, shard allocation, and issues.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to filter |
| `--status` | string | No | `all` | Filter by status: `green`, `yellow`, `red`, `all` |
| `--refresh` | int | No | - | Auto-refresh interval in seconds |

**Examples:**

```bash
# View health of all indices
elastic-janitor index health

# View only red/yellow indices
elastic-janitor index health --status red,yellow

# Monitor specific pattern with auto-refresh
elastic-janitor index health --pattern "logs-*" --refresh 5

# Output as JSON
ej index health --output json
```

**Output Format (table):**
```
┌─────────────────────┬────────┬────────┬──────────┬─────────────┐
│ Index               │ Status │ Shards │ Replicas │ Issues      │
├─────────────────────┼────────┼────────┼──────────┼─────────────┤
│ logs-2024.01.01     │ green  │ 5      │ 1        │ None        │
│ logs-2024.01.02     │ yellow │ 5      │ 1        │ Unassigned  │
└─────────────────────┴────────┴────────┴──────────┴─────────────┘
```

**Related Commands:**
- `elastic-janitor index shards` - Detailed shard analysis
- `elastic-janitor cluster health` - Overall cluster health

---

### 1.2 Shard Analysis

**Command:** `elastic-janitor index shards`

**Description:** Analyze shard distribution, allocation, and identify shard-related issues.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | No | `*` | Index pattern to analyze |
| `--node` | string | No | - | Filter by node name |
| `--state` | string | No | `all` | Shard state: `STARTED`, `RELOCATING`, `INITIALIZING`, `UNASSIGNED` |
| `--show-routing` | bool | No | `false` | Show routing allocation explanation |

**Examples:**

```bash
# Analyze all shards
elastic-janitor index shards

# Show unassigned shards with routing explanation
ej index shards --state UNASSIGNED --show-routing

# Analyze specific index
ej index shards --index "logs-2024.01.*" --verbose
```

**Output Format (table):**
```
┌──────────────┬───────┬──────┬───────────┬──────────┬──────────┐
│ Index        │ Shard │ Type │ State     │ Node     │ Size     │
├──────────────┼───────┼──────┼───────────┼──────────┼──────────┤
│ logs-2024.01 │ 0     │ p    │ STARTED   │ node-1   │ 1.2 GB   │
│ logs-2024.01 │ 0     │ r    │ STARTED   │ node-2   │ 1.2 GB   │
│ logs-2024.01 │ 1     │ p    │ UNASSIGNED│ -        │ -        │
└──────────────┴───────┴──────┴───────────┴──────────┴──────────┘
```

**Error Scenarios:**
- Invalid index pattern: Returns error with suggestion
- Connection timeout: Retries with exponential backoff

---

### 1.3 Index Settings Viewer

**Command:** `elastic-janitor index settings`

**Description:** View and compare index settings across indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index name or pattern |
| `--compare` | string | No | - | Compare with another index |
| `--setting` | string | No | `all` | Specific setting to view |
| `--diff` | bool | No | `false` | Show only differences when comparing |

**Examples:**

```bash
# View all settings for an index
elastic-janitor index settings --index "logs-2024.01.01"

# Compare settings between two indices
ej index settings --index "logs-2024.01.01" --compare "logs-2024.01.02" --diff

# View specific setting across pattern
ej index settings --index "logs-*" --setting "number_of_replicas"
```

---

### 1.4 Duplicate Index Detector

**Command:** `elastic-janitor index duplicates`

**Description:** Identify potentially duplicate indices based on naming patterns, document counts, and sizes.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to analyze |
| `--threshold` | float | No | `0.95` | Similarity threshold (0.0-1.0) |
| `--criteria` | string | No | `all` | Criteria: `name`, `size`, `docs`, `all` |

**Examples:**

```bash
# Find all potential duplicates
elastic-janitor index duplicates

# Find duplicates with high similarity
ej index duplicates --threshold 0.99

# Check specific pattern
ej index duplicates --pattern "logs-*" --criteria name,docs
```

**Output Format (table):**
```
┌─────────────────────┬─────────────────────┬────────────┬──────────┐
│ Index 1             │ Index 2             │ Similarity │ Criteria │
├─────────────────────┼─────────────────────┼────────────┼──────────┤
│ logs-2024.01.01     │ logs-2024.01.01-v2  │ 98%        │ name,docs│
│ metrics-app-prod    │ metrics-app-prod-bk │ 95%        │ all      │
└─────────────────────┴─────────────────────┴────────────┴──────────┘
```

---

### 1.5 Index Alias Management

**Command:** `elastic-janitor index alias`

**Description:** Manage index aliases - list, add, remove, and update.

**Subcommands:**
- `list` - List all aliases
- `add` - Add alias to index
- `remove` - Remove alias from index
- `update` - Update alias atomically

**Options (list):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--alias` | string | No | `*` | Alias pattern to filter |
| `--index` | string | No | `*` | Index pattern to filter |

**Options (add):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--alias` | string | Yes | - | Alias name |
| `--index` | string | Yes | - | Index name |
| `--routing` | string | No | - | Routing value |
| `--filter` | string | No | - | Filter query (JSON) |
| `--is-write-index` | bool | No | `false` | Set as write index |

**Examples:**

```bash
# List all aliases
elastic-janitor index alias list

# Add alias to index
ej index alias add --alias "logs-current" --index "logs-2024.01.01" --is-write-index

# Remove alias
ej index alias remove --alias "logs-old" --index "logs-2023.12.31"

# Update alias atomically (remove from old, add to new)
ej index alias update --alias "logs-current" --from "logs-2024.01.01" --to "logs-2024.01.02"

# Add alias with filter
ej index alias add --alias "logs-errors" --index "logs-*" --filter '{"term":{"level":"error"}}'
```

---

### 1.6 Index Rollover Status

**Command:** `elastic-janitor index rollover`

**Description:** Check rollover status and conditions for indices and data streams.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--alias` | string | No | `*` | Alias pattern to check |
| `--show-conditions` | bool | No | `true` | Show rollover conditions |
| `--simulate` | bool | No | `false` | Simulate rollover |

**Examples:**

```bash
# Check rollover status for all aliases
elastic-janitor index rollover

# Simulate rollover for specific alias
ej index rollover --alias "logs-current" --simulate

# Check with detailed conditions
ej index rollover --alias "logs-*" --show-conditions --verbose
```

---

### 1.7 Cold/Frozen Tier Migration

**Command:** `elastic-janitor index migrate`

**Description:** Migrate indices between data tiers (hot, warm, cold, frozen).

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern to migrate |
| `--from-tier` | string | No | - | Source tier |
| `--to-tier` | string | Yes | - | Target tier: `hot`, `warm`, `cold`, `frozen` |
| `--age` | string | No | - | Migrate indices older than (e.g., `30d`, `6h`) |
| `--batch-size` | int | No | `10` | Number of indices per batch |

**Examples:**

```bash
# Migrate old indices to cold tier
elastic-janitor index migrate --index "logs-*" --to-tier cold --age 90d

# Migrate specific indices to frozen
ej index migrate --index "logs-2023.*" --to-tier frozen --dry-run

# Migrate from warm to cold
ej index migrate --index "metrics-*" --from-tier warm --to-tier cold --batch-size 5
```

---

### 1.8 Index Merge Optimization

**Command:** `elastic-janitor index optimize`

**Description:** Optimize index segments through force merge operations.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern to optimize |
| `--max-segments` | int | No | `1` | Target number of segments |
| `--only-expunge-deletes` | bool | No | `false` | Only merge segments with deletions |
| `--flush` | bool | No | `true` | Flush after merge |

**Examples:**

```bash
# Force merge to 1 segment
elastic-janitor index optimize --index "logs-2024.01.01" --max-segments 1

# Expunge deletes only
ej index optimize --index "logs-*" --only-expunge-deletes

# Optimize with custom segment count
ej index optimize --index "metrics-*" --max-segments 5 --dry-run
```

**Warning:** Force merge is resource-intensive. Use with caution on large indices.

---

### 1.9 List Largest Indices

**Command:** `elastic-janitor index largest`

**Description:** List indices sorted by size, document count, or other metrics.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--top` | int | No | `25` | Number of indices to show |
| `--sort-by` | string | No | `size` | Sort by: `size`, `docs`, `shards`, `name` |
| `--pattern` | string | No | `*` | Index pattern to filter |
| `--min-size` | string | No | - | Minimum size (e.g., `1GB`) |

**Examples:**

```bash
# Show top 25 largest indices
elastic-janitor index largest

# Show top 50 by document count
ej index largest --top 50 --sort-by docs

# Show indices larger than 10GB
ej index largest --min-size 10GB --output json
```

---

## 2. Data Stream Management Commands

### 2.1 Clean Data Streams

**Command:** `elastic-janitor datastream clean`

**Description:** Delete backing indices from data streams older than specified retention period.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--retention` | string | No | `90d` | Retention period (e.g., `30d`, `6h`, `1y`) |
| `--pattern` | string | No | `*` | Data stream pattern |
| `--exclude-write-index` | bool | No | `true` | Exclude current write index |
| `--batch-size` | int | No | `100` | Indices to delete per batch |

**Examples:**

```bash
# Clean data streams older than 90 days
elastic-janitor datastream clean --retention 90d

# Clean specific pattern with 30-day retention
ej ds clean --pattern "logs-*" --retention 30d --dry-run

# Clean with custom batch size
ej datastream clean --retention 60d --batch-size 50 --verbose
```

**Output Format:**
```
Data Stream: logs-app-prod
  Total backing indices: 120
  Eligible for deletion: 45
  Total size to free: 125.5 GB

  Backing indices to delete:
  ✓ .ds-logs-app-prod-2023.10.01-000001 (2.8 GB, created 95 days ago)
  ✓ .ds-logs-app-prod-2023.10.02-000002 (2.7 GB, created 94 days ago)
  ...
```

---

### 2.2 Preview Data Streams

**Command:** `elastic-janitor datastream preview`

**Description:** Preview data stream structure and backing indices without making changes.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Data stream pattern |
| `--show-indices` | bool | No | `true` | Show backing indices |
| `--show-stats` | bool | No | `true` | Show statistics |

**Examples:**

```bash
# Preview all data streams
elastic-janitor datastream preview

# Preview specific pattern with details
ej ds preview --pattern "metrics-*" --verbose

# Preview without backing indices
ej datastream preview --show-indices false
```

---

### 2.3 Clean Standalone Indices

**Command:** `elastic-janitor datastream clean-standalone`

**Description:** Clean standalone indices (not part of data streams) older than retention period.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--retention` | string | No | `90d` | Retention period |
| `--pattern` | string | No | `*` | Index pattern |
| `--exclude-system` | bool | No | `true` | Exclude system indices |

**Examples:**

```bash
# Clean standalone indices older than 90 days
elastic-janitor datastream clean-standalone

# Clean specific pattern
ej ds clean-standalone --pattern "old-logs-*" --retention 30d
```

---

### 2.4 Data Stream Statistics

**Command:** `elastic-janitor datastream stats`

**Description:** Display comprehensive statistics for data streams.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Data stream pattern |
| `--sort-by` | string | No | `size` | Sort by: `size`, `docs`, `indices`, `name` |
| `--top` | int | No | `25` | Number to display |

**Examples:**

```bash
# Show stats for all data streams
elastic-janitor datastream stats

# Show top 10 by size
ej ds stats --top 10 --sort-by size

# Stats for specific pattern
ej datastream stats --pattern "logs-*" --output json
```

---

### 2.5 Data Stream Lifecycle Viewer

**Command:** `elastic-janitor datastream lifecycle`

**Description:** View ILM/DSL lifecycle status and phases for data streams.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Data stream pattern |
| `--phase` | string | No | `all` | Filter by phase: `hot`, `warm`, `cold`, `frozen`, `delete` |
| `--show-explain` | bool | No | `true` | Show ILM explain details |

**Examples:**

```bash
# View lifecycle for all data streams
elastic-janitor datastream lifecycle

# View specific phase
ej ds lifecycle --pattern "logs-*" --phase cold

# Detailed lifecycle explanation
ej datastream lifecycle --show-explain --verbose
```

---

### 2.6 Backing Index Reindexing

**Command:** `elastic-janitor datastream reindex`

**Description:** Reindex backing indices of a data stream.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--datastream` | string | Yes | - | Data stream name |
| `--source-index` | string | Yes | - | Source backing index |
| `--dest-index` | string | No | - | Destination index (auto-generated if not provided) |
| `--query` | string | No | - | Filter query (JSON) |
| `--wait` | bool | No | `true` | Wait for completion |

**Examples:**

```bash
# Reindex a backing index
elastic-janitor datastream reindex --datastream "logs-app" --source-index ".ds-logs-app-2024.01.01-000001"

# Reindex with filter
ej ds reindex --datastream "logs-app" --source-index ".ds-logs-app-2024.01.01-000001" \
  --query '{"range":{"@timestamp":{"gte":"2024-01-01","lt":"2024-01-02"}}}'

# Reindex without waiting
ej datastream reindex --datastream "logs-app" --source-index ".ds-logs-app-2024.01.01-000001" --wait false
```

---

### 2.7 Data Stream Cloning

**Command:** `elastic-janitor datastream clone`

**Description:** Clone a data stream with all its backing indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--source` | string | Yes | - | Source data stream name |
| `--dest` | string | Yes | - | Destination data stream name |
| `--include-settings` | bool | No | `true` | Clone settings |
| `--include-mappings` | bool | No | `true` | Clone mappings |

**Examples:**

```bash
# Clone data stream
elastic-janitor datastream clone --source "logs-prod" --dest "logs-prod-backup"

# Clone without settings
ej ds clone --source "logs-prod" --dest "logs-test" --include-settings false
```

---

### 2.8 Write Index Rotation

**Command:** `elastic-janitor datastream rotate`

**Description:** Manually rotate the write index of a data stream.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--datastream` | string | Yes | - | Data stream name |
| `--force` | bool | No | `false` | Force rotation even if conditions not met |

**Examples:**

```bash
# Rotate write index
elastic-janitor datastream rotate --datastream "logs-app"

# Force rotation
ej ds rotate --datastream "logs-app" --force --dry-run
```

---

## 3. Template & Policy Management Commands

### 3.1 Index Templates

#### 3.1.1 List Index Templates

**Command:** `elastic-janitor template index list`

**Description:** List all index templates with their patterns and priorities.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Template name pattern |
| `--show-details` | bool | No | `false` | Show full template details |

**Examples:**

```bash
# List all index templates
elastic-janitor template index list

# List specific pattern
ej tpl index list --pattern "logs-*"

# List with details
ej template index list --show-details --output json
```

---

#### 3.1.2 View Index Template Details

**Command:** `elastic-janitor template index view`

**Description:** View detailed configuration of an index template.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Template name |
| `--show-composed` | bool | No | `false` | Show composed settings (with component templates) |

**Examples:**

```bash
# View template details
elastic-janitor template index view --name "logs-template"

# View composed template
ej tpl index view --name "logs-template" --show-composed
```

---

#### 3.1.3 Delete Index Templates

**Command:** `elastic-janitor template index delete`

**Description:** Delete index templates matching pattern.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Template name pattern |
| `--confirm` | bool | No | `false` | Skip confirmation prompt |

**Examples:**

```bash
# Delete templates matching pattern
elastic-janitor template index delete --pattern "old-*"

# Delete with auto-confirm
ej tpl index delete --pattern "test-*" --confirm --dry-run
```

---

#### 3.1.4 Edit Index Template

**Command:** `elastic-janitor template index edit`

**Description:** Edit an index template with version control.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Template name |
| `--file` | string | No | - | JSON file with template definition |
| `--editor` | string | No | `$EDITOR` | Editor to use for interactive editing |
| `--save-version` | bool | No | `true` | Save version before editing |

**Examples:**

```bash
# Edit template interactively
elastic-janitor template index edit --name "logs-template"

# Edit from file
ej tpl index edit --name "logs-template" --file template.json

# Edit without saving version
ej template index edit --name "logs-template" --save-version false
```

---

#### 3.1.5 Rollback Index Template

**Command:** `elastic-janitor template index rollback`

**Description:** Rollback an index template to a previous version.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Template name |
| `--version` | int | No | - | Version number (if not provided, shows list) |
| `--show-diff` | bool | No | `true` | Show diff before rollback |

**Examples:**

```bash
# List versions and select
elastic-janitor template index rollback --name "logs-template"

# Rollback to specific version
ej tpl index rollback --name "logs-template" --version 5

# Rollback with diff
ej template index rollback --name "logs-template" --version 5 --show-diff
```

---

#### 3.1.6 Export/Import Index Templates

**Command:** `elastic-janitor template index export`
**Command:** `elastic-janitor template index import`

**Description:** Export templates to files or import from files.

**Options (export):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Template pattern to export |
| `--output-dir` | string | No | `./templates` | Output directory |
| `--format` | string | No | `json` | Format: `json`, `yaml` |

**Options (import):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--file` | string | Yes | - | File to import |
| `--overwrite` | bool | No | `false` | Overwrite existing templates |

**Examples:**

```bash
# Export all templates
elastic-janitor template index export

# Export specific pattern
ej tpl index export --pattern "logs-*" --output-dir ./backup

# Import template
ej template index import --file ./backup/logs-template.json

# Import with overwrite
ej tpl index import --file template.json --overwrite --dry-run
```

---

### 3.2 Component Templates

#### 3.2.1 List Component Templates

**Command:** `elastic-janitor template component list`

**Description:** List all component templates.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Template name pattern |
| `--show-usage` | bool | No | `false` | Show which index templates use each component |

**Examples:**

```bash
# List all component templates
elastic-janitor template component list

# List with usage information
ej tpl component list --show-usage
```

---

#### 3.2.2 View Component Template Details

**Command:** `elastic-janitor template component view`

**Description:** View detailed configuration of a component template.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Component template name |

**Examples:**

```bash
# View component template
elastic-janitor template component view --name "logs-settings"
```

---

#### 3.2.3 Delete Component Templates

**Command:** `elastic-janitor template component delete`

**Description:** Delete component templates matching pattern.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Template name pattern |
| `--check-usage` | bool | No | `true` | Check if used by index templates |
| `--confirm` | bool | No | `false` | Skip confirmation prompt |

**Examples:**

```bash
# Delete component templates
elastic-janitor template component delete --pattern "old-*"

# Delete without usage check
ej tpl component delete --pattern "test-*" --check-usage false
```

---

#### 3.2.4 Edit/Rollback/Export/Import Component Templates

Similar to index templates, component templates support:
- `elastic-janitor template component edit --name <name>`
- `elastic-janitor template component rollback --name <name> --version <version>`
- `elastic-janitor template component export --pattern <pattern>`
- `elastic-janitor template component import --file <file>`

---

### 3.3 Ingest Pipelines

#### 3.3.1 List Ingest Pipelines

**Command:** `elastic-janitor pipeline list`

**Description:** List all ingest pipelines.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Pipeline name pattern |
| `--show-processors` | bool | No | `false` | Show processor count |

**Examples:**

```bash
# List all pipelines
elastic-janitor pipeline list

# List with processor info
ej pipeline list --show-processors
```

---

#### 3.3.2 View Pipeline Details

**Command:** `elastic-janitor pipeline view`

**Description:** View detailed configuration of an ingest pipeline.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Pipeline name |
| `--show-processors` | bool | No | `true` | Show processor details |

**Examples:**

```bash
# View pipeline
elastic-janitor pipeline view --name "logs-pipeline"

# View without processor details
ej pipeline view --name "logs-pipeline" --show-processors false
```

---

#### 3.3.3 Edit Ingest Pipeline

**Command:** `elastic-janitor pipeline edit`

**Description:** Edit an ingest pipeline with version control.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Pipeline name |
| `--file` | string | No | - | JSON file with pipeline definition |
| `--save-version` | bool | No | `true` | Save version before editing |
| `--track-dependencies` | bool | No | `true` | Track dependent resources |

**Examples:**

```bash
# Edit pipeline interactively
elastic-janitor pipeline edit --name "logs-pipeline"

# Edit from file
ej pipeline edit --name "logs-pipeline" --file pipeline.json
```

---

#### 3.3.4 View Version History

**Command:** `elastic-janitor pipeline history`

**Description:** View version history of an ingest pipeline.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Pipeline name |
| `--limit` | int | No | `20` | Number of versions to show |

**Examples:**

```bash
# View version history
elastic-janitor pipeline history --name "logs-pipeline"

# View last 10 versions
ej pipeline history --name "logs-pipeline" --limit 10
```

---

#### 3.3.5 Rollback Pipeline

**Command:** `elastic-janitor pipeline rollback`

**Description:** Rollback an ingest pipeline to a previous version.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Pipeline name |
| `--version` | int | No | - | Version number |
| `--show-diff` | bool | No | `true` | Show diff before rollback |

**Examples:**

```bash
# Rollback to previous version
elastic-janitor pipeline rollback --name "logs-pipeline"

# Rollback to specific version
ej pipeline rollback --name "logs-pipeline" --version 5
```

---

#### 3.3.6 Emergency Rollback

**Command:** `elastic-janitor pipeline emergency-rollback`

**Description:** Emergency rollback to last known-good version.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Pipeline name |
| `--confirm` | bool | No | `false` | Skip confirmation |

**Examples:**

```bash
# Emergency rollback
elastic-janitor pipeline emergency-rollback --name "logs-pipeline"

# Emergency rollback with auto-confirm
ej pipeline emergency-rollback --name "logs-pipeline" --confirm
```

---

#### 3.3.7 Export/Import Pipelines

**Command:** `elastic-janitor pipeline export`
**Command:** `elastic-janitor pipeline import`

**Options (export):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Pipeline pattern |
| `--output-dir` | string | No | `./pipelines` | Output directory |
| `--include-dependencies` | bool | No | `false` | Include dependent resources |

**Examples:**

```bash
# Export all pipelines
elastic-janitor pipeline export

# Export with dependencies
ej pipeline export --pattern "logs-*" --include-dependencies
```

---

#### 3.3.8 Clone Pipeline

**Command:** `elastic-janitor pipeline clone`

**Description:** Clone an existing pipeline with a new name.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--source` | string | Yes | - | Source pipeline name |
| `--dest` | string | Yes | - | Destination pipeline name |
| `--overwrite` | bool | No | `false` | Overwrite if exists |

**Examples:**

```bash
# Clone pipeline
elastic-janitor pipeline clone --source "logs-prod" --dest "logs-test"

# Clone with overwrite
ej pipeline clone --source "logs-prod" --dest "logs-dev" --overwrite
```

---

#### 3.3.9 Delete Pipelines

**Command:** `elastic-janitor pipeline delete`

**Description:** Delete ingest pipelines matching pattern.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Pipeline name pattern |
| `--check-usage` | bool | No | `true` | Check if used by indices |
| `--confirm` | bool | No | `false` | Skip confirmation |

**Examples:**

```bash
# Delete pipelines
elastic-janitor pipeline delete --pattern "old-*"

# Delete with auto-confirm
ej pipeline delete --pattern "test-*" --confirm --dry-run
```

---

### 3.4 ILM Policies

#### 3.4.1 List ILM Policies

**Command:** `elastic-janitor policy ilm list`

**Description:** List all ILM policies.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Policy name pattern |
| `--show-usage` | bool | No | `false` | Show indices using each policy |

**Examples:**

```bash
# List all ILM policies
elastic-janitor policy ilm list

# List with usage
ej policy ilm list --show-usage
```

---

#### 3.4.2 View ILM Policy Details

**Command:** `elastic-janitor policy ilm view`

**Description:** View detailed configuration of an ILM policy.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Policy name |
| `--show-phases` | bool | No | `true` | Show phase details |

**Examples:**

```bash
# View ILM policy
elastic-janitor policy ilm view --name "logs-policy"
```

---

#### 3.4.3 Delete ILM Policies

**Command:** `elastic-janitor policy ilm delete`

**Description:** Delete ILM policies matching pattern.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Policy name pattern |
| `--check-usage` | bool | No | `true` | Check if used by indices |
| `--confirm` | bool | No | `false` | Skip confirmation |

**Examples:**

```bash
# Delete ILM policies
elastic-janitor policy ilm delete --pattern "old-*"
```

---

#### 3.4.4 ILM Policy Simulator

**Command:** `elastic-janitor policy ilm simulate`

**Description:** Simulate ILM policy execution on indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--policy` | string | Yes | - | Policy name |
| `--index` | string | No | - | Index to simulate (or pattern) |
| `--time-forward` | string | No | `0d` | Simulate time forward (e.g., `30d`) |

**Examples:**

```bash
# Simulate policy on index
elastic-janitor policy ilm simulate --policy "logs-policy" --index "logs-2024.01.01"

# Simulate 30 days forward
ej policy ilm simulate --policy "logs-policy" --index "logs-*" --time-forward 30d
```

---

#### 3.4.5 Bulk Policy Assignment

**Command:** `elastic-janitor policy ilm assign`

**Description:** Assign ILM policy to multiple indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--policy` | string | Yes | - | Policy name |
| `--index` | string | Yes | - | Index pattern |
| `--rollover-alias` | string | No | - | Rollover alias |

**Examples:**

```bash
# Assign policy to indices
elastic-janitor policy ilm assign --policy "logs-policy" --index "logs-*"

# Assign with rollover alias
ej policy ilm assign --policy "logs-policy" --index "logs-*" --rollover-alias "logs-current"
```

---

#### 3.4.6 Policy Effectiveness Report

**Command:** `elastic-janitor policy ilm effectiveness`

**Description:** Generate report on ILM policy effectiveness.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--policy` | string | No | `*` | Policy name pattern |
| `--metrics` | string | No | `all` | Metrics: `storage`, `performance`, `compliance`, `all` |

**Examples:**

```bash
# Generate effectiveness report
elastic-janitor policy ilm effectiveness

# Report for specific policy
ej policy ilm effectiveness --policy "logs-policy" --metrics storage,compliance
```

---

### 3.5 Template Analysis & Tools

#### 3.5.1 Template Conflict Detector

**Command:** `elastic-janitor template conflicts`

**Description:** Detect conflicts between index templates and component templates.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Template pattern to check |
| `--severity` | string | No | `all` | Filter by severity: `high`, `medium`, `low`, `all` |

**Examples:**

```bash
# Detect all conflicts
elastic-janitor template conflicts

# Detect high-severity conflicts
ej template conflicts --severity high
```

---

#### 3.5.2 Template Inheritance Viewer

**Command:** `elastic-janitor template inheritance`

**Description:** Visualize template inheritance and composition.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Template name |
| `--format` | string | No | `tree` | Format: `tree`, `graph`, `json` |

**Examples:**

```bash
# View inheritance tree
elastic-janitor template inheritance --name "logs-template"

# View as graph
ej template inheritance --name "logs-template" --format graph
```

---

#### 3.5.3 Unused Template Detector

**Command:** `elastic-janitor template unused`

**Description:** Identify templates not used by any indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--type` | string | No | `all` | Type: `index`, `component`, `all` |
| `--age` | string | No | - | Only show unused for longer than (e.g., `30d`) |

**Examples:**

```bash
# Find all unused templates
elastic-janitor template unused

# Find unused index templates older than 30 days
ej template unused --type index --age 30d
```

---

#### 3.5.4 View Resource Dependencies

**Command:** `elastic-janitor template dependencies`

**Description:** View dependencies between templates, pipelines, and policies.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--resource` | string | Yes | - | Resource name |
| `--type` | string | Yes | - | Type: `template`, `component`, `pipeline` |
| `--depth` | int | No | `2` | Dependency depth |

**Examples:**

```bash
# View template dependencies
elastic-janitor template dependencies --resource "logs-template" --type template

# View pipeline dependencies
ej template dependencies --resource "logs-pipeline" --type pipeline --depth 3
```

---

#### 3.5.5 Rollback with Dependencies

**Command:** `elastic-janitor template rollback-deps`

**Description:** Rollback a resource and all its dependencies to a previous state.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--resource` | string | Yes | - | Resource name |
| `--type` | string | Yes | - | Type: `template`, `component`, `pipeline` |
| `--version` | int | No | - | Version number |
| `--show-plan` | bool | No | `true` | Show rollback plan before executing |

**Examples:**

```bash
# Rollback with dependencies
elastic-janitor template rollback-deps --resource "logs-template" --type template

# Rollback to specific version
ej template rollback-deps --resource "logs-pipeline" --type pipeline --version 5
```

---

## 4. Snapshot & Backup Management Commands

### 4.1 Snapshot Management

#### 4.1.1 List Snapshot Repositories

**Command:** `elastic-janitor snapshot repo list`

**Description:** List all snapshot repositories.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--show-settings` | bool | No | `false` | Show repository settings |

**Examples:**

```bash
# List all repositories
elastic-janitor snapshot repo list

# List with settings
ej snap repo list --show-settings
```

---

#### 4.1.2 List Snapshots in Repository

**Command:** `elastic-janitor snapshot list`

**Description:** List snapshots in a repository.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--repo` | string | Yes | - | Repository name |
| `--pattern` | string | No | `*` | Snapshot name pattern |
| `--sort-by` | string | No | `date` | Sort by: `date`, `size`, `name` |
| `--state` | string | No | `all` | Filter by state: `SUCCESS`, `FAILED`, `IN_PROGRESS`, `all` |

**Examples:**

```bash
# List all snapshots in repository
elastic-janitor snapshot list --repo "backup-repo"

# List failed snapshots
ej snap list --repo "backup-repo" --state FAILED

# List sorted by size
ej snapshot list --repo "backup-repo" --sort-by size
```

---

#### 4.1.3 Delete Old Snapshots

**Command:** `elastic-janitor snapshot delete`

**Description:** Delete snapshots older than specified retention period.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--repo` | string | Yes | - | Repository name |
| `--retention` | string | No | `90d` | Retention period |
| `--pattern` | string | No | `*` | Snapshot name pattern |
| `--keep-last` | int | No | `5` | Keep at least N most recent snapshots |

**Examples:**

```bash
# Delete snapshots older than 90 days
elastic-janitor snapshot delete --repo "backup-repo" --retention 90d

# Delete with pattern, keeping last 10
ej snap delete --repo "backup-repo" --pattern "daily-*" --retention 30d --keep-last 10

# Dry run
ej snapshot delete --repo "backup-repo" --retention 60d --dry-run
```

---

#### 4.1.4 Verify Repository

**Command:** `elastic-janitor snapshot verify`

**Description:** Verify snapshot repository integrity.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--repo` | string | Yes | - | Repository name |

**Examples:**

```bash
# Verify repository
elastic-janitor snapshot verify --repo "backup-repo"
```

---

### 4.2 SLM Policies

#### 4.2.1 List SLM Policies

**Command:** `elastic-janitor snapshot slm list`

**Description:** List all Snapshot Lifecycle Management policies.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--show-stats` | bool | No | `false` | Show execution statistics |

**Examples:**

```bash
# List all SLM policies
elastic-janitor snapshot slm list

# List with statistics
ej snap slm list --show-stats
```

---

#### 4.2.2 Delete SLM Policies

**Command:** `elastic-janitor snapshot slm delete`

**Description:** Delete SLM policies matching pattern.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Policy name pattern |
| `--confirm` | bool | No | `false` | Skip confirmation |

**Examples:**

```bash
# Delete SLM policies
elastic-janitor snapshot slm delete --pattern "old-*"
```

---

### 4.3 Advanced Snapshot Operations

#### 4.3.1 Snapshot Size Analysis

**Command:** `elastic-janitor snapshot analyze`

**Description:** Analyze snapshot sizes and growth trends.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--repo` | string | Yes | - | Repository name |
| `--time-range` | string | No | `30d` | Time range to analyze |
| `--show-trends` | bool | No | `true` | Show growth trends |

**Examples:**

```bash
# Analyze snapshot sizes
elastic-janitor snapshot analyze --repo "backup-repo"

# Analyze last 90 days
ej snap analyze --repo "backup-repo" --time-range 90d
```

---

#### 4.3.2 Automated Snapshot Cleanup

**Command:** `elastic-janitor snapshot cleanup`

**Description:** Automated cleanup based on retention policies.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--repo` | string | Yes | - | Repository name |
| `--policy` | string | No | - | Cleanup policy file (YAML) |
| `--daily-keep` | int | No | `7` | Keep N daily snapshots |
| `--weekly-keep` | int | No | `4` | Keep N weekly snapshots |
| `--monthly-keep` | int | No | `12` | Keep N monthly snapshots |

**Examples:**

```bash
# Cleanup with default retention
elastic-janitor snapshot cleanup --repo "backup-repo"

# Cleanup with custom retention
ej snap cleanup --repo "backup-repo" --daily-keep 14 --weekly-keep 8 --monthly-keep 24

# Cleanup with policy file
ej snapshot cleanup --repo "backup-repo" --policy cleanup-policy.yaml
```

---

#### 4.3.3 Cross-Repository Copy

**Command:** `elastic-janitor snapshot copy`

**Description:** Copy snapshots between repositories.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--source-repo` | string | Yes | - | Source repository |
| `--dest-repo` | string | Yes | - | Destination repository |
| `--snapshot` | string | Yes | - | Snapshot name or pattern |
| `--rename` | string | No | - | Rename pattern |

**Examples:**

```bash
# Copy snapshot
elastic-janitor snapshot copy --source-repo "backup-repo" --dest-repo "archive-repo" --snapshot "daily-2024.01.01"

# Copy with rename
ej snap copy --source-repo "backup-repo" --dest-repo "archive-repo" --snapshot "daily-*" --rename "archived-{date}"
```

---

#### 4.3.4 Snapshot Restore Wizard

**Command:** `elastic-janitor snapshot restore`

**Description:** Interactive wizard for restoring snapshots.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--repo` | string | Yes | - | Repository name |
| `--snapshot` | string | Yes | - | Snapshot name |
| `--indices` | string | No | `*` | Indices to restore |
| `--rename-pattern` | string | No | - | Rename pattern |
| `--include-aliases` | bool | No | `true` | Include aliases |
| `--wait` | bool | No | `true` | Wait for completion |

**Examples:**

```bash
# Restore snapshot
elastic-janitor snapshot restore --repo "backup-repo" --snapshot "daily-2024.01.01"

# Restore specific indices
ej snap restore --repo "backup-repo" --snapshot "daily-2024.01.01" --indices "logs-*"

# Restore with rename
ej snapshot restore --repo "backup-repo" --snapshot "daily-2024.01.01" --rename-pattern "restored-{index}"
```

---

#### 4.3.5 Snapshot Comparison

**Command:** `elastic-janitor snapshot compare`

**Description:** Compare two snapshots to see differences.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--repo` | string | Yes | - | Repository name |
| `--snapshot1` | string | Yes | - | First snapshot name |
| `--snapshot2` | string | Yes | - | Second snapshot name |
| `--show-details` | bool | No | `false` | Show detailed differences |

**Examples:**

```bash
# Compare snapshots
elastic-janitor snapshot compare --repo "backup-repo" --snapshot1 "daily-2024.01.01" --snapshot2 "daily-2024.01.02"

# Compare with details
ej snap compare --repo "backup-repo" --snapshot1 "daily-2024.01.01" --snapshot2 "daily-2024.01.02" --show-details
```

---

## 5. Cluster Health & Diagnostics Commands

### 5.1 Cluster Health Overview

**Command:** `elastic-janitor cluster health`

**Description:** Display comprehensive cluster health overview.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--level` | string | No | `cluster` | Level: `cluster`, `indices`, `shards` |
| `--wait-for-status` | string | No | - | Wait for status: `green`, `yellow`, `red` |
| `--timeout` | string | No | `30s` | Timeout for wait |
| `--refresh` | int | No | - | Auto-refresh interval in seconds |

**Examples:**

```bash
# View cluster health
elastic-janitor cluster health

# View with index-level details
ej cluster health --level indices

# Wait for green status
ej cluster health --wait-for-status green --timeout 60s

# Monitor with auto-refresh
ej cluster health --refresh 5
```

---

### 5.2 Node Information

**Command:** `elastic-janitor cluster nodes`

**Description:** Display information about cluster nodes.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--node` | string | No | `*` | Node name or pattern |
| `--show-stats` | bool | No | `true` | Show node statistics |
| `--show-roles` | bool | No | `true` | Show node roles |

**Examples:**

```bash
# List all nodes
elastic-janitor cluster nodes

# View specific node
ej cluster nodes --node "node-1"

# List nodes without stats
ej cluster nodes --show-stats false
```

---

### 5.3 Cluster Stats

**Command:** `elastic-janitor cluster stats`

**Description:** Display comprehensive cluster statistics.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--metrics` | string | No | `all` | Metrics: `indices`, `nodes`, `storage`, `all` |
| `--human` | bool | No | `true` | Human-readable sizes |

**Examples:**

```bash
# View all cluster stats
elastic-janitor cluster stats

# View specific metrics
ej cluster stats --metrics indices,storage

# View raw numbers
ej cluster stats --human false --output json
```

---

## 6. Storage & Cost Optimization Commands

### 6.1 Storage Forecast

**Command:** `elastic-janitor storage forecast`

**Description:** Forecast storage growth based on historical trends.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--days` | int | No | `30` | Days to forecast |
| `--historical-days` | int | No | `30` | Historical data to analyze |
| `--pattern` | string | No | `*` | Index pattern to analyze |
| `--show-chart` | bool | No | `true` | Show growth chart |

**Examples:**

```bash
# Forecast storage for next 30 days
elastic-janitor storage forecast

# Forecast for specific pattern
ej storage forecast --pattern "logs-*" --days 90

# Forecast based on 60 days of history
ej storage forecast --historical-days 60 --days 30
```

**Output Format:**
```
Storage Forecast Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current Storage:     2.5 TB
Daily Growth Rate:   85 GB/day
Forecast (30 days):  5.05 TB
Forecast (60 days):  7.6 TB
Forecast (90 days):  10.15 TB

Recommendations:
  • Consider implementing ILM policies for indices older than 90 days
  • Migrate cold data to frozen tier to save 40% storage costs
  • Enable compression on indices to reduce storage by ~30%
```

---

### 6.2 Tier Distribution Report

**Command:** `elastic-janitor storage tiers`

**Description:** Analyze data distribution across storage tiers.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--show-indices` | bool | No | `false` | Show indices per tier |
| `--show-costs` | bool | No | `false` | Show estimated costs per tier |

**Examples:**

```bash
# View tier distribution
elastic-janitor storage tiers

# View with indices
ej storage tiers --show-indices

# View with cost estimates
ej storage tiers --show-costs
```

**Output Format:**
```
┌──────────┬─────────┬──────────┬────────────┬──────────────┐
│ Tier     │ Indices │ Size     │ % of Total │ Est. Cost/Mo │
├──────────┼─────────┼──────────┼────────────┼──────────────┤
│ hot      │ 45      │ 850 GB   │ 34%        │ $425         │
│ warm     │ 120     │ 1.2 TB   │ 48%        │ $360         │
│ cold     │ 85      │ 450 GB   │ 18%        │ $90          │
│ frozen   │ 12      │ 50 GB    │ 2%         │ $10          │
└──────────┴─────────┴──────────┴────────────┴──────────────┘
```

---

### 6.3 Compression Analysis

**Command:** `elastic-janitor storage compression`

**Description:** Analyze compression ratios and identify optimization opportunities.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to analyze |
| `--show-recommendations` | bool | No | `true` | Show compression recommendations |
| `--min-size` | string | No | `1GB` | Minimum index size to analyze |

**Examples:**

```bash
# Analyze compression for all indices
elastic-janitor storage compression

# Analyze specific pattern
ej storage compression --pattern "logs-*"

# Analyze large indices only
ej storage compression --min-size 10GB
```

**Output Format:**
```
Compression Analysis Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-2024.01.01
  Uncompressed Size: 5.2 GB
  Compressed Size:   1.8 GB
  Compression Ratio: 65% (2.9:1)
  Codec: default

  Recommendation: Switch to best_compression codec
  Potential Savings: 520 MB (10% additional compression)
```

---

### 6.4 Empty Index Cleanup

**Command:** `elastic-janitor storage cleanup-empty`

**Description:** Identify and delete empty or near-empty indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern |
| `--max-docs` | int | No | `0` | Maximum document count to consider empty |
| `--max-size` | string | No | `1MB` | Maximum size to consider empty |

**Examples:**

```bash
# Find and delete empty indices
elastic-janitor storage cleanup-empty

# Find indices with less than 100 docs
ej storage cleanup-empty --max-docs 100

# Find indices smaller than 10MB
ej storage cleanup-empty --max-size 10MB --dry-run
```

---

### 6.5 Sparse Index Detector

**Command:** `elastic-janitor storage sparse`

**Description:** Detect indices with low document density (sparse indices).

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern |
| `--threshold` | float | No | `0.1` | Sparsity threshold (0.0-1.0) |
| `--min-size` | string | No | `1GB` | Minimum size to analyze |

**Examples:**

```bash
# Detect sparse indices
elastic-janitor storage sparse

# Detect with custom threshold
ej storage sparse --threshold 0.05 --min-size 5GB
```

**Output Format:**
```
Sparse Index Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: metrics-2024.01.01
  Size: 12 GB
  Documents: 50,000
  Avg Doc Size: 240 KB
  Sparsity Score: 0.08 (Very Sparse)

  Recommendation: Consider reindexing with better compression or
                  merging with other sparse indices
  Potential Savings: 8 GB (67%)
```

---

### 6.6 Cost Estimator

**Command:** `elastic-janitor storage cost`

**Description:** Estimate storage costs and optimization savings.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--provider` | string | No | `elastic-cloud` | Provider: `elastic-cloud`, `aws`, `gcp`, `azure` |
| `--region` | string | No | - | Cloud region |
| `--show-optimizations` | bool | No | `true` | Show potential savings |

**Examples:**

```bash
# Estimate costs
elastic-janitor storage cost

# Estimate for AWS
ej storage cost --provider aws --region us-east-1

# Show optimization opportunities
ej storage cost --show-optimizations
```

**Output Format:**
```
Storage Cost Estimate
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current Monthly Cost: $1,250

Breakdown by Tier:
  Hot:    $625 (850 GB @ $0.735/GB)
  Warm:   $450 (1.2 TB @ $0.375/GB)
  Cold:   $150 (450 GB @ $0.333/GB)
  Frozen: $25  (50 GB @ $0.50/GB)

Optimization Opportunities:
  1. Migrate 200 GB from hot to warm tier:     Save $72/month
  2. Enable compression on 15 indices:         Save $95/month
  3. Delete 25 empty/unused indices:           Save $45/month
  4. Implement ILM for logs-* pattern:         Save $180/month

  Total Potential Savings: $392/month (31%)
```

---

## 7. Performance & Monitoring Commands

### 7.1 Slow Query Analyzer

**Command:** `elastic-janitor performance slow-queries`

**Description:** Analyze slow queries and identify performance bottlenecks.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--threshold` | string | No | `1s` | Slow query threshold |
| `--time-range` | string | No | `1h` | Time range to analyze |
| `--top` | int | No | `25` | Number of queries to show |
| `--index` | string | No | `*` | Index pattern to analyze |

**Examples:**

```bash
# Analyze slow queries
elastic-janitor performance slow-queries

# Analyze queries slower than 5 seconds
ej perf slow-queries --threshold 5s --time-range 24h

# Analyze specific index
ej performance slow-queries --index "logs-*" --top 50
```

**Output Format:**
```
Slow Query Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query #1: Search on logs-2024.01.01
  Avg Duration: 3.2s
  Executions: 1,245
  Total Time: 66.4 minutes

  Query DSL:
  {
    "query": {
      "bool": {
        "must": [
          {"wildcard": {"message": "*error*"}}
        ]
      }
    }
  }

  Recommendations:
  • Replace wildcard query with match query for better performance
  • Add index to 'message' field
  • Consider using ngram tokenizer
```

---

### 7.2 Indexing Performance Monitor

**Command:** `elastic-janitor performance indexing`

**Description:** Monitor indexing performance and throughput.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | No | `*` | Index pattern to monitor |
| `--time-range` | string | No | `1h` | Time range to analyze |
| `--refresh` | int | No | - | Auto-refresh interval in seconds |

**Examples:**

```bash
# Monitor indexing performance
elastic-janitor performance indexing

# Monitor specific index
ej perf indexing --index "logs-*" --time-range 24h

# Monitor with auto-refresh
ej performance indexing --refresh 10
```

**Output Format:**
```
Indexing Performance Monitor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-2024.01.01
  Indexing Rate:     1,250 docs/sec
  Avg Latency:       45ms
  Bulk Rejections:   12 (0.01%)
  Refresh Time:      250ms
  Merge Time:        1.2s

  Status: ✓ Healthy

  Recommendations:
  • Indexing rate is optimal
  • Consider increasing refresh_interval to reduce refresh overhead
```

---

### 7.3 Search Performance Dashboard

**Command:** `elastic-janitor performance search`

**Description:** Display search performance metrics and statistics.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | No | `*` | Index pattern |
| `--time-range` | string | No | `1h` | Time range |
| `--refresh` | int | No | - | Auto-refresh interval |

**Examples:**

```bash
# View search performance
elastic-janitor performance search

# Monitor specific index
ej perf search --index "logs-*" --refresh 5
```

---

### 7.4 Cluster Health Timeline

**Command:** `elastic-janitor performance timeline`

**Description:** Display cluster health timeline and historical trends.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--time-range` | string | No | `24h` | Time range to display |
| `--interval` | string | No | `1h` | Data point interval |
| `--metrics` | string | No | `all` | Metrics: `health`, `cpu`, `memory`, `disk`, `all` |

**Examples:**

```bash
# View 24-hour timeline
elastic-janitor performance timeline

# View 7-day timeline with 6-hour intervals
ej perf timeline --time-range 7d --interval 6h

# View specific metrics
ej performance timeline --metrics cpu,memory
```

---

### 7.5 Node Resource Usage

**Command:** `elastic-janitor performance nodes`

**Description:** Monitor resource usage across cluster nodes.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--node` | string | No | `*` | Node name or pattern |
| `--metrics` | string | No | `all` | Metrics: `cpu`, `memory`, `disk`, `jvm`, `all` |
| `--refresh` | int | No | - | Auto-refresh interval |

**Examples:**

```bash
# Monitor all nodes
elastic-janitor performance nodes

# Monitor specific node
ej perf nodes --node "node-1" --refresh 5

# Monitor specific metrics
ej performance nodes --metrics cpu,memory,jvm
```

**Output Format:**
```
Node Resource Usage
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Node: node-1 (Master, Data)
  CPU Usage:        45%
  Memory Usage:     78% (15.6 GB / 20 GB)
  JVM Heap:         65% (13 GB / 20 GB)
  Disk Usage:       82% (820 GB / 1 TB)

  Status: ⚠ Warning (High disk usage)

  Recommendations:
  • Disk usage above 80% - consider adding storage or cleaning old data
  • JVM heap usage is healthy
```

---

### 7.6 Hot Spot Detector

**Command:** `elastic-janitor performance hotspots`

**Description:** Detect performance hot spots and resource bottlenecks.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--type` | string | No | `all` | Type: `cpu`, `memory`, `disk`, `network`, `all` |
| `--threshold` | float | No | `0.8` | Threshold for detection (0.0-1.0) |

**Examples:**

```bash
# Detect all hot spots
elastic-janitor performance hotspots

# Detect CPU hot spots
ej perf hotspots --type cpu --threshold 0.9

# Detect with custom threshold
ej performance hotspots --threshold 0.7
```

**Output Format:**
```
Performance Hot Spots
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 Hot Spot #1: High CPU on node-2
   CPU Usage: 95%
   Cause: Heavy search load on logs-2024.01.01
   Impact: Search latency increased by 300%

   Recommendations:
   • Add more data nodes to distribute load
   • Optimize queries on logs-2024.01.01
   • Consider adding replicas

🔥 Hot Spot #2: High disk I/O on node-3
   Disk I/O: 92%
   Cause: Large merge operations on metrics-*
   Impact: Indexing throughput reduced by 40%

   Recommendations:
   • Reduce merge factor
   • Increase refresh_interval
   • Consider using faster storage
```

---

## 8. Bulk Operations & Automation Commands

### 8.1 Batch Index Operations

**Command:** `elastic-janitor bulk index`

**Description:** Perform batch operations on multiple indices.

**Subcommands:**
- `close` - Close multiple indices
- `open` - Open multiple indices
- `delete` - Delete multiple indices
- `freeze` - Freeze multiple indices
- `unfreeze` - Unfreeze multiple indices

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Index pattern |
| `--batch-size` | int | No | `10` | Batch size |
| `--parallel` | int | No | `1` | Parallel operations |
| `--continue-on-error` | bool | No | `false` | Continue if errors occur |

**Examples:**

```bash
# Close multiple indices
elastic-janitor bulk index close --pattern "old-logs-*"

# Delete with batching
ej bulk index delete --pattern "test-*" --batch-size 5 --dry-run

# Freeze indices in parallel
ej bulk index freeze --pattern "archive-*" --parallel 3
```

---

### 8.2 Scheduled Cleanup Jobs

**Command:** `elastic-janitor bulk schedule`

**Description:** Schedule automated cleanup jobs.

**Subcommands:**
- `create` - Create scheduled job
- `list` - List scheduled jobs
- `delete` - Delete scheduled job
- `run` - Run scheduled job manually
- `enable` - Enable scheduled job
- `disable` - Disable scheduled job

**Options (create):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | Yes | - | Job name |
| `--schedule` | string | Yes | - | Cron expression |
| `--operation` | string | Yes | - | Operation to perform |
| `--config` | string | Yes | - | Job configuration file (YAML) |

**Examples:**

```bash
# Create scheduled cleanup job
elastic-janitor bulk schedule create --name "daily-cleanup" \
  --schedule "0 2 * * *" \
  --operation "datastream-clean" \
  --config cleanup-config.yaml

# List scheduled jobs
ej bulk schedule list

# Run job manually
ej bulk schedule run --name "daily-cleanup"

# Disable job
ej bulk schedule disable --name "daily-cleanup"
```

**Config File Example (cleanup-config.yaml):**
```yaml
operation: datastream-clean
parameters:
  retention: 90d
  pattern: "logs-*"
  exclude_write_index: true
  batch_size: 100
notifications:
  email: admin@example.com
  slack_webhook: https://hooks.slack.com/...
```

---

### 8.3 Dry-Run Mode

**Command:** `elastic-janitor bulk dry-run`

**Description:** Toggle global dry-run mode or run specific operations in dry-run.

**Subcommands:**
- `enable` - Enable global dry-run mode
- `disable` - Disable global dry-run mode
- `status` - Show dry-run mode status

**Examples:**

```bash
# Enable dry-run mode
elastic-janitor bulk dry-run enable

# Disable dry-run mode
ej bulk dry-run disable

# Check status
ej bulk dry-run status
```

---

### 8.4 Operation History Log

**Command:** `elastic-janitor bulk history`

**Description:** View history of operations performed.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--limit` | int | No | `50` | Number of entries to show |
| `--operation` | string | No | `all` | Filter by operation type |
| `--status` | string | No | `all` | Filter by status: `success`, `failed`, `all` |
| `--time-range` | string | No | `7d` | Time range |
| `--export` | string | No | - | Export to file |

**Examples:**

```bash
# View recent operations
elastic-janitor bulk history

# View failed operations
ej bulk history --status failed --limit 100

# View specific operation type
ej bulk history --operation "index-delete" --time-range 30d

# Export history
ej bulk history --export history.json --output json
```

**Output Format:**
```
Operation History
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2024-01-15 14:30:25 | datastream-clean | SUCCESS | Deleted 45 indices (125 GB)
2024-01-15 10:15:10 | index-optimize   | SUCCESS | Optimized 12 indices
2024-01-14 22:05:33 | snapshot-delete  | SUCCESS | Deleted 8 snapshots
2024-01-14 18:45:12 | template-edit    | SUCCESS | Updated logs-template
2024-01-14 15:20:05 | index-delete     | FAILED  | Permission denied
```

---

### 8.5 Rollback Capability

**Command:** `elastic-janitor bulk rollback`

**Description:** Rollback recent operations.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--operation-id` | string | Yes | - | Operation ID to rollback |
| `--show-plan` | bool | No | `true` | Show rollback plan |
| `--confirm` | bool | No | `false` | Skip confirmation |

**Examples:**

```bash
# Rollback operation
elastic-janitor bulk rollback --operation-id "op-12345"

# Rollback with auto-confirm
ej bulk rollback --operation-id "op-12345" --confirm
```

**Note:** Not all operations are rollback-able. Deletions cannot be rolled back unless snapshots exist.

---

### 8.6 Export/Import Configurations

**Command:** `elastic-janitor bulk config export`
**Command:** `elastic-janitor bulk config import`

**Description:** Export/import cluster configurations.

**Options (export):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--output-dir` | string | No | `./config-backup` | Output directory |
| `--include` | string | No | `all` | What to export: `templates`, `pipelines`, `policies`, `all` |
| `--format` | string | No | `json` | Format: `json`, `yaml` |

**Options (import):**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--input-dir` | string | Yes | - | Input directory |
| `--overwrite` | bool | No | `false` | Overwrite existing |
| `--validate` | bool | No | `true` | Validate before import |

**Examples:**

```bash
# Export all configurations
elastic-janitor bulk config export

# Export specific resources
ej bulk config export --include templates,pipelines --output-dir ./backup

# Import configurations
ej bulk config import --input-dir ./backup --dry-run

# Import with overwrite
ej bulk config import --input-dir ./backup --overwrite
```

---

## 9. Advanced Cleanup Commands

### 9.1 Orphaned Document Cleanup

**Command:** `elastic-janitor cleanup orphaned-docs`

**Description:** Identify and clean up orphaned documents (documents without parent in parent-child relationships).

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--parent-field` | string | Yes | - | Parent field name |
| `--batch-size` | int | No | `1000` | Batch size for deletion |

**Examples:**

```bash
# Clean orphaned documents
elastic-janitor cleanup orphaned-docs --index "child-docs-*" --parent-field "parent_id"

# Clean with custom batch size
ej cleanup orphaned-docs --index "child-docs-*" --parent-field "parent_id" --batch-size 500 --dry-run
```

---

### 9.2 Field-Level Cleanup

**Command:** `elastic-janitor cleanup fields`

**Description:** Remove specific fields from documents.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--field` | string | Yes | - | Field name to remove |
| `--query` | string | No | - | Filter query (JSON) |
| `--batch-size` | int | No | `1000` | Batch size |

**Examples:**

```bash
# Remove field from all documents
elastic-janitor cleanup fields --index "logs-*" --field "temp_field"

# Remove field from filtered documents
ej cleanup fields --index "logs-*" --field "debug_info" \
  --query '{"range":{"@timestamp":{"lt":"2024-01-01"}}}'

# Remove with custom batch size
ej cleanup fields --index "logs-*" --field "old_field" --batch-size 500 --dry-run
```

---

### 9.3 Mapping Cleanup

**Command:** `elastic-janitor cleanup mappings`

**Description:** Clean up unused fields from index mappings.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index name |
| `--unused-only` | bool | No | `true` | Only remove unused fields |
| `--threshold` | float | No | `0.01` | Usage threshold (0.0-1.0) |

**Examples:**

```bash
# Clean unused mappings
elastic-janitor cleanup mappings --index "logs-2024.01.01"

# Clean fields used less than 5%
ej cleanup mappings --index "logs-2024.01.01" --threshold 0.05

# Preview cleanup
ej cleanup mappings --index "logs-2024.01.01" --dry-run
```

**Note:** This creates a new index with cleaned mappings and reindexes data.

---

### 9.4 Wildcard Index Deletion

**Command:** `elastic-janitor cleanup wildcard-delete`

**Description:** Delete indices matching complex wildcard patterns.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Wildcard pattern |
| `--exclude` | string | No | - | Exclusion pattern |
| `--age` | string | No | - | Only delete older than |
| `--confirm` | bool | No | `false` | Skip confirmation |

**Examples:**

```bash
# Delete indices matching pattern
elastic-janitor cleanup wildcard-delete --pattern "test-*-2023-*"

# Delete with exclusion
ej cleanup wildcard-delete --pattern "logs-*" --exclude "logs-prod-*"

# Delete old indices matching pattern
ej cleanup wildcard-delete --pattern "temp-*" --age 7d --dry-run
```

**Warning:** This is a destructive operation. Always use --dry-run first.

---

### 9.5 Time-Series Gap Detector

**Command:** `elastic-janitor cleanup gaps`

**Description:** Detect gaps in time-series data.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--time-field` | string | No | `@timestamp` | Time field name |
| `--interval` | string | No | `1d` | Expected interval |
| `--threshold` | string | No | `2x` | Gap threshold (e.g., `2x`, `1h`) |

**Examples:**

```bash
# Detect gaps in daily indices
elastic-janitor cleanup gaps --index "logs-*" --interval 1d

# Detect gaps with custom threshold
ej cleanup gaps --index "metrics-*" --interval 1h --threshold 3h

# Detect gaps in custom time field
ej cleanup gaps --index "events-*" --time-field "event_time" --interval 5m
```

**Output Format:**
```
Time-Series Gap Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index Pattern: logs-*
Expected Interval: 1 day
Gaps Detected: 3

Gap #1:
  Start: 2024-01-05 00:00:00
  End:   2024-01-07 00:00:00
  Duration: 2 days
  Missing Indices: logs-2024.01.05, logs-2024.01.06

Gap #2:
  Start: 2024-01-15 00:00:00
  End:   2024-01-16 00:00:00
  Duration: 1 day
  Missing Indices: logs-2024.01.15
```

---

### 9.6 Duplicate Document Detector

**Command:** `elastic-janitor cleanup duplicates`

**Description:** Detect and optionally remove duplicate documents.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--field` | string | Yes | - | Field(s) to check for duplicates (comma-separated) |
| `--action` | string | No | `detect` | Action: `detect`, `delete-oldest`, `delete-newest` |
| `--keep` | string | No | `newest` | Which to keep: `newest`, `oldest` |

**Examples:**

```bash
# Detect duplicates
elastic-janitor cleanup duplicates --index "logs-*" --field "message_id"

# Detect duplicates on multiple fields
ej cleanup duplicates --index "logs-*" --field "user_id,timestamp"

# Delete duplicate documents (keep newest)
ej cleanup duplicates --index "logs-*" --field "message_id" --action delete-oldest --dry-run

# Delete duplicates (keep oldest)
ej cleanup duplicates --index "logs-*" --field "message_id" --action delete-newest --keep oldest
```

**Output Format:**
```
Duplicate Document Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-2024.01.01
Duplicate Field: message_id
Total Documents: 1,000,000
Unique Documents: 985,000
Duplicate Documents: 15,000 (1.5%)

Sample Duplicates:
  message_id: msg-12345
    Count: 3
    Document IDs: doc-1, doc-2, doc-3

  message_id: msg-67890
    Count: 2
    Document IDs: doc-4, doc-5
```

---

## 10. Data Quality & Validation Commands

### 10.1 Missing Field Analyzer

**Command:** `elastic-janitor quality missing-fields`

**Description:** Analyze documents for missing required fields.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--fields` | string | Yes | - | Required fields (comma-separated) |
| `--sample-size` | int | No | `10000` | Sample size for analysis |
| `--show-examples` | bool | No | `true` | Show example documents |

**Examples:**

```bash
# Analyze missing fields
elastic-janitor quality missing-fields --index "logs-*" --fields "user_id,timestamp,level"

# Analyze with custom sample size
ej quality missing-fields --index "logs-*" --fields "user_id" --sample-size 50000

# Analyze without examples
ej dq missing-fields --index "logs-*" --fields "user_id,timestamp" --show-examples false
```

**Output Format:**
```
Missing Field Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-2024.01.01
Sample Size: 10,000 documents

Field: user_id
  Missing: 1,250 documents (12.5%)
  Present: 8,750 documents (87.5%)

Field: timestamp
  Missing: 0 documents (0%)
  Present: 10,000 documents (100%)

Field: level
  Missing: 350 documents (3.5%)
  Present: 9,650 documents (96.5%)

Example documents with missing fields:
  Document ID: doc-123
    Missing: user_id, level
```

---

### 10.2 Data Type Inconsistency Detector

**Command:** `elastic-janitor quality type-inconsistency`

**Description:** Detect data type inconsistencies across indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Index pattern |
| `--field` | string | No | `*` | Field pattern to check |
| `--show-conflicts` | bool | No | `true` | Show conflicting types |

**Examples:**

```bash
# Detect type inconsistencies
elastic-janitor quality type-inconsistency --pattern "logs-*"

# Check specific field
ej quality type-inconsistency --pattern "logs-*" --field "user_id"

# Check multiple fields
ej dq type-inconsistency --pattern "logs-*" --field "user_id,timestamp,count"
```

**Output Format:**
```
Data Type Inconsistency Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Field: user_id
  Inconsistency Detected: ⚠

  logs-2024.01.01: keyword
  logs-2024.01.02: keyword
  logs-2024.01.03: long      ← Conflict
  logs-2024.01.04: keyword

  Recommendation: Reindex logs-2024.01.03 with correct mapping

Field: count
  Inconsistency Detected: ⚠

  logs-2024.01.01: long
  logs-2024.01.02: integer   ← Conflict
  logs-2024.01.03: long

  Recommendation: Standardize to 'long' type
```

---

### 10.3 Null Value Statistics

**Command:** `elastic-janitor quality null-stats`

**Description:** Analyze null value distribution across fields.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--field` | string | No | `*` | Field pattern |
| `--threshold` | float | No | `0.1` | Null threshold to report (0.0-1.0) |
| `--sample-size` | int | No | `10000` | Sample size |

**Examples:**

```bash
# Analyze null values
elastic-janitor quality null-stats --index "logs-*"

# Analyze specific fields
ej quality null-stats --index "logs-*" --field "user_id,session_id"

# Report fields with >20% nulls
ej dq null-stats --index "logs-*" --threshold 0.2
```

**Output Format:**
```
Null Value Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-2024.01.01
Sample Size: 10,000 documents

Field: user_id
  Null: 1,250 (12.5%)
  Non-null: 8,750 (87.5%)
  Status: ⚠ Warning (>10% null)

Field: session_id
  Null: 450 (4.5%)
  Non-null: 9,550 (95.5%)
  Status: ✓ OK

Field: optional_field
  Null: 8,500 (85%)
  Non-null: 1,500 (15%)
  Status: ⚠ Warning (>10% null)

Recommendations:
  • Consider making user_id required or investigate data pipeline
  • optional_field has high null rate - consider removing if unused
```

---

### 10.4 Cardinality Analysis

**Command:** `elastic-janitor quality cardinality`

**Description:** Analyze field cardinality and uniqueness.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--field` | string | No | `*` | Field pattern |
| `--sample-size` | int | No | `10000` | Sample size |
| `--show-top-values` | int | No | `10` | Show top N values |

**Examples:**

```bash
# Analyze cardinality
elastic-janitor quality cardinality --index "logs-*"

# Analyze specific fields
ej quality cardinality --index "logs-*" --field "user_id,level,status"

# Show top 20 values
ej dq cardinality --index "logs-*" --field "level" --show-top-values 20
```

**Output Format:**
```
Cardinality Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-2024.01.01
Sample Size: 10,000 documents

Field: user_id
  Unique Values: 8,750
  Cardinality: 87.5%
  Type: High Cardinality

  Recommendation: Good candidate for keyword field

Field: level
  Unique Values: 4
  Cardinality: 0.04%
  Type: Low Cardinality

  Top Values:
    INFO:  6,500 (65%)
    WARN:  2,000 (20%)
    ERROR: 1,200 (12%)
    DEBUG:   300 (3%)

  Recommendation: Consider using constant_keyword or enum

Field: status
  Unique Values: 12
  Cardinality: 0.12%
  Type: Low Cardinality

  Recommendation: Good candidate for aggregations
```

---

### 10.5 Field Mapping Conflict Resolver

**Command:** `elastic-janitor quality resolve-conflicts`

**Description:** Resolve field mapping conflicts across indices.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | Yes | - | Index pattern |
| `--field` | string | Yes | - | Field name with conflict |
| `--target-type` | string | Yes | - | Target data type |
| `--strategy` | string | No | `reindex` | Strategy: `reindex`, `ignore`, `delete` |

**Examples:**

```bash
# Resolve mapping conflict
elastic-janitor quality resolve-conflicts --pattern "logs-*" --field "user_id" --target-type "keyword"

# Resolve with reindex strategy
ej quality resolve-conflicts --pattern "logs-*" --field "count" --target-type "long" --strategy reindex

# Preview resolution
ej dq resolve-conflicts --pattern "logs-*" --field "user_id" --target-type "keyword" --dry-run
```

**Output Format:**
```
Mapping Conflict Resolution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Field: user_id
Target Type: keyword
Strategy: reindex

Indices to Update:
  ✓ logs-2024.01.01 (already keyword)
  ✓ logs-2024.01.02 (already keyword)
  ⚠ logs-2024.01.03 (currently long) - Will reindex
  ✓ logs-2024.01.04 (already keyword)

Reindex Plan:
  1. Create new index: logs-2024.01.03-v2
  2. Update mapping: user_id -> keyword
  3. Reindex data from logs-2024.01.03
  4. Verify data integrity
  5. Delete old index: logs-2024.01.03
  6. Create alias: logs-2024.01.03 -> logs-2024.01.03-v2

Estimated Time: 15 minutes
Estimated Downtime: 0 (using aliases)
```

---

## 11. AWS Ingestion Management Commands

### 11.1 Firehose/Forwarder Health Check

**Command:** `elastic-janitor aws health-check`

**Description:** Check health of AWS Firehose and Lambda forwarders.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | No | `*` | Index pattern to check |
| `--time-range` | string | No | `1h` | Time range to analyze |
| `--show-metrics` | bool | No | `true` | Show ingestion metrics |

**Examples:**

```bash
# Check Firehose health
elastic-janitor aws health-check

# Check specific index pattern
ej aws health-check --index "aws-logs-*" --time-range 24h

# Check without metrics
ej aws health-check --show-metrics false
```

**Output Format:**
```
AWS Ingestion Health Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: aws-logs-firehose-2024.01.01
Status: ✓ Healthy

Ingestion Metrics (Last 1 hour):
  Documents Received: 125,000
  Ingestion Rate: 34.7 docs/sec
  Failed Documents: 12 (0.01%)
  Avg Latency: 250ms

Firehose Configuration:
  Delivery Stream: logs-to-elasticsearch
  Buffer Size: 5 MB
  Buffer Interval: 60 seconds
  Retry Duration: 300 seconds

Issues Detected: None
```

---

### 11.2 Common Issue Detection

**Command:** `elastic-janitor aws detect-issues`

**Description:** Detect common AWS ingestion issues.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | No | `*` | Index pattern |
| `--time-range` | string | No | `1h` | Time range |
| `--severity` | string | No | `all` | Filter by severity: `critical`, `warning`, `info`, `all` |

**Examples:**

```bash
# Detect all issues
elastic-janitor aws detect-issues

# Detect critical issues only
ej aws detect-issues --severity critical --time-range 24h

# Detect issues for specific index
ej aws detect-issues --index "aws-logs-*"
```

**Output Format:**
```
AWS Ingestion Issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 CRITICAL: High failure rate detected
   Index: aws-logs-firehose-2024.01.01
   Failure Rate: 15% (last 1 hour)
   Cause: Mapping conflicts on field 'timestamp'

   Recommendation: Fix mapping conflict using:
   ej quality resolve-conflicts --pattern "aws-logs-*" --field "timestamp" --target-type "date"

⚠ WARNING: Ingestion lag detected
   Index: aws-logs-lambda-2024.01.01
   Lag: 15 minutes
   Cause: Lambda function throttling

   Recommendation: Increase Lambda concurrency or batch size

ℹ INFO: Unusual field detected
   Index: aws-logs-firehose-2024.01.01
   Field: _firehose_error
   Documents: 125

   Recommendation: Investigate Firehose transformation errors
```

---

### 11.3 Field Structure Analysis

**Command:** `elastic-janitor aws analyze-fields`

**Description:** Analyze field structure from AWS ingestion sources.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--sample-size` | int | No | `1000` | Sample size |
| `--show-nested` | bool | No | `true` | Show nested field structure |

**Examples:**

```bash
# Analyze field structure
elastic-janitor aws analyze-fields --index "aws-logs-*"

# Analyze with larger sample
ej aws analyze-fields --index "aws-logs-*" --sample-size 10000

# Analyze without nested fields
ej aws analyze-fields --index "aws-logs-*" --show-nested false
```

---

### 11.4 Pipeline Troubleshooting

**Command:** `elastic-janitor aws troubleshoot-pipeline`

**Description:** Troubleshoot AWS ingestion pipeline issues.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pipeline` | string | Yes | - | Pipeline name |
| `--index` | string | No | - | Index pattern using pipeline |
| `--show-failures` | bool | No | `true` | Show pipeline failures |

**Examples:**

```bash
# Troubleshoot pipeline
elastic-janitor aws troubleshoot-pipeline --pipeline "aws-logs-pipeline"

# Troubleshoot with index context
ej aws troubleshoot-pipeline --pipeline "aws-logs-pipeline" --index "aws-logs-*"
```

---

### 11.5 Data Quality Metrics

**Command:** `elastic-janitor aws quality-metrics`

**Description:** Generate data quality metrics for AWS ingestion.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--index` | string | Yes | - | Index pattern |
| `--time-range` | string | No | `24h` | Time range |
| `--metrics` | string | No | `all` | Metrics: `completeness`, `accuracy`, `timeliness`, `all` |

**Examples:**

```bash
# Generate quality metrics
elastic-janitor aws quality-metrics --index "aws-logs-*"

# Generate specific metrics
ej aws quality-metrics --index "aws-logs-*" --metrics completeness,timeliness
```

---

### 11.6 Quick Fixes & Actions

**Command:** `elastic-janitor aws quick-fix`

**Description:** Apply quick fixes for common AWS ingestion issues.

**Subcommands:**
- `fix-mapping` - Fix mapping conflicts
- `fix-pipeline` - Fix pipeline errors
- `fix-throttling` - Fix throttling issues
- `fix-permissions` - Fix permission issues

**Examples:**

```bash
# Fix mapping conflicts
elastic-janitor aws quick-fix fix-mapping --index "aws-logs-*"

# Fix pipeline errors
ej aws quick-fix fix-pipeline --pipeline "aws-logs-pipeline"

# Fix throttling
ej aws quick-fix fix-throttling --index "aws-logs-*"
```

---

## 12. Data Quality & Governance Commands

### 12.1 Schema Evolution Tracker

**Command:** `elastic-janitor governance schema-evolution`

**Description:** Track mapping changes over time across indices matching a pattern.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to track |
| `--days` | int | No | `30` | Number of days to look back |

**Examples:**

```bash
# Track schema evolution for logs indices
elastic-janitor governance schema-evolution --pattern "logs-*"

# Look back 60 days
elastic-janitor governance schema-evolution --days 60

# Export to JSON
ej governance schema-evolution --pattern "metrics-*" --output json
```

**Output Format:**
```
Schema Evolution Timeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index Pattern: logs-*
Time Range: Last 30 days

Changes Detected:
  2024-01-15: logs-app-2024.01.15
    + Added field: response_time (type: long)
    + Added field: user_agent (type: keyword)

  2024-01-20: logs-app-2024.01.20
    ~ Modified field: status_code (text → keyword)
    - Removed field: deprecated_field

  2024-01-25: logs-app-2024.01.25
    + Added field: geo.location (type: geo_point)

Total Changes: 6 additions, 1 modification, 1 removal
```

**Use Cases:**
- Monitor schema drift across time-series indices
- Identify breaking changes in mappings
- Track field additions and removals
- Audit mapping evolution for compliance

---

### 12.2 Data Lineage Viewer

**Command:** `elastic-janitor governance data-lineage`

**Description:** Visualize data flow through ingest pipelines and transforms.

**Examples:**

```bash
# View data lineage
elastic-janitor governance data-lineage

# Export lineage graph
ej governance data-lineage --output json
```

**Output Format:**
```
Data Lineage Graph
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pipeline: logs-processing
  ↓
  Processors:
    1. grok (parse log format)
    2. date (parse timestamp)
    3. geoip (enrich with location)
  ↓
  Target Index: logs-processed-*

Transform: logs-aggregation
  Source: logs-processed-*
  ↓
  Aggregations:
    - Group by: host.name
    - Metrics: count, avg(response_time)
  ↓
  Destination: logs-summary

Total Pipelines: 3
Total Transforms: 1
```

**Use Cases:**
- Understand data flow through the cluster
- Identify pipeline dependencies
- Troubleshoot data processing issues
- Document data architecture

---

### 12.3 PII Detection

**Command:** `elastic-janitor governance pii-detection`

**Description:** Scan documents for PII patterns (emails, SSNs, phone numbers, credit cards, etc.).

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to scan |
| `--sample-size` | int | No | `1000` | Sample size per index |

**Examples:**

```bash
# Scan for PII in logs indices
elastic-janitor governance pii-detection --pattern "logs-*"

# Use larger sample size
ej governance pii-detection --sample-size 5000

# Export findings to JSON
ej governance pii-detection --pattern "user-data-*" --output json
```

**Output Format:**
```
PII Detection Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: user-logs-2024.01.01
Sample Size: 1,000 documents

PII Patterns Found:
  ✓ Email Addresses: 45 occurrences in field 'message'
  ✓ Phone Numbers: 12 occurrences in field 'contact_info'
  ✓ SSN: 3 occurrences in field 'user_data'
  ⚠ Credit Cards: 8 occurrences in field 'payment_info'

Recommendations:
  • Consider masking email addresses in 'message' field
  • Implement field-level security for 'payment_info'
  • Review data retention policies for PII fields
  • Enable audit logging for PII access

Risk Level: HIGH
```

**Use Cases:**
- Identify PII exposure risks
- Ensure GDPR/CCPA compliance
- Audit data for sensitive information
- Plan data masking strategies

---

### 12.4 Data Quality Scoring

**Command:** `elastic-janitor governance quality-score`

**Description:** Score indices based on completeness, consistency, and validity.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to score |
| `--sample-size` | int | No | `1000` | Sample size per index |
| `--threshold` | int | No | `70` | Quality threshold (0-100) |

**Examples:**

```bash
# Score data quality
elastic-janitor governance quality-score --pattern "logs-*"

# Set custom threshold
ej governance quality-score --threshold 80

# Export scores to CSV
ej governance quality-score --pattern "metrics-*" --output csv
```

**Output Format:**
```
Data Quality Scores
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-app-2024.01.01
Sample Size: 1,000 documents

Quality Metrics:
  Completeness: 92% ✓
    - Required fields present: 95%
    - Null values: 8%

  Consistency: 85% ✓
    - Type consistency: 98%
    - Format consistency: 72%

  Validity: 78% ✓
    - Valid values: 88%
    - Range compliance: 68%

Overall Score: 85/100 ✓ PASS

Recommendations:
  • Improve format consistency in 'timestamp' field
  • Validate range for 'response_time' field
  • Reduce null values in 'user_id' field
```

**Use Cases:**
- Monitor data quality over time
- Identify data quality issues
- Set quality standards and thresholds
- Generate quality reports for stakeholders

---

### 12.5 Metadata Management

**Command:** `elastic-janitor governance metadata`

**Description:** Manage index metadata (owner, purpose, sensitivity, retention, etc.).

**Examples:**

```bash
# Manage metadata interactively
elastic-janitor governance metadata

# View metadata for specific index
ej governance metadata --index "logs-app-*"
```

**Output Format:**
```
Index Metadata Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-app-2024.01.01

Current Metadata:
  Owner: platform-team
  Purpose: Application logging
  Sensitivity: Internal
  Retention: 90 days
  Cost Center: engineering
  Tags: production, monitoring

Actions:
  1. Add metadata
  2. Update metadata
  3. Remove metadata
  4. Search by metadata
  5. Export metadata
```

**Use Cases:**
- Track index ownership and responsibility
- Classify data by sensitivity level
- Manage retention policies
- Enable cost allocation and chargeback

---

### 12.6 Data Dictionary

**Command:** `elastic-janitor governance dictionary`

**Description:** Maintain field documentation and data dictionary.

**Examples:**

```bash
# Manage data dictionary
elastic-janitor governance dictionary

# Export dictionary to JSON
ej governance dictionary --output json
```

**Output Format:**
```
Data Dictionary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index Pattern: logs-app-*

Field Definitions:
  @timestamp
    Type: date
    Description: Event timestamp in ISO 8601 format
    Example: 2024-01-01T12:00:00Z
    Required: Yes
    Owner: platform-team

  response_time
    Type: long
    Description: HTTP response time in milliseconds
    Example: 250
    Valid Range: 0-30000
    Owner: api-team

  user_id
    Type: keyword
    Description: Unique user identifier
    Example: user_12345
    PII: Yes
    Owner: identity-team

Total Fields: 45
Documented: 38 (84%)
```

**Use Cases:**
- Document field meanings and usage
- Maintain data catalog
- Onboard new team members
- Ensure consistent field usage

---

## 13. Performance Tuning Commands

### 13.1 Auto-Tuning Engine

**Command:** `elastic-janitor tuning auto-tune`

**Description:** Analyze cluster and recommend performance optimizations.

**Examples:**

```bash
# Run auto-tuning analysis
elastic-janitor tuning auto-tune

# Export recommendations to JSON
ej tuning auto-tune --output json
```

**Output Format:**
```
Auto-Tuning Recommendations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cluster Analysis Complete

Recommendations:
  1. Shard Count Optimization
     Current: 1,250 shards across 5 nodes
     Recommended: 750 shards (reduce by 40%)
     Impact: Improved cluster stability, reduced overhead

  2. Refresh Interval Tuning
     Indices: logs-*
     Current: 1s
     Recommended: 30s
     Impact: 30% improvement in indexing throughput

  3. Merge Policy Adjustment
     Indices: metrics-*
     Current: default
     Recommended: max_merged_segment=5gb
     Impact: Reduced segment count, better search performance

  4. Cache Configuration
     Query Cache: Increase to 15% (currently 10%)
     Request Cache: Enable for time-series indices
     Impact: 25% improvement in query response time

Priority: HIGH
Estimated Performance Gain: 35%
```

**Use Cases:**
- Optimize cluster performance automatically
- Identify performance bottlenecks
- Get actionable recommendations
- Improve resource utilization

---

### 13.2 Shard Size Optimizer

**Command:** `elastic-janitor tuning shard-optimizer`

**Description:** Analyze shard distribution and recommend optimal shard counts.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--target-size` | int | No | `30` | Target shard size in GB |

**Examples:**

```bash
# Analyze with default 30GB target
elastic-janitor tuning shard-optimizer

# Use custom target size
ej tuning shard-optimizer --target-size 50
```

**Output Format:**
```
Shard Size Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Target Shard Size: 30 GB

Index: logs-app-2024.01.01
  Current Shards: 10
  Avg Shard Size: 5.2 GB
  Total Size: 52 GB
  Recommended Shards: 2
  Status: ⚠ OVER-SHARDED

Index: metrics-system-2024.01.01
  Current Shards: 1
  Avg Shard Size: 85 GB
  Total Size: 85 GB
  Recommended Shards: 3
  Status: ⚠ UNDER-SHARDED

Recommendations:
  • Reduce shards for logs-app-* from 10 to 2
  • Increase shards for metrics-system-* from 1 to 3
  • Consider using rollover for time-series indices

Total Shards: 250
Optimal Shards: 180
Potential Savings: 28% reduction in overhead
```

**Use Cases:**
- Optimize shard distribution
- Prevent over-sharding and under-sharding
- Improve cluster performance
- Plan index template shard settings

---

### 13.3 Refresh Interval Tuner

**Command:** `elastic-janitor tuning refresh-interval`

**Description:** Analyze and optimize refresh intervals based on workload.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to analyze |

**Examples:**

```bash
# Analyze refresh intervals
elastic-janitor tuning refresh-interval --pattern "logs-*"

# Export analysis to JSON
ej tuning refresh-interval --output json
```

**Output Format:**
```
Refresh Interval Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-app-2024.01.01
  Current Interval: 1s
  Indexing Rate: 5,000 docs/sec
  Search Rate: 10 queries/sec
  Recommended: 30s
  Reason: High indexing, low search frequency
  Impact: +40% indexing throughput

Index: search-catalog
  Current Interval: 1s
  Indexing Rate: 50 docs/sec
  Search Rate: 500 queries/sec
  Recommended: 1s (keep current)
  Reason: High search frequency requires near real-time
  Impact: No change

Recommendations:
  • Increase refresh interval for bulk indexing indices
  • Keep 1s for user-facing search indices
  • Consider -1 (disable) during bulk operations

Estimated Performance Gain: 35% for indexing workloads
```

**Use Cases:**
- Balance indexing vs search performance
- Optimize for specific workload patterns
- Reduce indexing overhead
- Improve bulk indexing speed

---

### 13.4 Merge Policy Optimizer

**Command:** `elastic-janitor tuning merge-policy`

**Description:** Analyze segments and recommend merge policy optimizations.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to analyze |

**Examples:**

```bash
# Analyze merge policies
elastic-janitor tuning merge-policy --pattern "logs-*"

# Export recommendations
ej tuning merge-policy --output json
```

**Output Format:**
```
Merge Policy Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Index: logs-app-2024.01.01
  Total Segments: 450
  Avg Segment Size: 250 MB
  Largest Segment: 4.2 GB
  Current Policy: default

  Recommended Policy:
    max_merged_segment: 5gb
    segments_per_tier: 8
    max_merge_at_once: 5

  Impact:
    • Reduce segment count by 60%
    • Improve search performance by 25%
    • Reduce merge I/O overhead

Status: ⚠ TOO MANY SEGMENTS

Recommendations:
  • Force merge read-only indices to 1 segment
  • Adjust merge policy for active indices
  • Monitor merge throttling settings

Total Indices Analyzed: 25
Indices Needing Optimization: 12
```

**Use Cases:**
- Optimize segment structure
- Reduce segment overhead
- Improve search performance
- Manage merge I/O impact

---

### 13.5 Cache Tuning

**Command:** `elastic-janitor tuning cache`

**Description:** Analyze cache performance and recommend optimizations.

**Examples:**

```bash
# Analyze cache performance
elastic-janitor tuning cache

# Export metrics to JSON
ej tuning cache --output json
```

**Output Format:**
```
Cache Performance Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query Cache:
  Size: 10% of heap (2.5 GB)
  Hit Rate: 45%
  Evictions: 12,500/hour
  Recommendation: Increase to 15%
  Impact: +20% hit rate, fewer evictions

Request Cache:
  Size: 1% of heap (256 MB)
  Hit Rate: 78%
  Evictions: 500/hour
  Recommendation: Keep current size
  Impact: Performing well

Field Data Cache:
  Size: 8.2 GB (82% of limit)
  Circuit Breaker: 10 GB
  Recommendation: Increase limit to 12 GB
  Impact: Prevent circuit breaker trips

Shard Request Cache:
  Enabled Indices: 45/100
  Recommendation: Enable for time-series indices
  Impact: Improved aggregation performance

Recommendations:
  • Increase query cache to 15%
  • Enable request cache for logs-* indices
  • Monitor field data usage
  • Consider doc values for high-cardinality fields

Estimated Performance Gain: 30% for cached queries
```

**Use Cases:**
- Optimize cache configuration
- Improve query performance
- Reduce cache evictions
- Prevent circuit breaker trips

---

### 13.6 JVM Tuning Assistant

**Command:** `elastic-janitor tuning jvm`

**Description:** Analyze JVM performance and recommend heap/GC optimizations.

**Examples:**

```bash
# Analyze JVM performance
elastic-janitor tuning jvm

# Export recommendations
ej tuning jvm --output json
```

**Output Format:**
```
JVM Performance Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Node: es-node-1

Heap Configuration:
  Current: 16 GB
  Usage: 12.8 GB (80%)
  Recommendation: Increase to 24 GB
  Reason: Frequent GC pressure

GC Statistics:
  Young GC: 450/hour (avg 50ms)
  Old GC: 12/hour (avg 2.5s)
  GC Overhead: 8%
  Recommendation: Tune GC settings

  Suggested GC Flags:
    -XX:+UseG1GC
    -XX:MaxGCPauseMillis=200
    -XX:G1HeapRegionSize=16m
    -XX:InitiatingHeapOccupancyPercent=45

Memory Pressure:
  Circuit Breaker Trips: 25/day
  OOM Errors: 0
  Recommendation: Increase heap or reduce cache sizes

Thread Pools:
  Search: 85% utilization
  Write: 45% utilization
  Recommendation: Increase search threads from 13 to 20

Recommendations:
  • Increase heap to 24 GB (50% of 48 GB RAM)
  • Apply recommended GC flags
  • Monitor GC logs for improvements
  • Consider adding nodes if heap > 32 GB needed

Priority: HIGH
Estimated Performance Gain: 40% reduction in GC pauses
```

**Use Cases:**
- Optimize JVM heap size
- Tune garbage collection
- Prevent OOM errors
- Improve node stability

---

## 14. Dashboard & Stats Commands

### 14.1 Real-time Monitoring Dashboard

**Command:** `elastic-janitor dashboard`

**Description:** Launch interactive real-time monitoring dashboard.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--refresh` | int | No | `5` | Refresh interval in seconds |
| `--metrics` | string | No | `all` | Metrics to display: `cluster`, `indices`, `ingestion`, `all` |
| `--layout` | string | No | `default` | Layout: `default`, `compact`, `detailed` |

**Examples:**

```bash
# Launch dashboard
elastic-janitor dashboard

# Launch with custom refresh
ej dashboard --refresh 10

# Launch with specific metrics
ej dashboard --metrics cluster,indices --layout compact
```

**Dashboard Layout:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Elastic Janitor Dashboard                            │
│                    Cluster: production-cluster                          │
│                    Updated: 2024-01-15 14:30:25                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Cluster Health                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Status: 🟢 GREEN                                                        │
│ Nodes: 12 (3 master, 9 data)                                           │
│ Indices: 1,245                                                          │
│ Shards: 6,225 (3,112 primary, 3,113 replica)                          │
│ Documents: 2.5B                                                         │
│ Storage: 5.2 TB                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Performance Metrics                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Indexing Rate: 1,250 docs/sec                                          │
│ Search Rate: 450 queries/sec                                           │
│ CPU Usage: 45%                                                          │
│ Memory Usage: 78%                                                       │
│ Disk Usage: 65%                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Recent Activity                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ 14:30:15 | Index created: logs-2024.01.15                              │
│ 14:25:10 | Snapshot completed: daily-2024.01.15                        │
│ 14:20:05 | ILM policy executed on 45 indices                           │
│ 14:15:00 | Data stream rolled over: metrics-app                        │
└─────────────────────────────────────────────────────────────────────────┘

Press 'q' to quit, 'r' to refresh, 'h' for help
```

---

### 12.2 Dashboard Subcommands

#### 12.2.1 Cluster Overview

**Command:** `elastic-janitor dashboard cluster`

**Description:** Display cluster-focused dashboard.

**Examples:**

```bash
# Cluster dashboard
elastic-janitor dashboard cluster
```

---

#### 12.2.2 Index Overview

**Command:** `elastic-janitor dashboard indices`

**Description:** Display index-focused dashboard.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--pattern` | string | No | `*` | Index pattern to monitor |
| `--sort-by` | string | No | `size` | Sort by: `size`, `docs`, `name` |

**Examples:**

```bash
# Index dashboard
elastic-janitor dashboard indices

# Monitor specific pattern
ej dashboard indices --pattern "logs-*"
```

---

#### 12.2.3 Performance Dashboard

**Command:** `elastic-janitor dashboard performance`

**Description:** Display performance-focused dashboard.

**Examples:**

```bash
# Performance dashboard
elastic-janitor dashboard performance
```

---

#### 12.2.4 Export Dashboard Data

**Command:** `elastic-janitor dashboard export`

**Description:** Export dashboard data to file.

**Options:**
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--output` | string | Yes | - | Output file path |
| `--format` | string | No | `json` | Format: `json`, `csv`, `html` |
| `--metrics` | string | No | `all` | Metrics to export |

**Examples:**

```bash
# Export dashboard data
elastic-janitor dashboard export --output dashboard.json

# Export as HTML report
ej dashboard export --output report.html --format html

# Export specific metrics
ej dashboard export --output metrics.csv --format csv --metrics cluster,indices
```

---

## 15. Global Dry-Run Mode Commands

### 15.1 Toggle Dry-Run Mode

**Command:** `elastic-janitor dry-run enable`
**Command:** `elastic-janitor dry-run disable`

**Description:** Enable or disable global dry-run mode.

**Examples:**

```bash
# Enable dry-run mode
elastic-janitor dry-run enable

# Disable dry-run mode
ej dry-run disable
```

**Output:**
```
✓ Dry-run mode ENABLED

All destructive operations will now show what would be changed
without actually making changes.

To disable: elastic-janitor dry-run disable
```

---

### 15.2 Check Dry-Run Status

**Command:** `elastic-janitor dry-run status`

**Description:** Check current dry-run mode status.

**Examples:**

```bash
# Check status
elastic-janitor dry-run status
```

**Output:**
```
Dry-Run Mode Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Global Dry-Run Mode: ENABLED
Enabled Since: 2024-01-15 14:00:00
Operations Prevented: 125

Recent Dry-Run Operations:
  • index delete (prevented deletion of 45 indices)
  • datastream clean (prevented deletion of 120 backing indices)
  • snapshot delete (prevented deletion of 8 snapshots)
```

---

## Error Handling

### Common Error Scenarios

#### Connection Errors

```bash
$ elastic-janitor cluster health
Error: Could not connect to Elasticsearch cluster
  URL: https://localhost:9200
  Cause: Connection refused

Suggestions:
  • Check if Elasticsearch is running
  • Verify ELASTIC_URL in configuration
  • Check network connectivity
  • Verify API key is valid
```

#### Permission Errors

```bash
$ elastic-janitor index delete --pattern "logs-*"
Error: Permission denied
  Operation: indices:admin/delete
  User: readonly_user

Suggestions:
  • Check user permissions
  • Verify API key has required privileges
  • Contact cluster administrator
```

#### Validation Errors

```bash
$ elastic-janitor datastream clean --retention invalid
Error: Invalid retention period: 'invalid'
  Expected format: <number><unit>
  Valid units: s, m, h, d, w, M, y
  Examples: 30d, 6h, 1y

Usage: elastic-janitor datastream clean --retention <period>
```

#### Resource Not Found

```bash
$ elastic-janitor index view --index "nonexistent"
Error: Index not found: 'nonexistent'

Suggestions:
  • Check index name spelling
  • List available indices: elastic-janitor index list
  • Use pattern matching: elastic-janitor index view --index "logs-*"
```

---

## Exit Codes

The CLI uses standard exit codes:

| Code | Meaning | Description |
|------|---------|-------------|
| `0` | Success | Operation completed successfully |
| `1` | General Error | Unspecified error occurred |
| `2` | Misuse | Invalid command or arguments |
| `3` | Connection Error | Could not connect to Elasticsearch |
| `4` | Permission Error | Insufficient permissions |
| `5` | Resource Not Found | Requested resource does not exist |
| `6` | Validation Error | Invalid input or configuration |
| `7` | Operation Failed | Operation failed during execution |
| `8` | Timeout | Operation timed out |
| `130` | Interrupted | Operation interrupted by user (Ctrl+C) |

**Example Usage in Scripts:**

```bash
#!/bin/bash

# Run cleanup with error handling
elastic-janitor datastream clean --retention 90d

case $? in
  0)
    echo "Cleanup completed successfully"
    ;;
  3)
    echo "Could not connect to cluster"
    exit 1
    ;;
  4)
    echo "Permission denied"
    exit 1
    ;;
  *)
    echo "Cleanup failed"
    exit 1
    ;;
esac
```

---

## Advanced Usage Examples

### Example 1: Automated Daily Cleanup

```bash
#!/bin/bash
# daily-cleanup.sh

# Enable dry-run for testing
elastic-janitor dry-run enable

# Clean old data streams
elastic-janitor datastream clean \
  --retention 90d \
  --pattern "logs-*" \
  --batch-size 100

# Clean old snapshots
elastic-janitor snapshot delete \
  --repo "backup-repo" \
  --retention 30d \
  --keep-last 10

# Optimize indices
elastic-janitor index optimize \
  --index "logs-$(date -d '1 day ago' +%Y.%m.%d)" \
  --max-segments 1

# Disable dry-run for production
elastic-janitor dry-run disable
```

---

### Example 2: Health Check and Alerting

```bash
#!/bin/bash
# health-check.sh

# Check cluster health
STATUS=$(elastic-janitor cluster health --output json | jq -r '.status')

if [ "$STATUS" != "green" ]; then
  # Send alert
  curl -X POST https://hooks.slack.com/... \
    -d "{\"text\":\"Cluster health is $STATUS\"}"

  # Get detailed diagnostics
  elastic-janitor cluster health --level indices > health-report.txt

  # Email report
  mail -s "Cluster Health Alert" admin@example.com < health-report.txt
fi
```

---

### Example 3: Cost Optimization Workflow

```bash
#!/bin/bash
# cost-optimization.sh

# Generate cost report
elastic-janitor storage cost \
  --show-optimizations \
  --output json > cost-report.json

# Identify optimization opportunities
SAVINGS=$(jq -r '.potential_savings' cost-report.json)

echo "Potential monthly savings: \$$SAVINGS"

# Apply optimizations
elastic-janitor index migrate \
  --index "logs-*" \
  --to-tier cold \
  --age 90d

elastic-janitor storage compression \
  --pattern "logs-*" \
  --min-size 10GB

elastic-janitor storage cleanup-empty
```

---

### Example 4: Data Quality Monitoring

```bash
#!/bin/bash
# data-quality-check.sh

# Check for missing fields
elastic-janitor quality missing-fields \
  --index "logs-$(date +%Y.%m.%d)" \
  --fields "user_id,timestamp,level" \
  --output json > missing-fields.json

# Check for type inconsistencies
elastic-janitor quality type-inconsistency \
  --pattern "logs-*" \
  --output json > type-conflicts.json

# Check for duplicates
elastic-janitor cleanup duplicates \
  --index "logs-$(date +%Y.%m.%d)" \
  --field "message_id" \
  --action detect \
  --output json > duplicates.json

# Generate quality report
cat > quality-report.html <<EOF
<html>
<body>
<h1>Data Quality Report - $(date)</h1>
<h2>Missing Fields</h2>
<pre>$(cat missing-fields.json)</pre>
<h2>Type Conflicts</h2>
<pre>$(cat type-conflicts.json)</pre>
<h2>Duplicates</h2>
<pre>$(cat duplicates.json)</pre>
</body>
</html>
EOF
```

---

### Example 5: Backup and Disaster Recovery

```bash
#!/bin/bash
# backup-and-verify.sh

# Create snapshot
SNAPSHOT_NAME="backup-$(date +%Y%m%d-%H%M%S)"

elastic-janitor snapshot create \
  --repo "backup-repo" \
  --name "$SNAPSHOT_NAME" \
  --indices "logs-*,metrics-*" \
  --wait

# Verify snapshot
elastic-janitor snapshot verify \
  --repo "backup-repo"

# Export configurations
elastic-janitor bulk config export \
  --output-dir "./config-backup-$(date +%Y%m%d)" \
  --include all

# Test restore (dry-run)
elastic-janitor snapshot restore \
  --repo "backup-repo" \
  --snapshot "$SNAPSHOT_NAME" \
  --indices "logs-2024.01.01" \
  --rename-pattern "test-{index}" \
  --dry-run

echo "Backup completed: $SNAPSHOT_NAME"
```

---

## Best Practices

### 1. Always Use Dry-Run First

```bash
# Test command with dry-run
elastic-janitor datastream clean --retention 30d --dry-run

# Review output, then run for real
elastic-janitor datastream clean --retention 30d
```

### 2. Use Configuration Files

```bash
# Store credentials in config file
cat > ~/.elastic-janitor/config.yaml <<EOF
elasticsearch:
  url: "https://cluster:9243"
  api_key: "your-api-key"
EOF

# Use config file
elastic-janitor cluster health --config ~/.elastic-janitor/config.yaml
```

### 3. Leverage Output Formats

```bash
# JSON for scripting
elastic-janitor cluster health --output json | jq '.status'

# CSV for spreadsheets
elastic-janitor index largest --output csv > indices.csv

# Table for humans
elastic-janitor index largest --output table
```

### 4. Monitor Operations

```bash
# View operation history
elastic-janitor bulk history --limit 100

# Export history for auditing
elastic-janitor bulk history --export audit.json --time-range 30d
```

### 5. Use Scheduled Jobs

```bash
# Create scheduled cleanup
elastic-janitor bulk schedule create \
  --name "weekly-cleanup" \
  --schedule "0 2 * * 0" \
  --operation "datastream-clean" \
  --config cleanup.yaml
```

---

## Troubleshooting

### Command Not Found

```bash
# Ensure elastic-janitor is in PATH
export PATH=$PATH:/path/to/elastic-janitor

# Or use full path
/path/to/elastic-janitor cluster health

# Or create alias
alias ej='elastic-janitor'
```

### Slow Performance

```bash
# Increase timeout
elastic-janitor cluster health --timeout 60s

# Reduce batch size
elastic-janitor datastream clean --batch-size 10

# Use parallel operations
elastic-janitor bulk index close --pattern "old-*" --parallel 5
```

### Memory Issues

```bash
# Reduce sample size
elastic-janitor quality cardinality --sample-size 1000

# Process in smaller batches
elastic-janitor cleanup duplicates --batch-size 100
```

---

## Appendix

### A. Time Period Format

Valid time period formats:
- `s` - seconds (e.g., `30s`)
- `m` - minutes (e.g., `15m`)
- `h` - hours (e.g., `6h`)
- `d` - days (e.g., `30d`)
- `w` - weeks (e.g., `4w`)
- `M` - months (e.g., `3M`)
- `y` - years (e.g., `1y`)

### B. Size Format

Valid size formats:
- `b` or `B` - bytes
- `kb` or `KB` - kilobytes
- `mb` or `MB` - megabytes
- `gb` or `GB` - gigabytes
- `tb` or `TB` - terabytes

### C. Cron Expression Format

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
* * * * *
```

Examples:
- `0 2 * * *` - Daily at 2:00 AM
- `0 */6 * * *` - Every 6 hours
- `0 2 * * 0` - Weekly on Sunday at 2:00 AM
- `0 2 1 * *` - Monthly on the 1st at 2:00 AM

### D. Query DSL Examples

**Match Query:**
```json
{
  "query": {
    "match": {
      "message": "error"
    }
  }
}
```

**Range Query:**
```json
{
  "query": {
    "range": {
      "@timestamp": {
        "gte": "2024-01-01",
        "lt": "2024-02-01"
      }
    }
  }
}
```

**Bool Query:**
```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"level": "error"}},
        {"range": {"@timestamp": {"gte": "now-1d"}}}
      ],
      "must_not": [
        {"term": {"status": "resolved"}}
      ]
    }
  }
}
```

---

## Support and Resources

### Documentation
- Official Docs: https://elastic-janitor.readthedocs.io
- GitHub: https://github.com/your-org/elastic-janitor
- Issue Tracker: https://github.com/your-org/elastic-janitor/issues

### Community
- Slack: https://elastic-janitor.slack.com
- Forum: https://discuss.elastic-janitor.io
- Stack Overflow: Tag `elastic-janitor`

### Getting Help

```bash
# Command help
elastic-janitor --help
elastic-janitor <command> --help

# Version info
elastic-janitor --version

# Verbose output for debugging
elastic-janitor <command> --verbose
```

---

**End of CLI Command Library**

*Last Updated: 2026-02-13*
*Version: 1.0*

