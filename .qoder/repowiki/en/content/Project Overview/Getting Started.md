# Getting Started

<cite>
**Referenced Files in This Document**
- [README.md](file://README.md)
- [QUICK_START.md](file://docs/QUICK_START.md)
- [CLI_USAGE.md](file://docs/CLI_USAGE.md)
- [CLI_COMMAND_LIBRARY.md](file://docs/CLI_COMMAND_LIBRARY.md)
- [pyproject.toml](file://pyproject.toml)
- [requirements.txt](file://requirements.txt)
- [janitor/__main__.py](file://janitor/__main__.py)
- [janitor/cli/main.py](file://janitor/cli/main.py)
- [janitor/core/connection.py](file://janitor/core/connection.py)
- [janitor/config.py](file://janitor/config.py)
- [run.py](file://run.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Installation Methods](#installation-methods)
4. [Configuration](#configuration)
5. [Quick Start Examples](#quick-start-examples)
6. [Modes of Operation](#modes-of-operation)
7. [Essential Configuration Options](#essential-configuration-options)
8. [Security Considerations](#security-considerations)
9. [Verification and Troubleshooting](#verification-and-troubleshooting)
10. [Next Steps](#next-steps)

## Introduction
Elastic Janitor is a comprehensive tool for managing Elasticsearch clusters from the command line or an interactive menu. It helps you monitor cluster health, manage indices and data streams, templates and policies, snapshots, and more. This guide focuses on rapid onboarding: prerequisites, installation, configuration, and practical first steps to verify your setup.

## Prerequisites
- Python 3.8 or higher
- Access to an Elasticsearch cluster (version 8.0.0 or higher recommended)
- Network access to the cluster from your machine
- An API key with appropriate permissions for the operations you intend to perform

**Section sources**
- [README.md](file://README.md#L54-L57)
- [pyproject.toml](file://pyproject.toml#L10)
- [CLI_COMMAND_LIBRARY.md](file://CLI_COMMAND_LIBRARY.md#L209-L210)

## Installation Methods
Choose one of the following methods depending on your needs.

- Install from source (development mode)
  - Clone the repository and install in editable mode for easy iteration
  - Use the development mode installer to register the CLI entry points

- Install dependencies only
  - Install required Python packages for a minimal setup

- Pip installation (if available)
  - Install directly from the package index using pip (if published)

Notes:
- Development mode is recommended during initial setup so you can quickly test changes
- The project’s packaging metadata defines the CLI entry points for both long and short aliases

**Section sources**
- [README.md](file://README.md#L58-L70)
- [pyproject.toml](file://pyproject.toml#L56-L58)

## Configuration
Configure your Elasticsearch connection and application defaults.

- Set credentials in the configuration file
  - Update the URL and API key in the configuration module
  - Keep secrets out of version control

- Environment variables (recommended for production)
  - Override configuration values using environment variables
  - Supports flexible deployment across environments

- Application settings
  - Adjust protection flags, retention defaults, and operational limits
  - Dry-run mode can be toggled globally

- Verify configuration
  - After updating, run a simple health check to confirm connectivity

**Section sources**
- [README.md](file://README.md#L72-L82)
- [janitor/config.py](file://janitor/config.py#L11-L23)
- [CLI_COMMAND_LIBRARY.md](file://CLI_COMMAND_LIBRARY.md#L91-L129)

## Quick Start Examples
Perform essential checks and operations right away.

- Check cluster health
  - Use the CLI to retrieve cluster health and status
  - Try JSON output for scripting-friendly results

- List largest indices
  - Fetch top N largest indices by size
  - Filter by pattern for targeted reporting

- Enable dry-run mode
  - Toggle global dry-run mode to preview changes safely
  - Useful before running destructive operations

- Interactive menu
  - Launch the interactive menu for guided navigation
  - Explore categories and subcommands visually

**Section sources**
- [README.md](file://README.md#L87-L105)
- [README.md](file://README.md#L107-L121)
- [CLI_USAGE.md](file://CLI_USAGE.md#L78-L90)
- [CLI_USAGE.md](file://CLI_USAGE.md#L94-L112)
- [CLI_USAGE.md](file://CLI_USAGE.md#L132-L141)

## Modes of Operation
Elastic Janitor supports two primary modes.

- CLI mode
  - Run specific commands directly from the terminal
  - Ideal for automation, scripts, and repeatable tasks

- Interactive menu mode
  - Launch without arguments to open the interactive menu
  - Great for exploration and ad-hoc operations

- Entry points
  - The main module detects whether arguments are present and routes accordingly
  - The CLI group registers all command categories

**Section sources**
- [README.md](file://README.md#L83-L121)
- [janitor/__main__.py](file://janitor/__main__.py#L16-L32)
- [janitor/cli/main.py](file://janitor/cli/main.py#L8-L36)

## Essential Configuration Options
Key settings you will use frequently.

- Elasticsearch settings
  - URL: Your Elasticsearch endpoint
  - API key: Authentication credential

- Application settings
  - Protect system indices: Prevents deletion of system indices
  - Default retention days: Default period for cleanup operations
  - Max delete limit: Cap on batch deletion size
  - Dry-run mode: Global toggle for preview-only operations

- Output formats
  - Table, JSON, YAML, CSV: Choose the format that fits your workflow

**Section sources**
- [README.md](file://README.md#L185-L196)
- [CLI_COMMAND_LIBRARY.md](file://CLI_COMMAND_LIBRARY.md#L40-L55)

## Security Considerations
Protect your environment and data.

- Use environment variables for secrets
  - Avoid committing credentials to version control
  - Set variables in your shell profile or CI environment

- Limit API key permissions
  - Grant least privilege required for intended operations
  - Regularly review and rotate keys

- System index protection
  - Enabled by default to avoid accidental deletion of internal indices
  - Can be adjusted via configuration

- Dry-run mode
  - Always test destructive actions with dry-run enabled first
  - Review the planned changes before confirming

**Section sources**
- [README.md](file://README.md#L81-L82)
- [README.md](file://README.md#L197-L212)
- [QUICK_START.md](file://docs/QUICK_START.md#L32-L44)
- [QUICK_START.md](file://docs/QUICK_START.md#L98-L116)

## Verification and Troubleshooting
Confirm your installation and resolve common issues.

- Verify installation
  - Check the CLI version and help output
  - Ensure both long and short aliases are recognized

- Test connectivity
  - Run a cluster health check
  - Use verbose output to diagnose connection problems

- Common issues
  - Missing dependencies: Install requirements
  - Import errors: Run from the repository root
  - Connection failures: Validate URL and API key, check network access
  - Permission errors: Confirm API key permissions and avoid protected indices

- Operational tips
  - Combine JSON output with processing tools for automation
  - Use patterns to filter results and reduce noise
  - Save outputs to files for auditing and reporting

**Section sources**
- [CLI_USAGE.md](file://CLI_USAGE.md#L19-L30)
- [CLI_USAGE.md](file://CLI_USAGE.md#L267-L283)
- [QUICK_START.md](file://docs/QUICK_START.md#L117-L151)

## Next Steps
- Set up a remote repository and push your configuration
- Create a dedicated environment file for secrets and add it to version control exclusion lists
- Install in development mode for iterative testing
- Integrate CLI commands into scheduled jobs for routine maintenance
- Explore advanced commands for templates, policies, snapshots, and performance tuning

**Section sources**
- [QUICK_START.md](file://docs/QUICK_START.md#L176-L199)
- [CLI_COMMAND_LIBRARY.md](file://CLI_COMMAND_LIBRARY.md#L284-L289)