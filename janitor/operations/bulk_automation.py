"""
Bulk Operations & Automation for Elastic Janitor.
Batch operations, scheduled cleanup, dry-run mode, operation history, and configuration management.
"""
import os
import yaml
from datetime import datetime
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, PROTECT_SYSTEM, MAX_DELETE_LIMIT, DRY_RUN_MODE
from ..utils import (
    safe_input, is_system, confirm_delete, confirm_action,
    show_breadcrumb, select_from_list, get_number_input
)


def option_batch_index_operations(es):
    """Allow users to select multiple indices and apply settings changes in bulk."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Batch Index Operations"])
    
    console.print("\n[cyan]Batch Index Operations[/cyan]\n")
    
    try:
        # Get all indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_list = es.cat.indices(format="json", h="index,health,status")
        
        # Filter out system indices if protected
        index_names = [idx["index"] for idx in indices_list if not (PROTECT_SYSTEM and is_system(idx["index"]))]
        index_names.sort()
        
        if not index_names:
            console.print("[yellow]🟡 No indices found.[/yellow]\n")
            return
        
        # Let user select multiple indices
        console.print(f"[bold]Found {len(index_names)} indices[/bold]\n")
        
        # Create choices for selection
        choices = [f"{idx}" for idx in index_names]
        
        selected_indices = select_from_list(
            "Select indices to modify (use space to select, enter to confirm):",
            choices,
            multi=True
        )
        
        if not selected_indices:
            console.print("\n[yellow]⚠️  No indices selected.[/yellow]\n")
            return
        
        console.print(f"\n[cyan]Selected {len(selected_indices)} indices[/cyan]\n")
        
        # Show operation options
        console.print("[bold]Select operation to apply:[/bold]")
        console.print("1) Set number of replicas")
        console.print("2) Set refresh interval")
        console.print("3) Set read-only mode")
        console.print("4) Remove read-only mode")
        console.print("5) Close indices")
        console.print("6) Open indices")
        console.print("q) Cancel\n")
        
        operation = safe_input("Select operation: ").strip().lower()
        
        if operation in ("q", "quit", "cancel"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return
        
        # Execute operation based on choice
        if operation == "1":
            replicas = get_number_input("Enter number of replicas", default=1, min_val=0, max_val=10)
            if replicas is None:
                return
            
            settings = {"index.number_of_replicas": replicas}
            operation_name = f"Set replicas to {replicas}"
            
        elif operation == "2":
            interval = safe_input("Enter refresh interval (e.g., '30s', '1m', '-1' for disable): ").strip()
            if not interval:
                return
            
            settings = {"index.refresh_interval": interval}
            operation_name = f"Set refresh interval to {interval}"
            
        elif operation == "3":
            settings = {"index.blocks.read_only": True}
            operation_name = "Enable read-only mode"
            
        elif operation == "4":
            settings = {"index.blocks.read_only": False}
            operation_name = "Disable read-only mode"
            
        elif operation == "5":
            # Close indices
            if not confirm_action(f"Close {len(selected_indices)} indices?", len(selected_indices)):
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
                return
            
            console.print()
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Closing indices..."),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("close", total=len(selected_indices))
                
                for idx in selected_indices:
                    try:
                        if not DRY_RUN_MODE:
                            es.indices.close(index=idx)
                        progress.update(task, advance=1)
                    except Exception as e:
                        console.print(f"[red]❌ Failed to close {idx}: {e}[/red]")
            
            console.print(f"\n[green]✅ {'Would close' if DRY_RUN_MODE else 'Closed'} {len(selected_indices)} indices.[/green]\n")
            
            # Log operation
            from ..utils.history_logger import log_operation
            log_operation("CLOSE_INDICES", selected_indices, f"Closed {len(selected_indices)} indices")
            return
            
        elif operation == "6":
            # Open indices
            if not confirm_action(f"Open {len(selected_indices)} indices?", len(selected_indices)):
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
                return
            
            console.print()
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Opening indices..."),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("open", total=len(selected_indices))
                
                for idx in selected_indices:
                    try:
                        if not DRY_RUN_MODE:
                            es.indices.open(index=idx)
                        progress.update(task, advance=1)
                    except Exception as e:
                        console.print(f"[red]❌ Failed to open {idx}: {e}[/red]")
            
            console.print(f"\n[green]✅ {'Would open' if DRY_RUN_MODE else 'Opened'} {len(selected_indices)} indices.[/green]\n")

            # Log operation
            from ..utils.history_logger import log_operation
            log_operation("OPEN_INDICES", selected_indices, f"Opened {len(selected_indices)} indices")
            return

        else:
            console.print("\n[red]❌ Invalid operation.[/red]\n")
            return

        # Confirm settings change
        if not confirm_action(f"{operation_name} for {len(selected_indices)} indices?", len(selected_indices)):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Apply settings
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]{operation_name}..."),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("update", total=len(selected_indices))

            for idx in selected_indices:
                try:
                    if not DRY_RUN_MODE:
                        es.indices.put_settings(index=idx, body=settings)
                    progress.update(task, advance=1)
                except Exception as e:
                    console.print(f"[red]❌ Failed to update {idx}: {e}[/red]")

        console.print(f"\n[green]✅ {'Would update' if DRY_RUN_MODE else 'Updated'} {len(selected_indices)} indices.[/green]\n")

        # Log operation
        from ..utils.history_logger import log_operation
        log_operation("BATCH_SETTINGS_UPDATE", selected_indices, operation_name)

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: {e}[/red]\n")


def option_scheduled_cleanup_jobs(es):
    """Placeholder for scheduled cleanup jobs feature."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Scheduled Cleanup Jobs"])

    console.print()
    placeholder = Panel(
        "[bold yellow]Coming Soon: Configure Cron-Like Scheduled Cleanup Tasks[/bold yellow]\n\n"
        "This feature will allow you to:\n"
        "• Schedule automatic cleanup of old indices and data streams\n"
        "• Configure retention policies with cron-like syntax\n"
        "• Set up automated snapshot cleanup\n"
        "• Receive notifications on cleanup operations\n"
        "• View and manage scheduled jobs\n\n"
        "[dim]This feature is currently under development.[/dim]",
        title="🚧 Feature Not Yet Implemented",
        box=box.DOUBLE_EDGE,
        style="yellow"
    )
    console.print(placeholder)
    console.print()


