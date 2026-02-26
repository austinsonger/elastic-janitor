"""
Policy management commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.template_policy_advanced import (
    option_policy_health_checker,
    option_template_policy_alignment_detector
)


@click.group()
def policy():
    """Policy management commands."""
    pass


@policy.command(name='health-check')
@common_options
@handle_errors
@pass_es_client
def health_check(es, output, verbose, quiet):
    """
    Analyze ILM policies for misconfigurations and best practice violations.
    
    Detects:
    - Phase transition logic issues
    - Orphaned policies (not referenced by templates/indices)
    - Missing rollover conditions
    - Conflicting settings (e.g., readonly in hot phase)
    
    Examples:
    
        # Check all ILM policies for health issues
        elastic-janitor policy health-check
        
        # Verbose output
        elastic-janitor policy health-check --verbose
    """
    if not quiet:
        info("Analyzing ILM policies for health issues...")
    
    option_policy_health_checker(es)


@policy.command()
@common_options
@handle_errors
@pass_es_client
def alignment(es, output, verbose, quiet):
    """
    Cross-reference templates, policies, and indices to find misalignments.
    
    Detects:
    - Unmanaged indices (created from templates without ILM policy)
    - Priority-policy mismatches
    - Orphaned policy references in templates
    - Pattern coverage gaps
    
    Examples:
    
        # Check template-policy alignment
        elastic-janitor policy alignment
        
        # JSON output
        elastic-janitor policy alignment --output json
    """
    if not quiet:
        info("Analyzing template-policy alignment...")
    
    option_template_policy_alignment_detector(es)

