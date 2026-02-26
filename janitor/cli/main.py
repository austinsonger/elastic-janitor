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
        
        # Clean old data streams (simulates by default - safe mode)
        elastic-janitor datastream clean --retention 90d
        
        # Enable God-Mode for destructive operations
        elastic-janitor god-mode enable
    
    For detailed help on any command:
    
        elastic-janitor <command> --help
    """
    pass


# Import command groups
from .commands import cluster, index, datastream, godmode, performance, governance, tuning, template, policy
from .commands import remediation, policyactions, queryanalyzer, shardadvisor, templateoptimizer

# Register command groups
cli.add_command(cluster.cluster)
cli.add_command(index.index)
cli.add_command(datastream.datastream)
cli.add_command(godmode.godmode)
cli.add_command(performance.perf)
cli.add_command(governance.governance)
cli.add_command(tuning.tuning)
cli.add_command(template.template)
cli.add_command(policy.policy)
cli.add_command(remediation.remediation)
cli.add_command(policyactions.policy_actions)
cli.add_command(queryanalyzer.query_analyzer)
cli.add_command(shardadvisor.shard_advisor)
cli.add_command(templateoptimizer.template_optimizer)


if __name__ == '__main__':
    cli()

