"""
Cluster health and diagnostics operations for Elastic Janitor.
Cluster health, node information, statistics, and dry-run mode.
"""
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box
from ..config import console, DRY_RUN_MODE
from ..utils import show_breadcrumb
from .. import config


def toggle_dry_run_mode():
    """Toggle global dry-run mode."""
    global DRY_RUN_MODE
    DRY_RUN_MODE = not DRY_RUN_MODE

    status = "[green]ENABLED[/green]" if DRY_RUN_MODE else "[red]DISABLED[/red]"
    console.print(f"\n[cyan]🔍 Dry-Run Mode: {status}[/cyan]")

    if DRY_RUN_MODE:
        console.print("[yellow]All delete operations will be simulated without executing.[/yellow]\n")
    else:
        console.print("[yellow]Delete operations will be executed normally.[/yellow]\n")




def option_dashboard_stats_view(es):
    """Create a real-time monitoring dashboard using rich.live."""
    show_breadcrumb(["Main Menu", "Dashboard & Stats View"])

    def generate_dashboard():
        """Generate dashboard layout."""
        layout = Layout()

        # Create layout structure
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )

        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )

        # Header
        header_text = Text("🧹 Elastic Janitor - Real-Time Dashboard", style="bold cyan", justify="center")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))

        # Fetch cluster health
        try:
            health = es.cluster.health()
            status = health.get("status", "unknown")
            status_color = {"green": "green", "yellow": "yellow", "red": "red"}.get(status, "white")

            health_table = Table(title="Cluster Health", box=box.ROUNDED, title_style="bold cyan")
            health_table.add_column("Metric", style="cyan")
            health_table.add_column("Value", style="white")

            health_table.add_row("Status", f"[{status_color}]{status}[/{status_color}]")
            health_table.add_row("Nodes", str(health.get("number_of_nodes", 0)))
            health_table.add_row("Active Shards", str(health.get("active_shards", 0)))
            health_table.add_row("Unassigned Shards", str(health.get("unassigned_shards", 0)))

            layout["left"].update(health_table)
        except Exception as e:
            layout["left"].update(Panel(f"[red]Error fetching health: {e}[/red]", box=box.ROUNDED))

        # Fetch storage stats
        try:
            indices_info = get_all_indices_info(es)

            # Calculate tier storage
            tier_storage = defaultdict(int)
            for idx_info in indices_info.values():
                tier = idx_info.get("tier", "unknown")
                tier_storage[tier] += idx_info.get("size_bytes", 0)

            storage_table = Table(title="Storage by Tier", box=box.ROUNDED, title_style="bold cyan")
            storage_table.add_column("Tier", style="cyan")
            storage_table.add_column("Size", justify="right", style="yellow")

            for tier in ["hot", "warm", "cold", "frozen", "unknown"]:
                if tier in tier_storage:
                    storage_table.add_row(tier.capitalize(), bytes_to_human(tier_storage[tier]))

            layout["right"].update(storage_table)
        except Exception as e:
            layout["right"].update(Panel(f"[red]Error fetching storage: {e}[/red]", box=box.ROUNDED))

        # Footer
        footer_text = Text(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Press Ctrl+C to exit",
                          style="dim", justify="center")
        layout["footer"].update(Panel(footer_text, box=box.ROUNDED))

        return layout

    console.print("\n[cyan]Starting real-time dashboard... Press Ctrl+C to exit.[/cyan]\n")
    time.sleep(1)

    try:
        with Live(generate_dashboard(), refresh_per_second=0.5, console=console) as live:
            while True:
                time.sleep(2)  # Update every 2 seconds
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Dashboard stopped.[/yellow]\n")


# ------------------------------------------------------------
# SUB-MENUS
# ------------------------------------------------------------



def option_cluster_health_overview(es):
    """Display cluster health overview."""
    show_breadcrumb(["Main Menu", "Cluster Health & Diagnostics", "Cluster Health Overview"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching cluster health..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        health = es.cluster.health()

    console.print()
    table = Table(title="Cluster Health", box=box.DOUBLE_EDGE, title_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    status = health.get("status", "unknown")
    status_color = {"green": "[green]", "yellow": "[yellow]", "red": "[red]"}.get(status, "")

    table.add_row("Cluster Name", health.get("cluster_name", "N/A"))
    table.add_row("Status", f"{status_color}{status}[/{status_color.strip('[')}]")
    table.add_row("Number of Nodes", str(health.get("number_of_nodes", 0)))
    table.add_row("Number of Data Nodes", str(health.get("number_of_data_nodes", 0)))
    table.add_row("Active Primary Shards", str(health.get("active_primary_shards", 0)))
    table.add_row("Active Shards", str(health.get("active_shards", 0)))
    table.add_row("Relocating Shards", str(health.get("relocating_shards", 0)))
    table.add_row("Initializing Shards", str(health.get("initializing_shards", 0)))
    table.add_row("Unassigned Shards", str(health.get("unassigned_shards", 0)))

    console.print(table)
    console.print()




def option_node_information(es):
    """Display node information."""
    show_breadcrumb(["Main Menu", "Cluster Health & Diagnostics", "Node Information"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching node information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        nodes = es.cat.nodes(format="json", h="name,ip,heap.percent,ram.percent,cpu,load_1m,node.role,master")

    console.print()
    table = Table(title="Cluster Nodes", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("IP", style="white")
    table.add_column("Heap %", justify="right")
    table.add_column("RAM %", justify="right")
    table.add_column("CPU", justify="right")
    table.add_column("Load", justify="right")
    table.add_column("Role", style="yellow")
    table.add_column("Master", justify="center")

    for node in nodes:
        table.add_row(
            node.get("name", ""),
            node.get("ip", ""),
            node.get("heap.percent", ""),
            node.get("ram.percent", ""),
            node.get("cpu", ""),
            node.get("load_1m", ""),
            node.get("node.role", ""),
            "✓" if node.get("master") == "*" else ""
        )

    console.print(table)
    console.print()




def option_cluster_stats(es):
    """Display cluster statistics."""
    show_breadcrumb(["Main Menu", "Cluster Health & Diagnostics", "Cluster Stats"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching cluster stats..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        stats = es.cluster.stats()

    console.print()

    # Indices stats
    indices_stats = stats.get("indices", {})
    table1 = Table(title="Indices Statistics", box=box.ROUNDED, title_style="bold cyan")
    table1.add_column("Metric", style="cyan")
    table1.add_column("Value", justify="right")

    table1.add_row("Total Indices", str(indices_stats.get("count", 0)))
    table1.add_row("Total Shards", str(indices_stats.get("shards", {}).get("total", 0)))
    table1.add_row("Total Documents", f"{indices_stats.get('docs', {}).get('count', 0):,}")

    store = indices_stats.get("store", {})
    if "size_in_bytes" in store:
        table1.add_row("Total Size", bytes_to_human(store["size_in_bytes"]))

    console.print(table1)
    console.print()


# ------------------------------------------------------------
# Menu
# ------------------------------------------------------------



