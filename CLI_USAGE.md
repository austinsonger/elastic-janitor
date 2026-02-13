# Elastic Janitor CLI - Usage Guide

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/elastic-janitor.git
cd elastic-janitor

# Install in development mode
pip install -e .

# Or install from requirements
pip install -r requirements.txt
```

### Verify Installation

```bash
# Check version
elastic-janitor --version

# Show help
elastic-janitor --help

# Use short alias
ej --help
```

## Configuration

Elastic Janitor uses configuration from `janitor/config.py`. You can set:

- `ELASTIC_URL` - Your Elasticsearch cluster URL
- `ELASTIC_API_KEY` - Your API key for authentication
- `PROTECT_SYSTEM` - Protect system indices (default: True)
- `DEFAULT_RETENTION_DAYS` - Default retention period (default: 90)
- `DRY_RUN_MODE` - Global dry-run mode (default: False)

### Environment Variables

You can also use environment variables:

```bash
export ELASTIC_URL="https://your-cluster:9243"
export ELASTIC_API_KEY="your-api-key"
```

## Usage Modes

Elastic Janitor supports two modes:

### 1. CLI Mode (with arguments)

```bash
# Run specific commands
elastic-janitor cluster health
elastic-janitor index largest --top 25
elastic-janitor datastream clean --retention 90d --dry-run
```

### 2. Interactive Menu Mode (no arguments)

```bash
# Launch interactive menu
elastic-janitor

# Or
python -m janitor
```

## Available Commands

### Cluster Commands

```bash
# Check cluster health
elastic-janitor cluster health

# Show cluster health in JSON
elastic-janitor cluster health --output json

# List all nodes
elastic-janitor cluster nodes

# Show cluster statistics
elastic-janitor cluster stats --verbose
```

### Index Commands

```bash
# List top 25 largest indices
elastic-janitor index largest

# List top 50 largest indices
elastic-janitor index largest --top 50

# Filter by pattern
elastic-janitor index largest --pattern "logs-*"

# Check index health
elastic-janitor index health

# Show only yellow and red indices
elastic-janitor index health --status yellow --status red

# Check specific pattern
elastic-janitor index health --pattern "logs-*"
```

### Data Stream Commands

```bash
# Preview cleanup (DRY-RUN - always do this first!)
elastic-janitor datastream clean --retention 90d --dry-run

# Clean indices older than 90 days
elastic-janitor datastream clean --retention 90d

# Clean with specific pattern
elastic-janitor datastream clean --retention 6M --pattern "logs-*"

# JSON output
elastic-janitor datastream clean --retention 90d --output json --dry-run
```

### Dry-Run Mode Commands

```bash
# Enable global dry-run mode
elastic-janitor dry-run enable

# Check dry-run status
elastic-janitor dry-run status

# Disable dry-run mode
elastic-janitor dry-run disable
```

## Global Options

All commands support these global options:

```bash
--verbose, -v       # Enable verbose output
--quiet, -q         # Suppress non-essential output
--output, -o        # Output format: json, table, yaml, csv
--help, -h          # Show help message
```

## Output Formats

### Table (default)

```bash
elastic-janitor index largest
```

Human-readable table format with colors and formatting.

### JSON

```bash
elastic-janitor index largest --output json
```

Machine-readable JSON format, perfect for scripting.

### YAML

```bash
elastic-janitor cluster health --output yaml
```

YAML format, useful for configuration files.

### CSV

```bash
elastic-janitor index largest --output csv > indices.csv
```

CSV format, perfect for spreadsheets.

## Examples

### Daily Cleanup Script

```bash
#!/bin/bash
# daily-cleanup.sh

# Enable dry-run for safety
ej dry-run enable

# Clean old data streams
ej datastream clean --retention 90d

# Check cluster health
ej cluster health

# Disable dry-run
ej dry-run disable
```

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

# Get cluster status
STATUS=$(ej cluster health --output json | jq -r '.status')

if [ "$STATUS" != "GREEN" ]; then
    echo "Cluster health is $STATUS"
    ej cluster health --verbose
    exit 1
fi

echo "Cluster is healthy"
```

### Find Large Indices

```bash
# Find top 50 largest indices and save to CSV
ej index largest --top 50 --output csv > large-indices.csv

# Find large log indices
ej index largest --pattern "logs-*" --top 100
```

## Tips & Best Practices

1. **Always use --dry-run first**
   ```bash
   ej datastream clean --retention 30d --dry-run
   ```

2. **Use global dry-run mode for safety**
   ```bash
   ej dry-run enable
   # Run your commands
   ej dry-run disable
   ```

3. **Combine with jq for JSON processing**
   ```bash
   ej cluster health --output json | jq '.status'
   ```

4. **Use patterns for filtering**
   ```bash
   ej index health --pattern "logs-2024.*"
   ```

5. **Save output to files**
   ```bash
   ej index largest --output csv > indices.csv
   ej cluster health --output json > health.json
   ```

## Troubleshooting

### Connection Issues

```bash
# Check with verbose output
ej cluster health --verbose
```

### Permission Issues

Make sure your API key has the required permissions for the operations you're performing.

### Timeout Issues

For large clusters, some operations may take longer. The tool has built-in timeouts that should handle most cases.

## Next Steps

- See [CLI_COMMAND_LIBRARY.md](CLI_COMMAND_LIBRARY.md) for complete command reference
- See [CLI_QUICK_REFERENCE.md](CLI_QUICK_REFERENCE.md) for quick reference
- See [README.md](README.md) for general information about Elastic Janitor

