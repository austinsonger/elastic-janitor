"""
God-Mode management commands.
"""
import click
from ..utils.output import success, error, info, warning
from ... import config


@click.group(name='god-mode')
def godmode():
    """God-Mode management - enable destructive operations."""
    pass


@click.command()
def enable():
    """
    Enable God-Mode to execute destructive operations.
    
    When enabled, all destructive operations (delete, cleanup, etc.)
    will be executed permanently. Requires confirmation phrase.
    
    Examples:
    
        # Enable God-Mode
        elastic-janitor god-mode enable
    """
    from ...config import console, GOD_MODE_CONFIRMATION_PHRASE
    
    if config.GOD_MODE:
        warning("God-Mode is already ENABLED")
        return
    
    console.print()
    console.print("[bold red]WARNING: You are about to enable God-Mode[/bold red]")
    console.print("[yellow]All destructive operations will execute PERMANENTLY.[/yellow]")
    console.print()
    console.print(f"[cyan]Type '{GOD_MODE_CONFIRMATION_PHRASE}' to confirm:[/cyan]")
    
    try:
        confirmation = input("> ").strip()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        return
    
    if confirmation == GOD_MODE_CONFIRMATION_PHRASE:
        config.GOD_MODE = True
        console.print()
        error("GOD-MODE ENABLED")
        warning("All destructive operations will now execute permanently.")
        info("")
        info("To disable: elastic-janitor god-mode disable")
    else:
        console.print()
        success("God-Mode NOT enabled - Safe mode remains active")
        info("All operations will continue to simulate without making changes.")


@click.command()
def disable():
    """
    Disable God-Mode and return to safe mode.
    
    When disabled (default), all destructive operations will simulate
    without making actual changes.
    
    Examples:
    
        # Disable God-Mode
        elastic-janitor god-mode disable
    """
    config.GOD_MODE = False
    success("God-Mode DISABLED - Safe mode active")
    info("All operations will now simulate without making changes.")


@click.command()
def status():
    """
    Check current God-Mode status.
    
    Examples:
    
        # Check status
        elastic-janitor god-mode status
    """
    from ...config import console
    
    console.print("\n[bold cyan]God-Mode Status[/bold cyan]")
    console.print("=" * 70)
    console.print()
    
    if config.GOD_MODE:
        console.print("[bold red]GOD-MODE: ENABLED[/bold red]")
        console.print()
        console.print("[yellow]All destructive operations will execute permanently.[/yellow]")
        console.print()
        console.print("To disable: [cyan]elastic-janitor god-mode disable[/cyan]")
    else:
        console.print("[bold green]SAFE MODE: ACTIVE[/bold green]")
        console.print()
        console.print("[dim]All operations simulate without making changes (default).[/dim]")
        console.print()
        console.print("To enable destructive operations: [cyan]elastic-janitor god-mode enable[/cyan]")
    
    console.print()


# Add commands to group
godmode.add_command(enable)
godmode.add_command(disable)
godmode.add_command(status)
