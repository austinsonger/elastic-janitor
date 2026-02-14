"""
Main CLI entry point for Elastic Janitor.
"""
import click
from ..config import console


@click.group()
@click.version_option(version='1.0.0', prog_name='elastic-janitor')
@click.help_option('-h', '--help')
def cli():
    """
    Elastic Janitor - Elasticsearch Cluster Management Tool
    
    A comprehensive CLI tool for managing, monitoring, and optimizing
    Elasticsearch clusters.
    
    Examples:
    
        # Check cluster health
        elastic-janitor cluster health
        
        # List largest indices
        elastic-janitor index largest --top 25
        
        # Clean old data streams (dry-run first!)
        elastic-janitor datastream clean --retention 90d --dry-run
        
        # Enable global dry-run mode
        elastic-janitor dry-run enable
    
    For detailed help on any command:
    
        elastic-janitor <command> --help
    """
    pass


# Import command groups
from .commands import cluster, index, datastream, dryrun, performance, governance, tuning

# Register command groups
cli.add_command(cluster.cluster)
cli.add_command(index.index)
cli.add_command(datastream.datastream)
cli.add_command(dryrun.dryrun)
cli.add_command(performance.perf)
cli.add_command(governance.governance)
cli.add_command(tuning.tuning)


if __name__ == '__main__':
    cli()

