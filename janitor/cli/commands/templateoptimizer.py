"""
Index template optimizer CLI commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.template_optimizer import (
    option_template_mapping_analyzer,
    option_template_settings_analyzer,
    option_template_live_index_analysis,
    option_template_optimization_report,
)


@click.group(name='template-optimizer')
def template_optimizer():
    """Index template optimization commands."""
    pass


@template_optimizer.command()
@common_options
@handle_errors
@pass_es_client
def mappings(es, output, verbose, quiet):
    """
    Analyze template mappings and suggest field type optimizations.

    Detects mistyped fields like identifiers stored as text,
    dates stored as keywords, and missing keyword sub-fields.

    Examples:

        # Analyze template mappings
        elastic-janitor template-optimizer mappings
    """
    if not quiet:
        info("Analyzing template mappings...")

    option_template_mapping_analyzer(es)


@template_optimizer.command()
@common_options
@handle_errors
@pass_es_client
def settings(es, output, verbose, quiet):
    """
    Analyze template settings and dynamic mapping configuration.

    Checks shard counts, replica counts, refresh intervals,
    and dynamic mapping policies.

    Examples:

        # Analyze template settings
        elastic-janitor template-optimizer settings
    """
    if not quiet:
        info("Analyzing template settings...")

    option_template_settings_analyzer(es)


@template_optimizer.command(name='live-analysis')
@common_options
@handle_errors
@pass_es_client
def live_analysis(es, output, verbose, quiet):
    """
    Analyze live index mappings for optimization opportunities.

    Examines actual index mappings (not just templates) and
    suggests field type improvements.

    Examples:

        # Analyze live indices
        elastic-janitor template-optimizer live-analysis
    """
    if not quiet:
        info("Analyzing live index mappings...")

    option_template_live_index_analysis(es)


@template_optimizer.command()
@common_options
@handle_errors
@pass_es_client
def report(es, output, verbose, quiet):
    """
    Generate a comprehensive optimization report across all templates.

    Examples:

        # Generate optimization report
        elastic-janitor template-optimizer report
    """
    if not quiet:
        info("Generating optimization report...")

    option_template_optimization_report(es)
