"""
Template management commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.template_policy_advanced import (
    option_template_validation_analyzer,
    option_performance_impact_analyzer
)


@click.group()
def template():
    """Template management commands."""
    pass


@template.command()
@common_options
@handle_errors
@pass_es_client
def validate(es, output, verbose, quiet):
    """
    Analyze index templates and component templates for configuration issues.
    
    Detects:
    - Missing/incomplete settings (replicas, refresh_interval, shards)
    - Lifecycle policy gaps
    - Shard configuration issues
    - Component template validation (circular dependencies, broken references)
    
    Examples:
    
        # Analyze all templates for configuration issues
        elastic-janitor template validate
        
        # Verbose output
        elastic-janitor template validate --verbose
    """
    if not quiet:
        info("Analyzing templates for configuration issues...")
    
    option_template_validation_analyzer(es)


@template.command(name='performance-impact')
@common_options
@handle_errors
@pass_es_client
def performance_impact(es, output, verbose, quiet):
    """
    Analyze template settings for potential performance problems.
    
    Detects:
    - Excessive replicas
    - Shard over-allocation
    - Disabled refresh intervals
    - Missing field mappings for timestamps
    - Suboptimal codec and tier settings
    
    Examples:
    
        # Analyze templates for performance issues
        elastic-janitor template performance-impact
        
        # JSON output
        elastic-janitor template performance-impact --output json
    """
    if not quiet:
        info("Analyzing templates for performance issues...")
    
    option_performance_impact_analyzer(es)

