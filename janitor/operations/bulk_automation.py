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

            # Log operation and track for rollback
            from ..utils.history_logger import log_operation
            log_operation("CLOSE_INDICES", selected_indices, f"Closed {len(selected_indices)} indices")

            if not DRY_RUN_MODE:
                from .rollback import track_destructive_operation
                track_destructive_operation(
                    "CLOSE_INDICES",
                    selected_indices,
                    previous_state={"state": "open"}
                )
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

            # Log operation and track for rollback
            from ..utils.history_logger import log_operation
            log_operation("OPEN_INDICES", selected_indices, f"Opened {len(selected_indices)} indices")

            if not DRY_RUN_MODE:
                from .rollback import track_destructive_operation
                track_destructive_operation(
                    "OPEN_INDICES",
                    selected_indices,
                    previous_state={"state": "closed"}
                )
            return

        else:
            console.print("\n[red]❌ Invalid operation.[/red]\n")
            return

        # Confirm settings change
        if not confirm_action(f"{operation_name} for {len(selected_indices)} indices?", len(selected_indices)):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Get current settings for rollback tracking
        previous_settings = {}
        if not DRY_RUN_MODE:
            try:
                for idx in selected_indices[:1]:  # Sample one index for settings
                    idx_settings = es.indices.get_settings(index=idx)
                    if idx in idx_settings:
                        previous_settings = idx_settings[idx].get("settings", {}).get("index", {})
                        break
            except Exception:
                pass

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

        # Log operation and track for rollback
        from ..utils.history_logger import log_operation
        log_operation("BATCH_SETTINGS_UPDATE", selected_indices, operation_name)

        if not DRY_RUN_MODE:
            from .rollback import track_destructive_operation
            track_destructive_operation(
                "BULK_SETTINGS_CHANGE",
                selected_indices,
                previous_state={"settings": previous_settings},
                operation_params={"settings": settings, "operation": operation_name}
            )

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
    """Display enhanced operation history log with filtering and export."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Operation History Log"])

    from .change_history import enhanced_operation_history
    enhanced_operation_history()


def option_rollback_capability(es):
    """View and rollback recent destructive operations."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Rollback Capability"])

    from .rollback import display_rollback_history
    display_rollback_history(es)


def option_export_import_configurations(es):
    """Configuration versioning with full snapshot, version management, and restore functionality."""
    show_breadcrumb(["Main Menu", "Bulk Operations & Automation", "Export/Import Configurations"])

    from .config_versioning import configuration_versioning_menu
    configuration_versioning_menu(es)

