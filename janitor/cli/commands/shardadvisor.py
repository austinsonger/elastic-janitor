"""
Shard rebalancing advisor CLI commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.shard_advisor import (
    option_shard_distribution_analysis,
    option_shard_count_recommendations,
    option_shard_rebalance_plan,
    option_shard_allocation_strategy,
)


@click.group(name='shard-advisor')
def shard_advisor():
    """Shard rebalancing advisor commands."""
    pass


@shard_advisor.command()
@common_options
@handle_errors
@pass_es_client
def distribution(es, output, verbose, quiet):
    """
    Analyze current shard distribution across nodes.

    Shows allocation summary, balance analysis, and unassigned shards.

    Examples:

        # View shard distribution
        elastic-janitor shard-advisor distribution
    """
    if not quiet:
        info("Analyzing shard distribution...")

    option_shard_distribution_analysis(es)


@shard_advisor.command()
@common_options
@handle_errors
@pass_es_client
def recommend(es, output, verbose, quiet):
    """
    Recommend optimal shard counts for all indices.

    Compares current shard counts against target shard sizes
    and identifies over-sharded and under-sharded indices.

    Examples:

        # Get shard count recommendations
        elastic-janitor shard-advisor recommend
    """
    if not quiet:
        info("Generating shard count recommendations...")

    option_shard_count_recommendations(es)


@shard_advisor.command()
@common_options
@handle_errors
@pass_es_client
def rebalance(es, output, verbose, quiet):
    """
    Generate and optionally execute a shard rebalancing plan.

    Examples:

        # Generate rebalance plan
        elastic-janitor shard-advisor rebalance
    """
    if not quiet:
        info("Generating rebalance plan...")

    option_shard_rebalance_plan(es)


@shard_advisor.command()
@common_options
@handle_errors
@pass_es_client
def strategy(es, output, verbose, quiet):
    """
    Recommend allocation strategies based on node resources.

    Analyzes disk, heap, CPU, and shard counts per node to
    suggest optimal allocation configurations.

    Examples:

        # View allocation strategy recommendations
        elastic-janitor shard-advisor strategy
    """
    if not quiet:
        info("Analyzing allocation strategy...")

    option_shard_allocation_strategy(es)
