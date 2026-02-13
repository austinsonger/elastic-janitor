"""
Output formatting utilities for CLI.
"""
import json
import yaml
import csv
import sys
from enum import Enum
from rich.table import Table
from rich.console import Console
from ...config import console as rich_console


class OutputFormat(str, Enum):
    """Output format options."""
    JSON = "json"
    TABLE = "table"
    YAML = "yaml"
    CSV = "csv"


def format_output(data, format_type=OutputFormat.TABLE, headers=None, title=None):
    """
    Format and output data in the specified format.
    
    Args:
        data: Data to output (dict, list of dicts, or simple value)
        format_type: Output format (json, table, yaml, csv)
        headers: Column headers for table/csv output
        title: Title for table output
    """
    if format_type == OutputFormat.JSON:
        _output_json(data)
    elif format_type == OutputFormat.YAML:
        _output_yaml(data)
    elif format_type == OutputFormat.CSV:
        _output_csv(data, headers)
    else:  # TABLE
        _output_table(data, headers, title)


def _output_json(data):
    """Output data as JSON."""
    print(json.dumps(data, indent=2, default=str))


def _output_yaml(data):
    """Output data as YAML."""
    print(yaml.dump(data, default_flow_style=False, sort_keys=False))


def _output_csv(data, headers=None):
    """Output data as CSV."""
    if not data:
        return
    
    # Handle list of dicts
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        if not headers:
            headers = list(data[0].keys())
        
        writer = csv.DictWriter(sys.stdout, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    
    # Handle single dict
    elif isinstance(data, dict):
        if not headers:
            headers = list(data.keys())
        
        writer = csv.DictWriter(sys.stdout, fieldnames=headers)
        writer.writeheader()
        writer.writerow(data)
    
    # Handle simple list
    elif isinstance(data, list):
        writer = csv.writer(sys.stdout)
        if headers:
            writer.writerow(headers)
        for item in data:
            if isinstance(item, (list, tuple)):
                writer.writerow(item)
            else:
                writer.writerow([item])


def _output_table(data, headers=None, title=None):
    """Output data as a Rich table."""
    if not data:
        rich_console.print("[yellow]No data to display[/yellow]")
        return
    
    # Handle list of dicts
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        if not headers:
            headers = list(data[0].keys())
        
        table = Table(title=title, show_header=True, header_style="bold cyan")
        
        for header in headers:
            table.add_column(header, style="cyan")
        
        for row in data:
            table.add_row(*[str(row.get(h, "")) for h in headers])
        
        rich_console.print(table)
    
    # Handle single dict
    elif isinstance(data, dict):
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="yellow")
        
        for key, value in data.items():
            table.add_row(str(key), str(value))
        
        rich_console.print(table)
    
    # Handle simple list
    elif isinstance(data, list):
        table = Table(title=title, show_header=False)
        table.add_column("Value", style="cyan")
        
        for item in data:
            table.add_row(str(item))
        
        rich_console.print(table)
    
    # Handle simple value
    else:
        rich_console.print(f"[cyan]{data}[/cyan]")


def success(message):
    """Print success message."""
    rich_console.print(f"[green]✓ {message}[/green]")


def error(message):
    """Print error message."""
    rich_console.print(f"[red]✗ {message}[/red]")


def warning(message):
    """Print warning message."""
    rich_console.print(f"[yellow]⚠ {message}[/yellow]")


def info(message):
    """Print info message."""
    rich_console.print(f"[cyan]ℹ {message}[/cyan]")

