# Installation and Setup

<cite>
**Referenced Files in This Document**
- [README.md](file://README.md)
- [pyproject.toml](file://pyproject.toml)
- [requirements.txt](file://requirements.txt)
- [setup.py](file://setup.py)
- [janitor/config.py](file://janitor/config.py)
- [janitor/core/connection.py](file://janitor/core/connection.py)
- [janitor/__main__.py](file://janitor/__main__.py)
- [janitor/cli/main.py](file://janitor/cli/main.py)
- [run.py](file://run.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Installation Methods](#installation-methods)
4. [Configuration Setup](#configuration-setup)
5. [Security Considerations](#security-considerations)
6. [Verification Steps](#verification-steps)
7. [Deployment Scenarios and Platform Notes](#deployment-scenarios-and-platform-notes)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Upgrade Procedures and Version Compatibility](#upgrade-procedures-and-version-compatibility)
10. [Conclusion](#conclusion)

## Introduction
This guide helps you install and set up Elastic Janitor so you can manage and monitor your Elasticsearch clusters from the command line or an interactive menu. It covers installation via pip, installing from source, development setup, prerequisites, configuration, security, verification, troubleshooting, and upgrades.

## Prerequisites
- Python 3.8 or higher
- Access to an Elasticsearch cluster (including URL and authentication)

These prerequisites are required for all installation methods.

**Section sources**
- [README.md](file://README.md#L54-L57)
- [pyproject.toml](file://pyproject.toml#L10)

## Installation Methods

### Install from Source (Recommended for Development)
Follow these steps to install from source in development mode:

1. Clone the repository and navigate into the project directory.
2. Install in editable (development) mode using pip.
3. Alternatively, install only the runtime dependencies.

Notes:
- Editable installs let you modify the code and run the tool immediately.
- Installing only dependencies is useful if you prefer a minimal environment.

**Section sources**
- [README.md](file://README.md#L58-L70)

### Install from PyPI (pip)
To install the package from PyPI using pip:
- Use the package name as published in the project metadata.
- After installation, the CLI entry points are registered and available globally.

Tip:
- If you encounter permission errors, consider using a virtual environment or user installation flags supported by your pip version.

**Section sources**
- [pyproject.toml](file://pyproject.toml#L6)
- [pyproject.toml](file://pyproject.toml#L56-L58)

### Development Setup
If you plan to contribute or run tests:
- Install development dependencies.
- Run tests with pytest.

Optional:
- Use code formatting and linting tools as configured in the project.

**Section sources**
- [README.md](file://README.md#L213-L231)
- [pyproject.toml](file://pyproject.toml#L41-L48)
- [pyproject.toml](file://pyproject.toml#L84-L89)

## Configuration Setup

### Configure Elasticsearch Connection
Before running Elastic Janitor, set your Elasticsearch connection details. The primary configuration file is:
- [janitor/config.py](file://janitor/config.py)

Key settings:
- ELASTIC_URL: Your Elasticsearch cluster URL
- ELASTIC_API_KEY: API key for authentication

Important:
- For production environments, avoid committing secrets to the repository. Consider using environment variables or a separate configuration file.

**Section sources**
- [README.md](file://README.md#L72-L82)
- [janitor/config.py](file://janitor/config.py#L11-L12)

### Environment Variables
While the default configuration reads from the config file, the connection module validates that essential values are present. For production deployments, consider externalizing secrets via environment variables and loading them into the configuration at runtime.

How the connection module uses configuration:
- The connection module imports ELASTIC_URL and ELASTIC_API_KEY from the config module and performs validation and connection attempts.

**Section sources**
- [janitor/core/connection.py](file://janitor/core/connection.py#L11-L17)
- [janitor/config.py](file://janitor/config.py#L11-L12)

### Additional Application Settings
Beyond Elasticsearch connection, the configuration file defines application behavior:
- PROTECT_SYSTEM: Protect system indices from deletion
- DEFAULT_RETENTION_DAYS: Default retention period for cleanup operations
- MAX_DELETE_LIMIT: Maximum number of items to delete in one operation
- DRY_RUN_MODE: Global dry-run mode flag
- Query timeouts: DEFAULT_QUERY_TIMEOUT, SLOW_QUERY_TIMEOUT, REQUEST_TIMEOUT, REINDEX_TIMEOUT
- Version control settings: ENABLE_DEPENDENCY_TRACKING, MAX_DEPENDENCY_DEPTH, MAX_VERSIONS_PER_RESOURCE
- UI configuration: Rich console and Questionary custom style

These settings influence safety, performance, and user interface behavior.

**Section sources**
- [README.md](file://README.md#L185-L196)
- [janitor/config.py](file://janitor/config.py#L18-L56)

## Security Considerations
- Store secrets securely: Avoid hardcoding credentials in the repository. Prefer environment variables or a separate configuration file.
- Limit API key permissions to the minimum required for operations.
- Review and adjust protection settings (e.g., system index protection) according to your environment’s policies.

**Section sources**
- [README.md](file://README.md#L81)
- [janitor/config.py](file://janitor/config.py#L18)

## Verification Steps
After installation and configuration, verify your setup:

1. Launch the interactive menu:
   - Use the installed command without arguments.
   - Or run as a Python module.
   - Or use the launcher script.

2. Run a quick CLI command:
   - Check cluster health.
   - List largest indices.
   - Enable dry-run mode to preview operations safely.

3. Confirm connection:
   - The connection module validates that required configuration values are present and attempts to connect to the cluster.

Notes:
- If the connection fails, review your Elasticsearch URL and API key.
- Ensure network access to the cluster and appropriate firewall rules.

**Section sources**
- [README.md](file://README.md#L83-L120)
- [janitor/__main__.py](file://janitor/__main__.py#L16-L32)
- [janitor/cli/main.py](file://janitor/cli/main.py#L8-L36)
- [janitor/core/connection.py](file://janitor/core/connection.py#L11-L32)

## Deployment Scenarios and Platform Notes
- Linux/macOS/Windows: The tool runs on all major platforms as long as Python 3.8+ is available.
- Virtual environments: Recommended for isolation and avoiding permission issues.
- Containerized environments: Ensure the container has network access to the Elasticsearch cluster and that secrets are mounted or injected appropriately.
- CI/CD pipelines: Use the CLI mode for automation and dry-run mode for safe previews.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common installation and setup issues:

- Python version mismatch:
  - Ensure Python 3.8 or newer is installed and selected by your environment.

- Missing dependencies:
  - Install runtime dependencies from the project’s dependency list.

- Installation failures:
  - Try installing in editable mode from source for development.
  - If installing from PyPI fails, verify your network and pip configuration.

- Connection errors:
  - Verify ELASTIC_URL and ELASTIC_API_KEY are set correctly.
  - Confirm network access to the cluster and that the cluster is reachable.
  - Check Elasticsearch client version compatibility.

- CLI not found:
  - Ensure the package is installed and the scripts are registered.
  - Use the module execution path if the command is unavailable.

- Interactive menu not launching:
  - Confirm the main entry point is accessible.
  - Try running the launcher script or module execution.

**Section sources**
- [pyproject.toml](file://pyproject.toml#L31-L39)
- [requirements.txt](file://requirements.txt#L1-L7)
- [janitor/core/connection.py](file://janitor/core/connection.py#L11-L32)
- [janitor/__main__.py](file://janitor/__main__.py#L16-L32)
- [run.py](file://run.py#L1-L10)

## Upgrade Procedures and Version Compatibility
- Current version:
  - The project version is defined in the project metadata.

- Upgrading from source:
  - Pull the latest changes and reinstall in editable mode if you are developing locally.
  - For production, reinstall the package from PyPI.

- Version compatibility:
  - Requires Python 3.8+.
  - The Elasticsearch client dependency specifies a minimum version.
  - The project declares classifiers for supported Python versions.

- Post-upgrade verification:
  - Re-run verification steps to ensure everything works as expected.

**Section sources**
- [pyproject.toml](file://pyproject.toml#L7)
- [pyproject.toml](file://pyproject.toml#L10)
- [pyproject.toml](file://pyproject.toml#L34)
- [pyproject.toml](file://pyproject.toml#L16-L29)
- [README.md](file://README.md#L256-L258)

## Conclusion
You now have the essentials to install, configure, and verify Elastic Janitor. Use the interactive menu or CLI to manage your Elasticsearch clusters, apply safety features, and tailor configuration to your environment. For development, follow the development setup and testing guidance. If issues arise, consult the troubleshooting section and verify your configuration and connectivity.