def option_dry_run_mode(es):
    """Toggle dry-run mode globally."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Dry-Run Mode"])

    from ..operations.cluster import toggle_dry_run_mode
    toggle_dry_run_mode()


def option_operation_history_log(es):
    """Display operation history log."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Operation History Log"])

    console.print("\n[cyan]Operation History Log[/cyan]\n")

    # Check if log file exists
    log_file = "janitor_history.log"

    if not os.path.exists(log_file):
        console.print("[yellow]🟡 No operation history found. The log file will be created when operations are performed.[/yellow]\n")
        return

    try:
        # Read log file
        with open(log_file, "r") as f:
            lines = f.readlines()

        if not lines:
            console.print("[yellow]🟡 Operation history is empty.[/yellow]\n")
            return

        # Display last N entries
        n_input = safe_input("Show last how many entries? (default 20): ").strip()
        n = int(n_input) if n_input else 20

        recent_lines = lines[-n:] if len(lines) > n else lines

        console.print(f"\n[bold]Showing last {len(recent_lines)} operations:[/bold]\n")

        table = Table(title="Operation History", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Operation", style="yellow")
        table.add_column("Details", style="white")

        for line in recent_lines:
            parts = line.strip().split(" | ")
            if len(parts) >= 3:
                table.add_row(parts[0], parts[1], " | ".join(parts[2:]))

        console.print(table)
        console.print()

        # Show log file location
        console.print(f"[dim]Full log file: {os.path.abspath(log_file)}[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not read operation history: {e}[/red]\n")


def option_rollback_capability(es):
    """Placeholder for rollback capability feature."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Rollback Capability"])

    console.print()
    placeholder = Panel(
        "[bold yellow]Coming Soon: Undo Recent Operations[/bold yellow]\n\n"
        "This feature will allow you to:\n"
        "• View recent destructive operations\n"
        "• Restore deleted indices from snapshots\n"
        "• Revert settings changes\n"
        "• Rollback bulk operations\n"
        "• Configure automatic backup before destructive operations\n\n"
        "[dim]This feature is currently under development.[/dim]",
        title="🚧 Feature Not Yet Implemented",
        box=box.DOUBLE_EDGE,
        style="yellow"
    )
    console.print(placeholder)
    console.print()


def option_export_import_configurations(es):
    """Export/import janitor settings to/from YAML file."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Export/Import Configurations"])

    console.print("\n[cyan]Configuration Management[/cyan]\n")
    console.print("[bold]Select operation:[/bold]")
    console.print("1) Export current configuration")
    console.print("2) Import configuration from file")
    console.print("q) Cancel\n")

    choice = safe_input("Select option: ").strip().lower()

    if choice in ("q", "quit", "cancel"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    if choice == "1":
        # Export configuration
        from .. import config

        config_data = {
            "elastic_url": config.ELASTIC_URL,
            "protect_system": config.PROTECT_SYSTEM,
            "default_retention_days": config.DEFAULT_RETENTION_DAYS,
            "max_delete_limit": config.MAX_DELETE_LIMIT,
            "dry_run_mode": config.DRY_RUN_MODE,
            "exported_at": datetime.now().isoformat()
        }

        filename = safe_input("Enter filename to export (default: janitor_config.yaml): ").strip()
        if not filename:
            filename = "janitor_config.yaml"

        try:
            with open(filename, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

            console.print(f"\n[green]✅ Configuration exported to {filename}[/green]\n")

            # Display exported config
            table = Table(title="Exported Configuration", box=box.ROUNDED, title_style="bold cyan")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="white")

            for key, value in config_data.items():
                table.add_row(key, str(value))

            console.print(table)
            console.print()

        except Exception as e:
            console.print(f"\n[red]❌ ERROR: Could not export configuration: {e}[/red]\n")

    elif choice == "2":
        # Import configuration
        filename = safe_input("Enter filename to import: ").strip()
        if not filename:
            console.print("\n[yellow]⚠️  No filename provided.[/yellow]\n")
            return

        if not os.path.exists(filename):
            console.print(f"\n[red]❌ File not found: {filename}[/red]\n")
            return

        try:
            with open(filename, "r") as f:
                config_data = yaml.safe_load(f)

            # Display configuration to import
            table = Table(title="Configuration to Import", box=box.ROUNDED, title_style="bold yellow")
            table.add_column("Setting", style="cyan")
            table.add_column("Current Value", style="white")
            table.add_column("New Value", style="yellow")

            from .. import config

            settings_map = {
                "protect_system": ("PROTECT_SYSTEM", config.PROTECT_SYSTEM),
                "default_retention_days": ("DEFAULT_RETENTION_DAYS", config.DEFAULT_RETENTION_DAYS),
                "max_delete_limit": ("MAX_DELETE_LIMIT", config.MAX_DELETE_LIMIT),
                "dry_run_mode": ("DRY_RUN_MODE", config.DRY_RUN_MODE),
            }

            for key, (attr_name, current_value) in settings_map.items():
                if key in config_data:
                    table.add_row(key, str(current_value), str(config_data[key]))

            console.print()
            console.print(table)
            console.print()

            console.print("[yellow]⚠️  Note: Importing configuration will update settings for this session only.[/yellow]")
            console.print("[yellow]    To persist changes, update the config.py file manually.[/yellow]\n")

            if not confirm_action("Import this configuration?"):
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
                return

            # Apply configuration
            if "protect_system" in config_data:
                config.PROTECT_SYSTEM = config_data["protect_system"]
            if "default_retention_days" in config_data:
                config.DEFAULT_RETENTION_DAYS = config_data["default_retention_days"]
            if "max_delete_limit" in config_data:
                config.MAX_DELETE_LIMIT = config_data["max_delete_limit"]
            if "dry_run_mode" in config_data:
                config.DRY_RUN_MODE = config_data["dry_run_mode"]

            console.print("\n[green]✅ Configuration imported successfully.[/green]\n")

        except Exception as e:
            console.print(f"\n[red]❌ ERROR: Could not import configuration: {e}[/red]\n")

    else:
        console.print("\n[red]❌ Invalid option.[/red]\n")

