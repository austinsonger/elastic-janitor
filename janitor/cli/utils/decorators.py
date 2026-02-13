"""
Common decorators for CLI commands.
"""
import sys
import functools
import click
from elasticsearch import Elasticsearch
from ...config import ELASTIC_URL, ELASTIC_API_KEY, console
from ...core.connection import connect
from .output import error


def pass_es_client(f):
    """
    Decorator to pass Elasticsearch client to command.
    Handles connection and error handling.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            es = connect()
            return f(*args, es=es, **kwargs)
        except Exception as e:
            error(f"Failed to connect to Elasticsearch: {e}")
            sys.exit(3)
    return wrapper


def handle_errors(f):
    """
    Decorator to handle common errors in CLI commands.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            sys.exit(130)
        except Exception as e:
            error(f"Command failed: {e}")
            if kwargs.get('verbose'):
                import traceback
                traceback.print_exc()
            sys.exit(1)
    return wrapper


def dry_run_option(f):
    """
    Decorator to add --dry-run option to a command.
    """
    @click.option(
        '--dry-run', '-d',
        is_flag=True,
        help='Preview changes without executing'
    )
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapper


def common_options(f):
    """
    Decorator to add common options to all commands.
    """
    @click.option(
        '--verbose', '-v',
        is_flag=True,
        help='Enable verbose output'
    )
    @click.option(
        '--quiet', '-q',
        is_flag=True,
        help='Suppress non-essential output'
    )
    @click.option(
        '--output', '-o',
        type=click.Choice(['json', 'table', 'yaml', 'csv'], case_sensitive=False),
        default='table',
        help='Output format'
    )
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapper

