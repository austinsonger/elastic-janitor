"""
Auto-remediation CLI commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.auto_remediation import (
    option_auto_remediation_scan,
    option_auto_remediation_execute,
    option_auto_remediation_configure,
    option_auto_remediation_history,
)


@click.group()
def remediation():
    """Auto-remediation engine commands."""
    pass


@remediation.command()
@common_options
@handle_errors
@pass_es_client
def scan(es, output, verbose, quiet):
    """
    Scan cluster for issues and display remediation recommendations.

    Examples:

        # Scan for cluster issues
        elastic-janitor remediation scan
    """
    if not quiet:
        info("Scanning cluster for remediation targets...")

    option_auto_remediation_scan(es)


@remediation.command()
@common_options
@handle_errors
@pass_es_client
def execute(es, output, verbose, quiet):
    """
    Scan and execute auto-remediation actions.

    Detects issues like excessive segments, unassigned shards,
    disk watermarks, and node failures, then applies fixes.

    Examples:

        # Execute remediation (safe mode by default)
        elastic-janitor remediation execute
    """
    if not quiet:
        info("Running auto-remediation...")

    option_auto_remediation_execute(es)


@remediation.command()
@common_options
@handle_errors
@pass_es_client
def configure(es, output, verbose, quiet):
    """
    View and configure remediation thresholds.

    Examples:

        # View current thresholds
        elastic-janitor remediation configure
    """
    option_auto_remediation_configure(es)


@remediation.command()
@common_options
@handle_errors
@pass_es_client
def history(es, output, verbose, quiet):
    """
    View recent auto-remediation actions.

    Examples:

        # View remediation history
        elastic-janitor remediation history
    """
    option_auto_remediation_history(es)
