"""
Performance tuning commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.performance_tuning import (
    option_auto_tuning_engine,
    option_shard_size_optimizer,
    option_refresh_interval_tuner,
    option_merge_policy_optimizer,
    option_cache_tuning,
    option_jvm_tuning_assistant,
)


@click.group()
def tuning():
    """Performance tuning and optimization commands."""
    pass


@tuning.command()
@common_options
@handle_errors
@pass_es_client
def auto_tune(es, output, verbose, quiet):
    """
    Analyze cluster and recommend performance optimizations.
    
    Examples:
    
        # Run auto-tuning analysis
        elastic-janitor tuning auto-tune
    """
    if not quiet:
        info("Running auto-tuning analysis...")
    
    option_auto_tuning_engine(es)


@tuning.command()
@click.option('--target-size', '-t', default=30, help='Target shard size in GB', type=int)
@common_options
@handle_errors
@pass_es_client
def shard_optimizer(es, target_size, output, verbose, quiet):
    """
    Analyze shard distribution and recommend optimal shard counts.
    
    Examples:
    
        # Analyze with default 30GB target
        elastic-janitor tuning shard-optimizer
        
        # Use custom target size
        elastic-janitor tuning shard-optimizer --target-size 50
    """
    if not quiet:
        info(f"Analyzing shard distribution (target: {target_size}GB)...")
    
    option_shard_size_optimizer(es)


@tuning.command()
@click.option('--pattern', '-p', default='*', help='Index pattern to analyze')
@common_options
@handle_errors
@pass_es_client
def refresh_interval(es, pattern, output, verbose, quiet):
    """
    Analyze and optimize refresh intervals based on workload.
    
    Examples:
    
        # Analyze refresh intervals
        elastic-janitor tuning refresh-interval --pattern "logs-*"
    """
    if not quiet:
        info(f"Analyzing refresh intervals for pattern: {pattern}")
    
    option_refresh_interval_tuner(es)


@tuning.command()
@click.option('--pattern', '-p', default='*', help='Index pattern to analyze')
@common_options
@handle_errors
@pass_es_client
def merge_policy(es, pattern, output, verbose, quiet):
    """
    Analyze segments and recommend merge policy optimizations.
    
    Examples:
    
        # Analyze merge policies
        elastic-janitor tuning merge-policy --pattern "logs-*"
    """
    if not quiet:
        info(f"Analyzing merge policies for pattern: {pattern}")
    
    option_merge_policy_optimizer(es)


@tuning.command()
@common_options
@handle_errors
@pass_es_client
def cache(es, output, verbose, quiet):
    """
    Analyze cache performance and recommend optimizations.
    
    Examples:
    
        # Analyze cache performance
        elastic-janitor tuning cache
    """
    if not quiet:
        info("Analyzing cache performance...")
    
    option_cache_tuning(es)


@tuning.command()
@common_options
@handle_errors
@pass_es_client
def jvm(es, output, verbose, quiet):
    """
    Analyze JVM performance and recommend heap/GC optimizations.
    
    Examples:
    
        # Analyze JVM performance
        elastic-janitor tuning jvm
    """
    if not quiet:
        info("Analyzing JVM performance...")
    
    option_jvm_tuning_assistant(es)

