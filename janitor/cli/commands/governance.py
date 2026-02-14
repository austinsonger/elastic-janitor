"""
Data governance commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.data_governance import (
    option_schema_evolution_tracker,
    option_data_lineage_viewer,
    option_pii_detection,
    option_data_quality_scoring,
    option_metadata_management,
    option_data_dictionary,
)


@click.group()
def governance():
    """Data quality and governance commands."""
    pass


@governance.command()
@click.option('--pattern', '-p', default='*', help='Index pattern to track')
@click.option('--days', '-d', default=30, help='Number of days to look back', type=int)
@common_options
@handle_errors
@pass_es_client
def schema_evolution(es, pattern, days, output, verbose, quiet):
    """
    Track mapping changes over time across indices.
    
    Examples:
    
        # Track schema evolution for logs indices
        elastic-janitor governance schema-evolution --pattern "logs-*"
        
        # Look back 60 days
        elastic-janitor governance schema-evolution --days 60
    """
    if not quiet:
        info(f"Tracking schema evolution for pattern: {pattern}")
    
    # Call the operation function
    option_schema_evolution_tracker(es)


@governance.command()
@common_options
@handle_errors
@pass_es_client
def data_lineage(es, output, verbose, quiet):
    """
    Visualize data flow through ingest pipelines and transforms.
    
    Examples:
    
        # View data lineage
        elastic-janitor governance data-lineage
    """
    if not quiet:
        info("Analyzing data lineage...")
    
    option_data_lineage_viewer(es)


@governance.command()
@click.option('--pattern', '-p', default='*', help='Index pattern to scan')
@click.option('--sample-size', '-s', default=1000, help='Sample size per index', type=int)
@common_options
@handle_errors
@pass_es_client
def pii_detection(es, pattern, sample_size, output, verbose, quiet):
    """
    Scan documents for PII patterns (emails, SSNs, phone numbers, etc.).
    
    Examples:
    
        # Scan for PII in logs indices
        elastic-janitor governance pii-detection --pattern "logs-*"
        
        # Use larger sample size
        elastic-janitor governance pii-detection --sample-size 5000
    """
    if not quiet:
        info(f"Scanning for PII in pattern: {pattern}")
    
    option_pii_detection(es)


@governance.command()
@click.option('--pattern', '-p', default='*', help='Index pattern to score')
@click.option('--sample-size', '-s', default=1000, help='Sample size per index', type=int)
@click.option('--threshold', '-t', default=70, help='Quality threshold (0-100)', type=int)
@common_options
@handle_errors
@pass_es_client
def quality_score(es, pattern, sample_size, threshold, output, verbose, quiet):
    """
    Score indices based on completeness, consistency, and validity.
    
    Examples:
    
        # Score data quality
        elastic-janitor governance quality-score --pattern "logs-*"
        
        # Set custom threshold
        elastic-janitor governance quality-score --threshold 80
    """
    if not quiet:
        info(f"Scoring data quality for pattern: {pattern}")
    
    option_data_quality_scoring(es)


@governance.command()
@common_options
@handle_errors
@pass_es_client
def metadata(es, output, verbose, quiet):
    """
    Manage index metadata (owner, purpose, sensitivity, etc.).
    
    Examples:
    
        # Manage metadata
        elastic-janitor governance metadata
    """
    if not quiet:
        info("Managing index metadata...")
    
    option_metadata_management(es)


@governance.command()
@common_options
@handle_errors
@pass_es_client
def dictionary(es, output, verbose, quiet):
    """
    Maintain field documentation and data dictionary.
    
    Examples:
    
        # Manage data dictionary
        elastic-janitor governance dictionary
    """
    if not quiet:
        info("Managing data dictionary...")
    
    option_data_dictionary(es)

