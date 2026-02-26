"""
Query performance analyzer CLI commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.query_analyzer import (
    option_query_performance_overview,
    option_query_slow_index_analysis,
    option_query_anti_pattern_detector,
    option_query_optimization_suggestions,
    option_query_known_patterns,
)


@click.group(name='query-analyzer')
def query_analyzer():
    """Query performance analysis and optimization commands."""
    pass


@query_analyzer.command()
@common_options
@handle_errors
@pass_es_client
def overview(es, output, verbose, quiet):
    """
    Display query performance overview across all nodes.

    Examples:

        # View query performance overview
        elastic-janitor query-analyzer overview
    """
    if not quiet:
        info("Analyzing query performance...")

    option_query_performance_overview(es)


@query_analyzer.command(name='slow-indices')
@common_options
@handle_errors
@pass_es_client
def slow_indices(es, output, verbose, quiet):
    """
    Identify the slowest indices by search performance.

    Examples:

        # Find slowest indices
        elastic-janitor query-analyzer slow-indices
    """
    if not quiet:
        info("Identifying slow indices...")

    option_query_slow_index_analysis(es)


@query_analyzer.command(name='anti-patterns')
@common_options
@handle_errors
@pass_es_client
def anti_patterns(es, output, verbose, quiet):
    """
    Detect common query anti-patterns like N+1 queries.

    Examples:

        # Scan for anti-patterns
        elastic-janitor query-analyzer anti-patterns
    """
    if not quiet:
        info("Scanning for query anti-patterns...")

    option_query_anti_pattern_detector(es)


@query_analyzer.command()
@common_options
@handle_errors
@pass_es_client
def optimize(es, output, verbose, quiet):
    """
    Generate targeted optimization suggestions.

    Analyzes cluster search metrics and provides actionable
    recommendations with expected performance improvements.

    Examples:

        # Get optimization suggestions
        elastic-janitor query-analyzer optimize
    """
    if not quiet:
        info("Generating optimization suggestions...")

    option_query_optimization_suggestions(es)


@query_analyzer.command(name='patterns')
@common_options
@handle_errors
@pass_es_client
def patterns(es, output, verbose, quiet):
    """
    Display known anti-pattern reference guide.

    Examples:

        # View anti-pattern reference
        elastic-janitor query-analyzer patterns
    """
    option_query_known_patterns(es)
