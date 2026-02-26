"""
Main menu for Elastic Janitor.
"""
import sys
import questionary
from questionary import Choice, Separator
from rich.panel import Panel
from rich import box
from ..config import console, custom_style, GOD_MODE
from ..core import connect
from ..utils import show_breadcrumb
from ..operations import option_dashboard_stats_view, toggle_god_mode
from ..operations.web_dashboard import option_launch_web_dashboard
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
    submenu_data_quality,
    submenu_aws_ingestion,
    submenu_developer_tools,
    submenu_data_governance,
    submenu_performance_tuning,
    submenu_auto_remediation,
    submenu_policy_actions,
    submenu_query_analyzer,
    submenu_shard_advisor,
    submenu_template_optimizer,
)


def show_god_mode_banner():
    """Display warning banner when God-Mode is active."""
    from .. import config
    if config.GOD_MODE:
        console.print(Panel(
            "[bold white]GOD-MODE ACTIVE[/bold white]\n"
            "[white]Destructive operations WILL execute permanently[/white]",
            title="[bold]WARNING[/bold]",
            border_style="bold red",
            box=box.DOUBLE_EDGE,
            style="red on yellow"
        ))
        console.print()


def menu():
    """Display the new hierarchical main menu."""
    show_breadcrumb(["Main Menu"])
    show_god_mode_banner()




def main():
    console.print()
    console.print(Panel("[bold cyan]🧹 Elastic Janitor[/bold cyan]", box=box.DOUBLE, style="cyan"))
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
                    questionary.Choice("🔍 Data Quality & Validation", value="10"),
                    questionary.Choice("🔥 AWS Ingestion Management", value="11"),
                    questionary.Choice("🛠️  Developer Tools", value="12"),
                    questionary.Choice("🏛️  Data Quality & Governance", value="13"),
                    questionary.Choice("⚙️  Performance Tuning", value="14"),
                    questionary.Choice("🩺 Auto-Remediation Engine", value="15"),
                    questionary.Choice("📜 Policy-Based Actions", value="16"),
                    questionary.Choice("🔎 Query Performance Analyzer", value="17"),
                    questionary.Choice("⚖️  Shard Rebalancing Advisor", value="18"),
                    questionary.Choice("📐 Index Template Optimizer", value="19"),
                    questionary.Choice("📈 Dashboard & Stats View", value="20"),
                    questionary.Choice("🌐 Launch Web Dashboard", value="21"),
                    questionary.Choice("Toggle God-Mode", value="22"),
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
            submenu_data_quality(es)
        elif choice == "11":
            submenu_aws_ingestion(es)
        elif choice == "12":
            submenu_developer_tools(es)
        elif choice == "13":
            submenu_data_governance(es)
        elif choice == "14":
            submenu_performance_tuning(es)
        elif choice == "15":
            submenu_auto_remediation(es)
        elif choice == "16":
            submenu_policy_actions(es)
        elif choice == "17":
            submenu_query_analyzer(es)
        elif choice == "18":
            submenu_shard_advisor(es)
        elif choice == "19":
            submenu_template_optimizer(es)
        elif choice == "20":
            option_dashboard_stats_view(es)
        elif choice == "21":
            option_launch_web_dashboard(es)
        elif choice == "22":
            toggle_god_mode()


if __name__ == "__main__":
    main()


