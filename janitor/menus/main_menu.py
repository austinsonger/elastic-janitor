"""
Main menu for Elastic Janitor.
"""
import sys
import questionary
from questionary import Choice, Separator
from rich.table import Table
from rich.panel import Panel
from rich import box
from ..config import console, custom_style, DRY_RUN_MODE
from ..core import connect
from ..utils import show_breadcrumb
from ..operations import option_dashboard_stats_view, toggle_dry_run_mode
from .submenus import (
    submenu_index_management,
    submenu_data_streams,
    submenu_templates_policies,
    submenu_snapshots,
    submenu_cluster_health,
    submenu_storage_optimization,
    submenu_performance_monitoring,
    submenu_bulk_automation,
    submenu_advanced_cleanup,
)


def menu():
    """Display the new hierarchical main menu."""
    show_breadcrumb(["Main Menu"])

    # Display dry-run mode status
    global DRY_RUN_MODE
    dry_run_status = "[green]ENABLED[/green]" if DRY_RUN_MODE else "[red]DISABLED[/red]"
    console.print(f"[dim]Dry-Run Mode: {dry_run_status}[/dim]")

    # Display menu table without the numbered column
    menu_table = Table(
        title="🧹 Elastic Janitor - Main Menu",
        box=box.ROUNDED,
        title_style="bold cyan",
        show_header=False
    )
    menu_table.add_column("Category", style="white")
    menu_table.add_column("Description", style="dim")

    menu_table.add_row("📊 Index Management", "Health, shards, settings, aliases, rollover, optimization")
    menu_table.add_row("🌊 Data Stream Management", "Clean and manage data streams")
    menu_table.add_row("📋 Template & Policy Management", "Index templates, component templates, ILM, pipelines")
    menu_table.add_row("💾 Snapshot & Backup Management", "Repositories, snapshots, SLM policies")
    menu_table.add_row("🏥 Cluster Health & Diagnostics", "Cluster health, nodes, statistics")
    menu_table.add_row("💰 Storage & Cost Optimization", "Forecast, tier distribution, compression, cost estimation")
    menu_table.add_row("⚡ Performance & Monitoring", "Query analysis, indexing rates, resource usage, hot spots")
    menu_table.add_row("🔧 Bulk Operations & Automation", "Batch operations, history log, config management")
    menu_table.add_row("🧹 Advanced Cleanup Features", "Orphaned docs, field cleanup, mapping cleanup, duplicates")
    menu_table.add_row("📈 Dashboard & Stats View", "Real-time monitoring dashboard")
    menu_table.add_row("🔍 Toggle Dry-Run Mode", f"Current: {dry_run_status}")
    menu_table.add_row("", "")
    menu_table.add_row("Quit", "")

    console.print()
    console.print(menu_table)
    console.print()




def main():
    console.print()
    console.print(Panel("[bold cyan]🧹 Elastic Janitor - Enhanced Edition[/bold cyan]", box=box.DOUBLE, style="cyan"))
    console.print()
    es = connect()

    while True:
        menu()

        # Use questionary.select for arrow key navigation
        try:
            choice = questionary.select(
                "Select category:",
                choices=[
                    questionary.Choice("📊 Index Management", value="1"),
                    questionary.Choice("🌊 Data Stream Management", value="2"),
                    questionary.Choice("📋 Template & Policy Management", value="3"),
                    questionary.Choice("💾 Snapshot & Backup Management", value="4"),
                    questionary.Choice("🏥 Cluster Health & Diagnostics", value="5"),
                    questionary.Choice("💰 Storage & Cost Optimization", value="6"),
                    questionary.Choice("⚡ Performance & Monitoring", value="7"),
                    questionary.Choice("🔧 Bulk Operations & Automation", value="8"),
                    questionary.Choice("🧹 Advanced Cleanup Features", value="9"),
                    questionary.Choice("📈 Dashboard & Stats View", value="10"),
                    questionary.Choice("🔍 Toggle Dry-Run Mode", value="11"),
                    questionary.Separator(),
                    questionary.Choice("Quit", value="q"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("q", "quit", "exit"):
            console.print("\n[cyan]👋 Bye![/cyan]\n")
            return

        if choice == "1":
            submenu_index_management(es)
        elif choice == "2":
            submenu_data_streams(es)
        elif choice == "3":
            submenu_templates_policies(es)
        elif choice == "4":
            submenu_snapshots(es)
        elif choice == "5":
            submenu_cluster_health(es)
        elif choice == "6":
            submenu_storage_optimization(es)
        elif choice == "7":
            submenu_performance_monitoring(es)
        elif choice == "8":
            submenu_bulk_automation(es)
        elif choice == "9":
            submenu_advanced_cleanup(es)
        elif choice == "10":
            option_dashboard_stats_view(es)
        elif choice == "11":
            toggle_dry_run_mode()


if __name__ == "__main__":
    main()


