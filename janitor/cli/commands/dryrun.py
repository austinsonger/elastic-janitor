"""
Global dry-run mode management commands.
"""
import click
from ..utils.output import success, error, info, warning
from ... import config


@click.group(name='dry-run')
def dryrun():
    """Global dry-run mode management."""
    pass


@dryrun.command()
def enable():
    """
    Enable global dry-run mode.
    
    When enabled, all destructive operations will show what would be
    changed without actually making changes.
    
    Examples:
    
        # Enable dry-run mode
        elastic-janitor dry-run enable
    """
    config.DRY_RUN_MODE = True
    success("Dry-run mode ENABLED")
    info("All destructive operations will now show what would be changed")
    info("without actually making changes.")
    info("")
    info("To disable: elastic-janitor dry-run disable")


@dryrun.command()
def disable():
    """
    Disable global dry-run mode.
    
    When disabled, destructive operations will be executed normally.
    
    Examples:
    
        # Disable dry-run mode
        elastic-janitor dry-run disable
    """
    config.DRY_RUN_MODE = False
    warning("Dry-run mode DISABLED")
    warning("Destructive operations will now be executed normally.")
    info("")
    info("To enable: elastic-janitor dry-run enable")


@dryrun.command()
def status():
    """
    Check current dry-run mode status.
    
    Examples:
    
        # Check status
        elastic-janitor dry-run status
    """
    from ...config import console
    
    console.print("\n[bold cyan]Dry-Run Mode Status[/bold cyan]")
    console.print("=" * 70)
    console.print()
    
    if config.DRY_RUN_MODE:
        console.print("[green]Global Dry-Run Mode: ENABLED[/green]")
        console.print()
        console.print("[yellow]All destructive operations will show what would be changed[/yellow]")
        console.print("[yellow]without actually making changes.[/yellow]")
        console.print()
        console.print("To disable: [cyan]elastic-janitor dry-run disable[/cyan]")
    else:
        console.print("[red]Global Dry-Run Mode: DISABLED[/red]")
        console.print()
        console.print("[yellow]Destructive operations will be executed normally.[/yellow]")
        console.print()
        console.print("To enable: [cyan]elastic-janitor dry-run enable[/cyan]")
    
    console.print()

