# Elastic Janitor

A comprehensive Elasticsearch cluster management tool for managing indices, data streams, templates, policies, snapshots, and cluster health.

**Now with CLI support!** Use Elastic Janitor from the command line or interactive menu mode.


## Features

### Index Management
- **Basic Operations**: List largest indices, view settings, detect duplicates
- **Health Monitoring**: Health dashboard, shard analysis
- **Advanced Operations**: Alias management, rollover status, tier migration, merge optimization

### Data Streams
- **Cleanup**: Clean data streams and standalone indices
- **Preview**: Preview data streams before operations
- **Statistics**: View statistics and lifecycle information
- **Advanced**: Reindexing, cloning, write index rotation

### Templates & Policies
- **Index Templates**: List and manage index and component templates
- **ILM Policies**: Manage Index Lifecycle Management policies
- **Ingest Pipelines**: List and manage ingest pipelines
- **Advanced**: Template conflict detection, policy simulation, bulk assignment

### Snapshots
- **Repository Management**: List and verify snapshot repositories
- **Snapshot Operations**: List, delete, and analyze snapshots
- **SLM**: Manage Snapshot Lifecycle Management policies
- **Advanced**: Automated cleanup, cross-repository copy, restore wizard

### Cluster Health
- **Overview**: Cluster health and statistics
- **Node Information**: Detailed node information
- **Dry-Run Mode**: Toggle dry-run mode for safe testing

### Storage Optimization
- **Forecasting**: Storage forecast and tier distribution
- **Analysis**: Compression analysis, empty index cleanup
- **Detection**: Sparse index detector
- **Cost Estimation**: Estimate storage costs

### Performance Monitoring
- **Metrics**: Monitor cluster performance metrics
- **Analysis**: Identify performance bottlenecks

### Bulk Automation
- **Batch Operations**: Execute operations in bulk
- **Scheduled Cleanup**: Automate cleanup tasks
- **Configuration Management**: Save and load configurations

## Installation

### Prerequisites
- Python 3.8 or higher
- Access to an Elasticsearch cluster

### Install from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/elastic-janitor.git
cd elastic-janitor

# Install in development mode (recommended)
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

### Configuration

Edit `janitor/config.py` to configure your Elasticsearch connection:

```python
ELASTIC_URL = "https://your-elasticsearch-cluster:9243"
ELASTIC_API_KEY = "your-api-key-here"
```

**Important**: For production use, consider using environment variables or a separate configuration file for sensitive credentials.

## Usage

Elastic Janitor supports two modes: **CLI mode** and **Interactive Menu mode**.

### CLI Mode (New!)

Use Elastic Janitor from the command line with specific commands:

```bash
# Check cluster health
elastic-janitor cluster health

# List largest indices
elastic-janitor index largest --top 25

# Clean old data streams (dry-run first!)
elastic-janitor datastream clean --retention 90d --dry-run

# Use short alias
ej cluster health
```

**See [CLI_USAGE.md](CLI_USAGE.md) for complete CLI documentation.**

### Interactive Menu Mode

Launch the interactive menu (no arguments):

```bash
# Using installed command
elastic-janitor

# Or as Python module
python -m janitor

# Or using launcher script
python run.py
```

### Quick Examples

```bash
# CLI: Check cluster health with JSON output
elastic-janitor cluster health --output json

# CLI: Find top 50 largest indices
elastic-janitor index largest --top 50 --pattern "logs-*"

# CLI: Enable global dry-run mode
elastic-janitor dry-run enable

# Interactive: Launch menu
elastic-janitor
```

```bash
chmod +x run.py
./run.py
```

## Project Structure

```
elastic-janitor/
├── __init__.py              - Package initialization
├── __main__.py              - Entry point for module execution
├── config.py                - Configuration and constants
├── run.py                   - Launcher script
├── requirements.txt         - Python dependencies
├── README.md                - This file
│
├── utils/                   - Utility functions
│   ├── __init__.py
│   ├── helpers.py           - User input and confirmations
│   ├── formatters.py        - Date and size formatting
│   ├── ui.py                - UI helpers (breadcrumb)
│   └── history_logger.py    - Operation history logging
│
├── core/                    - Core functionality
│   ├── __init__.py
│   └── connection.py        - Elasticsearch connection
│
├── operations/              - All operations organized by category
│   ├── __init__.py
│   ├── index_basic.py       - Basic index operations
│   ├── index_health.py      - Health monitoring
│   ├── index_advanced.py    - Advanced index operations
│   ├── data_streams_*.py    - Data stream operations
│   ├── templates_*.py       - Template operations
│   ├── snapshots.py         - Snapshot management
│   ├── cluster.py           - Cluster health & diagnostics
│   ├── storage_optimization.py - Storage optimization
│   ├── performance_monitoring.py - Performance monitoring
│   ├── bulk_automation.py   - Bulk operations
│   └── advanced_cleanup.py  - Advanced cleanup features
│
└── menus/                   - Menu system
    ├── __init__.py
    ├── main_menu.py         - Main menu
    └── submenus.py          - All submenus
```

## Configuration Options

### Elasticsearch Settings
- `ELASTIC_URL`: Your Elasticsearch cluster URL
- `ELASTIC_API_KEY`: API key for authentication

### Application Settings
- `PROTECT_SYSTEM`: Protect system indices from deletion (default: `True`)
- `DEFAULT_RETENTION_DAYS`: Default retention period for cleanup operations (default: `90`)
- `MAX_DELETE_LIMIT`: Maximum number of items to delete in one operation (default: `5000`)
- `DRY_RUN_MODE`: Global dry-run mode flag (default: `False`)

## Safety Features

### Dry-Run Mode
Enable dry-run mode to preview operations without making actual changes:
- Toggle from the Cluster Health menu
- All destructive operations will show what would be deleted without actually deleting

### System Index Protection
By default, system indices (starting with `.`) are protected from deletion. This can be configured via `PROTECT_SYSTEM` in `config.py`.

### Confirmation Prompts
All destructive operations require explicit confirmation before execution.

### Operation Limits
Maximum deletion limits prevent accidental bulk deletions. Configure via `MAX_DELETE_LIMIT` in `config.py`.

## Development

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest
```

### Code Style

This project follows PEP 8 style guidelines. Use `black` for code formatting:

```bash
black .
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

[Add your license information here]

## Support

For issues, questions, or contributions, please [open an issue](https://github.com/yourusername/elastic-janitor/issues) on GitHub.

## Changelog

See [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) for details on the latest refactoring and improvements.

## Version

Current version: 2.0.0

## Author

Elastic Janitor Team

## Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- Uses [Questionary](https://github.com/tmbo/questionary) for interactive prompts
- Powered by the official [Elasticsearch Python client](https://github.com/elastic/elasticsearch-py)
