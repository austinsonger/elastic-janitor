# Elastic Janitor CLI - Quick Reference Guide

**Version:** 1.0  
**Last Updated:** 2026-02-13

---

## Quick Start

```bash
# Install and configure
pip install elastic-janitor
elastic-janitor config init

# Set credentials
export ELASTIC_URL="https://your-cluster:9243"
export ELASTIC_API_KEY="your-api-key"

# Test connection
elastic-janitor cluster health
```

---

## Most Common Commands

### Index Management
```bash
# View largest indices
ej index largest --top 25

# Check index health
ej index health --status yellow,red

# View index settings
ej index settings --index "logs-2024.01.01"

# Optimize index
ej index optimize --index "logs-2024.01.01" --max-segments 1
```

### Data Stream Management
```bash
# Clean old data streams (dry-run first!)
ej datastream clean --retention 90d --dry-run
ej datastream clean --retention 90d

# Preview data streams
ej ds preview --pattern "logs-*"

# View data stream stats
ej ds stats --pattern "logs-*"
```

### Template & Policy Management
```bash
# List templates
ej template index list
ej template component list
ej pipeline list

# View template details
ej template index view --name "logs-template"

# Edit with version control
ej pipeline edit --name "logs-pipeline"

# Rollback
ej pipeline rollback --name "logs-pipeline" --version 5
```

### Snapshot Management
```bash
# List snapshots
ej snapshot list --repo "backup-repo"

# Delete old snapshots
ej snap delete --repo "backup-repo" --retention 90d --keep-last 10

# Create snapshot
ej snapshot create --repo "backup-repo" --name "backup-$(date +%Y%m%d)"

# Restore snapshot
ej snap restore --repo "backup-repo" --snapshot "backup-20240115"
```

### Cluster Health
```bash
# Cluster overview
ej cluster health

# Node information
ej cluster nodes

# Cluster statistics
ej cluster stats
```

### Storage Optimization
```bash
# Storage forecast
ej storage forecast --days 30

# Tier distribution
ej storage tiers --show-costs

# Find empty indices
ej storage cleanup-empty --dry-run

# Cost estimate
ej storage cost --show-optimizations
```

### Performance Monitoring
```bash
# Slow queries
ej perf slow-queries --threshold 1s --time-range 1h

# Indexing performance
ej perf indexing --index "logs-*"

# Node resource usage
ej perf nodes --refresh 5

# Hot spots
ej perf hotspots
```

### Data Quality
```bash
# Missing fields
ej quality missing-fields --index "logs-*" --fields "user_id,timestamp"

# Type inconsistencies
ej quality type-inconsistency --pattern "logs-*"

# Null value stats
ej dq null-stats --index "logs-*"

# Cardinality analysis
ej dq cardinality --index "logs-*"
```

### Cleanup Operations
```bash
# Find duplicates
ej cleanup duplicates --index "logs-*" --field "message_id"

# Delete duplicates
ej cleanup duplicates --index "logs-*" --field "message_id" --action delete-oldest --dry-run

# Wildcard deletion
ej cleanup wildcard-delete --pattern "test-*" --dry-run

# Detect time-series gaps
ej cleanup gaps --index "logs-*" --interval 1d
```

### AWS Ingestion
```bash
# Health check
ej aws health-check --index "aws-logs-*"

# Detect issues
ej aws detect-issues --severity critical

# Troubleshoot pipeline
ej aws troubleshoot-pipeline --pipeline "aws-logs-pipeline"
```

### Dashboard
```bash
# Launch dashboard
ej dashboard --refresh 5

# Export dashboard data
ej dashboard export --output report.html --format html
```

---

## Global Options

All commands support:
```bash
--dry-run, -d       # Preview without executing
--verbose, -v       # Verbose output
--output, -o        # Output format: json, table, yaml, csv
--help, -h          # Show help
--config, -c        # Config file path
--quiet, -q         # Suppress output
```

---

## Command Aliases

```bash
ej = elastic-janitor
ds = datastream
tpl = template
snap = snapshot
perf = performance
dq = quality
```

---

## Dry-Run Mode

```bash
# Enable global dry-run
ej dry-run enable

# Check status
ej dry-run status

# Disable
ej dry-run disable

# Or use per-command
ej datastream clean --retention 90d --dry-run
```

---

## Output Formats

```bash
# Table (default, human-readable)
ej index largest --output table

# JSON (for scripting)
ej index largest --output json | jq '.indices[0].name'

# CSV (for spreadsheets)
ej index largest --output csv > indices.csv

# YAML (for configs)
ej template index view --name "logs-template" --output yaml
```

---

## Common Workflows

### Daily Cleanup
```bash
#!/bin/bash
ej datastream clean --retention 90d
ej snapshot delete --repo "backup-repo" --retention 30d --keep-last 10
ej storage cleanup-empty
```

### Health Check
```bash
#!/bin/bash
ej cluster health
ej index health --status yellow,red
ej perf hotspots
```

### Cost Optimization
```bash
#!/bin/bash
ej storage cost --show-optimizations
ej index migrate --index "logs-*" --to-tier cold --age 90d
ej storage compression --pattern "logs-*"
```

---

## Troubleshooting

```bash
# Connection issues
ej cluster health --verbose

# Permission issues
ej cluster health --output json

# Timeout issues
ej cluster health --timeout 60s

# View operation history
ej bulk history --limit 50

# Check dry-run status
ej dry-run status
```

---

## Tips & Tricks

1. **Always test with --dry-run first**
   ```bash
   ej datastream clean --retention 30d --dry-run
   ```

2. **Use patterns for bulk operations**
   ```bash
   ej index health --pattern "logs-2024.01.*"
   ```

3. **Combine with jq for JSON processing**
   ```bash
   ej cluster health --output json | jq '.status'
   ```

4. **Export configurations regularly**
   ```bash
   ej bulk config export --output-dir ./backup-$(date +%Y%m%d)
   ```

5. **Monitor with auto-refresh**
   ```bash
   ej dashboard --refresh 5
   ```

6. **Use scheduled jobs for automation**
   ```bash
   ej bulk schedule create --name "daily-cleanup" --schedule "0 2 * * *"
   ```

---

## Exit Codes

- `0` - Success
- `1` - General error
- `2` - Invalid arguments
- `3` - Connection error
- `4` - Permission error
- `5` - Resource not found
- `6` - Validation error
- `7` - Operation failed
- `8` - Timeout

---

## Getting Help

```bash
# General help
ej --help

# Command help
ej cluster --help
ej cluster health --help

# Version
ej --version

# Verbose mode for debugging
ej cluster health --verbose
```

---

**For full documentation, see CLI_COMMAND_LIBRARY.md**

