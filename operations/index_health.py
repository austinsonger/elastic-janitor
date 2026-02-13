"""
Index management operations for Elastic Janitor - Health & Diagnostics.
Health monitoring and shard analysis.
"""
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console
from ..utils import show_breadcrumb, select_from_list


def option_index_health_dashboard(es):
    """Display health status for all indices with filtering options."""
    show_breadcrumb(["Main Menu", "Index Management", "Index Health Dashboard"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index health information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        health_data = es.cat.indices(format="json", h="index,health,status,pri,rep,docs.count,store.size,creation.date")

    # Group by health status
    health_groups = {"green": [], "yellow": [], "red": []}

    for idx in health_data:
        health = idx.get("health", "unknown")
        if health in health_groups:
            health_groups[health].append(idx)

    # Summary
    console.print()
    summary = Table(title="Index Health Summary", box=box.DOUBLE_EDGE, title_style="bold cyan")
    summary.add_column("Health Status", style="cyan")
    summary.add_column("Count", justify="right")

    summary.add_row("[green]Green[/green]", f"[green]{len(health_groups['green'])}[/green]")
    summary.add_row("[yellow]Yellow[/yellow]", f"[yellow]{len(health_groups['yellow'])}[/yellow]")
    summary.add_row("[red]Red[/red]", f"[red]{len(health_groups['red'])}[/red]")

    console.print(summary)
    console.print()

    # Filter options
    filter_choice = select_from_list(
        "Filter by health status:",
        choices=["All", "Green only", "Yellow only", "Red only", "Yellow + Red", "Back to menu"],
        multi=False
    )

    if not filter_choice or filter_choice == "Back to menu":
        return

    # Determine which indices to show
    if filter_choice == "All":
        indices_to_show = health_data
    elif filter_choice == "Green only":
        indices_to_show = health_groups["green"]
    elif filter_choice == "Yellow only":
        indices_to_show = health_groups["yellow"]
    elif filter_choice == "Red only":
        indices_to_show = health_groups["red"]
    elif filter_choice == "Yellow + Red":
        indices_to_show = health_groups["yellow"] + health_groups["red"]

    if not indices_to_show:
        console.print("[yellow]No indices match the selected filter.[/yellow]\n")
        return

    # Display detailed table
    console.print()
    table = Table(title=f"Index Health Details - {filter_choice}", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Index", style="cyan", no_wrap=False)
    table.add_column("Health", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Pri", justify="right")
    table.add_column("Rep", justify="right")
    table.add_column("Docs", justify="right")
    table.add_column("Size", justify="right")

    for idx in indices_to_show[:50]:  # Limit to 50 for readability
        health = idx.get("health", "unknown")
        health_color = {"green": "[green]●[/green]", "yellow": "[yellow]●[/yellow]", "red": "[red]●[/red]"}.get(health, "●")

        table.add_row(
            idx.get("index", ""),
            health_color,
            idx.get("status", ""),
            idx.get("pri", ""),
            idx.get("rep", ""),
            idx.get("docs.count", "0"),
            idx.get("store.size", "0b")
        )

    console.print(table)

    if len(indices_to_show) > 50:
        console.print(f"\n[dim]Showing first 50 of {len(indices_to_show)} indices[/dim]\n")

    console.print()




def option_shard_analysis(es):
    """Show comprehensive shard information."""
    show_breadcrumb(["Main Menu", "Index Management", "Shard Analysis"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing shards..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        shards = es.cat.shards(format="json", h="index,shard,prirep,state,docs,store,node,unassigned.reason")

    # Analyze shard distribution
    primary_count = sum(1 for s in shards if s.get("prirep") == "p")
    replica_count = sum(1 for s in shards if s.get("prirep") == "r")
    unassigned = [s for s in shards if s.get("state") != "STARTED"]

    # Node distribution
    node_distribution = defaultdict(int)
    for s in shards:
        node = s.get("node")
        if node:
            node_distribution[node] += 1

    # Summary
    console.print()
    summary = Table(title="Shard Analysis Summary", box=box.DOUBLE_EDGE, title_style="bold cyan")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")

    summary.add_row("Total Shards", str(len(shards)))
    summary.add_row("Primary Shards", f"[green]{primary_count}[/green]")
    summary.add_row("Replica Shards", f"[blue]{replica_count}[/blue]")
    summary.add_row("Unassigned Shards", f"[red]{len(unassigned)}[/red]" if unassigned else "[green]0[/green]")
    summary.add_row("Nodes with Shards", str(len(node_distribution)))

    console.print(summary)
    console.print()

    # Node distribution
    if node_distribution:
        console.print()
        node_table = Table(title="Shard Distribution by Node", box=box.ROUNDED, title_style="bold cyan")
        node_table.add_column("Node", style="cyan")
        node_table.add_column("Shard Count", justify="right")

        for node, count in sorted(node_distribution.items(), key=lambda x: x[1], reverse=True):
            node_table.add_row(node, str(count))

        console.print(node_table)
        console.print()

    # Unassigned shards
    if unassigned:
        console.print()
        unassigned_table = Table(title="Unassigned Shards", box=box.ROUNDED, title_style="bold red")
        unassigned_table.add_column("Index", style="cyan")
        unassigned_table.add_column("Shard", justify="right")
        unassigned_table.add_column("Type", justify="center")
        unassigned_table.add_column("State", style="red")
        unassigned_table.add_column("Reason", style="yellow")

        for s in unassigned[:20]:  # Show first 20
            unassigned_table.add_row(
                s.get("index", ""),
                s.get("shard", ""),
                s.get("prirep", ""),
                s.get("state", ""),
                s.get("unassigned.reason", "N/A")
            )

        console.print(unassigned_table)

        if len(unassigned) > 20:
            console.print(f"\n[dim]Showing first 20 of {len(unassigned)} unassigned shards[/dim]\n")

    console.print()




