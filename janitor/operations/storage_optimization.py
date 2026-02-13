"""
Storage & Cost Optimization operations for Elastic Janitor.
Analyze storage usage, forecast growth, and estimate costs.
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, PROTECT_SYSTEM, MAX_DELETE_LIMIT, DRY_RUN_MODE
from ..utils import (
    safe_input, is_system, confirm_delete, show_breadcrumb,
    size_to_bytes, bytes_to_human, get_number_input
)


def option_storage_forecast(es):
    """Analyze historical index growth and predict future storage needs."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Storage Forecast"])
    
    # Get configurable time window
    console.print("[cyan]Analyzing historical index growth rates...[/cyan]\n")
    window_days = get_number_input("Historical analysis window in days (default: 30):", default=30)
    
    if window_days is None:
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,creation.date,store.size,docs.count")
    
    # Calculate current total storage and analyze growth
    total_bytes = 0
    indices_in_window = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=window_days)
    
    for r in rows:
        size_str = r.get("store.size", "0b")
        size_bytes = size_to_bytes(size_str)
        total_bytes += size_bytes
        
        creation_ms = r.get("creation.date")
        if creation_ms:
            from ..utils.formatters import parse_epoch_millis
            created = parse_epoch_millis(creation_ms)
            if created >= cutoff_date:
                indices_in_window.append({
                    "name": r.get("index"),
                    "created": created,
                    "size_bytes": size_bytes,
                    "docs": r.get("docs.count", "0")
                })
    
    # Calculate daily growth rate
    if indices_in_window:
        total_new_bytes = sum(idx["size_bytes"] for idx in indices_in_window)
        daily_growth = total_new_bytes / window_days if window_days > 0 else 0
    else:
        daily_growth = 0
    
    # Project future storage
    proj_30 = total_bytes + (daily_growth * 30)
    proj_60 = total_bytes + (daily_growth * 60)
    proj_90 = total_bytes + (daily_growth * 90)
    
    # Display results
    console.print()
    table = Table(title="Storage Forecast Analysis", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="yellow")
    
    table.add_row("Current Total Storage", bytes_to_human(total_bytes))
    table.add_row("Analysis Window", f"{window_days} days")
    table.add_row("New Indices in Window", str(len(indices_in_window)))
    table.add_row("Growth in Window", bytes_to_human(total_new_bytes) if indices_in_window else "0b")
    table.add_row("Daily Growth Rate", bytes_to_human(daily_growth))
    table.add_row("", "")
    table.add_row("Projected Storage (30 days)", bytes_to_human(proj_30))
    table.add_row("Projected Storage (60 days)", bytes_to_human(proj_60))
    table.add_row("Projected Storage (90 days)", bytes_to_human(proj_90))
    
    console.print(table)
    console.print()


def option_tier_distribution(es):
    """Display storage distribution across tiers (hot/warm/cold/frozen)."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Tier Distribution Report"])
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching tier distribution..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,store.size,docs.count,dt")
    
    # Aggregate by tier
    tier_stats = defaultdict(lambda: {"size_bytes": 0, "count": 0, "docs": 0})
    total_bytes = 0
    total_indices = 0
    total_docs = 0
    
    for r in rows:
        tier = r.get("dt", "unknown") or "unknown"
        size_str = r.get("store.size", "0b")
        size_bytes = size_to_bytes(size_str)
        docs = int(r.get("docs.count", "0") or 0)
        
        tier_stats[tier]["size_bytes"] += size_bytes
        tier_stats[tier]["count"] += 1
        tier_stats[tier]["docs"] += docs
        
        total_bytes += size_bytes
        total_indices += 1
        total_docs += docs
    
    # Display results
    console.print()
    table = Table(title="Storage Tier Distribution", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Tier", style="cyan")
    table.add_column("Storage", justify="right", style="yellow")
    table.add_column("% of Total", justify="right", style="green")
    table.add_column("Indices", justify="right", style="blue")
    table.add_column("Documents", justify="right", style="magenta")
    
    # Sort tiers: hot, warm, cold, frozen, then others
    tier_order = ["hot", "warm", "cold", "frozen"]
    sorted_tiers = sorted(tier_stats.keys(), key=lambda t: (tier_order.index(t) if t in tier_order else 999, t))
    
    for tier in sorted_tiers:
        stats = tier_stats[tier]
        size_pct = (stats["size_bytes"] / total_bytes * 100) if total_bytes > 0 else 0
        table.add_row(
            tier.upper(),
            bytes_to_human(stats["size_bytes"]),
            f"{size_pct:.1f}%",
            str(stats["count"]),
            f"{stats['docs']:,}"
        )
    
    table.add_row("", "", "", "", "")
    table.add_row(
        "TOTAL",
        bytes_to_human(total_bytes),
        "100.0%",
        str(total_indices),
        f"{total_docs:,}"
    )
    
    console.print(table)
    console.print()


def option_compression_analysis(es):
    """Identify indices that would benefit from compression."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Compression Analysis"])

    console.print("[cyan]Analyzing index compression settings...[/cyan]\n")
    threshold_gb = get_number_input("Flag indices larger than (GB, default: 10):", default=10)

    if threshold_gb is None:
        return

    threshold_bytes = threshold_gb * (1024 ** 3)

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index settings and sizes..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,store.size,docs.count")

    # Get settings for all indices
    candidates = []

    for r in rows:
        index_name = r.get("index")
        if is_system(index_name):
            continue

        size_str = r.get("store.size", "0b")
        size_bytes = size_to_bytes(size_str)

        if size_bytes >= threshold_bytes:
            try:
                settings = es.indices.get_settings(index=index_name)
                codec = settings[index_name]["settings"]["index"].get("codec", "default")

                # Flag indices using default codec
                if codec == "default":
                    # Estimate 20-30% compression savings with best_compression
                    potential_savings = size_bytes * 0.25
                    candidates.append({
                        "name": index_name,
                        "size_bytes": size_bytes,
                        "size": size_str,
                        "docs": r.get("docs.count", "0"),
                        "codec": codec,
                        "savings_bytes": potential_savings
                    })
            except Exception as e:
                console.print(f"[yellow]Warning: Could not get settings for {index_name}: {e}[/yellow]")

    # Display results
    if not candidates:
        console.print("[green]✅ No indices found that would benefit from compression.[/green]\n")
        return

    console.print()
    table = Table(
        title=f"Indices Using Default Codec (>{threshold_gb}GB)",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    table.add_column("Index Name", style="cyan", no_wrap=False)
    table.add_column("Size", justify="right", style="yellow")
    table.add_column("Documents", justify="right", style="blue")
    table.add_column("Codec", justify="right", style="magenta")
    table.add_column("Est. Savings", justify="right", style="green")

    total_savings = 0
    for c in sorted(candidates, key=lambda x: x["size_bytes"], reverse=True):
        table.add_row(
            c["name"],
            c["size"],
            c["docs"],
            c["codec"],
            bytes_to_human(c["savings_bytes"])
        )
        total_savings += c["savings_bytes"]

    console.print(table)
    console.print(f"\n[green]💡 Total potential savings: {bytes_to_human(total_savings)}[/green]")
    console.print("[dim]Tip: Use 'best_compression' codec for better compression at the cost of indexing speed.[/dim]\n")


def option_empty_index_cleanup(es):
    """Find and optionally delete indices with zero documents."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Empty Index Cleanup"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Scanning for empty indices..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,creation.date,store.size,docs.count")

    # Find empty indices
    empty_indices = []

    for r in rows:
        index_name = r.get("index")
        if is_system(index_name):
            continue

        docs = int(r.get("docs.count", "0") or 0)
        if docs == 0:
            creation_ms = r.get("creation.date")
            created = None
            if creation_ms:
                from ..utils.formatters import parse_epoch_millis
                created = parse_epoch_millis(creation_ms)

            empty_indices.append({
                "name": index_name,
                "created": created,
                "size": r.get("store.size", "0b")
            })

    if not empty_indices:
        console.print("\n[green]✅ No empty indices found.[/green]\n")
        return

    # Display results
    console.print()
    table = Table(title=f"Empty Indices ({len(empty_indices)} found)", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Index Name", style="cyan", no_wrap=False)
    table.add_column("Created", style="yellow")
    table.add_column("Size", justify="right", style="blue")

    for idx in sorted(empty_indices, key=lambda x: x["created"] if x["created"] else datetime.min.replace(tzinfo=timezone.utc)):
        created_str = idx["created"].strftime("%Y-%m-%d %H:%M") if idx["created"] else "Unknown"
        table.add_row(idx["name"], created_str, idx["size"])

    console.print(table)
    console.print()

    # Ask if user wants to delete
    if not confirm_delete():
        console.print("[yellow]Cancelled.[/yellow]\n")
        return

    # Respect MAX_DELETE_LIMIT
    if len(empty_indices) > MAX_DELETE_LIMIT:
        console.print(f"[red]❌ Cannot delete {len(empty_indices)} indices. MAX_DELETE_LIMIT is {MAX_DELETE_LIMIT}.[/red]\n")
        return

    # Delete indices
    deleted = 0
    failed = 0

    console.print()
    for idx in empty_indices:
        index_name = idx["name"]
        try:
            if DRY_RUN_MODE:
                console.print(f"[dim][DRY-RUN] Would delete: {index_name}[/dim]")
            else:
                es.indices.delete(index=index_name)
                console.print(f"[green]✓ Deleted: {index_name}[/green]")
            deleted += 1
        except Exception as e:
            console.print(f"[red]✗ Failed to delete {index_name}: {e}[/red]")
            failed += 1

    console.print()
    if DRY_RUN_MODE:
        console.print(f"[cyan][DRY-RUN] Would delete {deleted} empty indices.[/cyan]\n")
    else:
        console.print(f"[green]✅ Deleted {deleted} empty indices.[/green]")
        if failed > 0:
            console.print(f"[yellow]⚠️  Failed to delete {failed} indices.[/yellow]")
        console.print()


def option_sparse_index_detector(es):
    """Identify indices with very low document density (docs per GB)."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Sparse Index Detector"])

    console.print("[cyan]Analyzing document density...[/cyan]\n")
    threshold = get_number_input("Flag indices below docs/GB threshold (default: 10000):", default=10000)

    if threshold is None:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,store.size,docs.count")

    # Calculate density for each index
    sparse_indices = []

    for r in rows:
        index_name = r.get("index")
        if is_system(index_name):
            continue

        size_str = r.get("store.size", "0b")
        size_bytes = size_to_bytes(size_str)
        docs = int(r.get("docs.count", "0") or 0)

        # Skip very small indices (less than 100MB)
        if size_bytes < 100 * 1024 * 1024:
            continue

        # Calculate docs per GB
        size_gb = size_bytes / (1024 ** 3)
        if size_gb > 0:
            docs_per_gb = docs / size_gb

            if docs_per_gb < threshold:
                sparse_indices.append({
                    "name": index_name,
                    "size_bytes": size_bytes,
                    "size": size_str,
                    "docs": docs,
                    "docs_per_gb": docs_per_gb
                })

    if not sparse_indices:
        console.print(f"\n[green]✅ No sparse indices found below {threshold} docs/GB.[/green]\n")
        return

    # Sort by sparseness (lowest docs/GB first)
    sparse_indices.sort(key=lambda x: x["docs_per_gb"])

    # Display results
    console.print()
    table = Table(
        title=f"Sparse Indices (<{threshold} docs/GB)",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    table.add_column("Index Name", style="cyan", no_wrap=False)
    table.add_column("Size", justify="right", style="yellow")
    table.add_column("Documents", justify="right", style="blue")
    table.add_column("Docs/GB", justify="right", style="magenta")

    for idx in sparse_indices:
        table.add_row(
            idx["name"],
            idx["size"],
            f"{idx['docs']:,}",
            f"{idx['docs_per_gb']:,.0f}"
        )

    console.print(table)
    console.print(f"\n[yellow]💡 Found {len(sparse_indices)} sparse indices.[/yellow]")
    console.print("[dim]Tip: Sparse indices may indicate inefficient mappings or excessive metadata.[/dim]\n")


def option_cost_estimator(es):
    """Estimate monthly storage costs based on tier pricing."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Cost Estimator"])

    console.print("[cyan]Configure storage tier pricing (per GB/month):[/cyan]\n")

    # Get pricing for each tier
    pricing = {}
    pricing["hot"] = get_number_input("Hot tier price ($/GB/month, default: 0.125):", default=0.125)
    if pricing["hot"] is None:
        return

    pricing["warm"] = get_number_input("Warm tier price ($/GB/month, default: 0.045):", default=0.045)
    if pricing["warm"] is None:
        return

    pricing["cold"] = get_number_input("Cold tier price ($/GB/month, default: 0.015):", default=0.015)
    if pricing["cold"] is None:
        return

    pricing["frozen"] = get_number_input("Frozen tier price ($/GB/month, default: 0.005):", default=0.005)
    if pricing["frozen"] is None:
        return

    pricing["unknown"] = get_number_input("Unknown tier price ($/GB/month, default: 0.125):", default=0.125)
    if pricing["unknown"] is None:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Calculating costs..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,store.size,dt")

    # Aggregate by tier
    tier_costs = defaultdict(lambda: {"size_gb": 0, "cost": 0})
    total_cost = 0

    for r in rows:
        tier = r.get("dt", "unknown") or "unknown"
        size_str = r.get("store.size", "0b")
        size_bytes = size_to_bytes(size_str)
        size_gb = size_bytes / (1024 ** 3)

        price_per_gb = pricing.get(tier, pricing["unknown"])
        cost = size_gb * price_per_gb

        tier_costs[tier]["size_gb"] += size_gb
        tier_costs[tier]["cost"] += cost
        total_cost += cost

    # Display results
    console.print()
    table = Table(title="Monthly Storage Cost Estimate", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Tier", style="cyan")
    table.add_column("Storage (GB)", justify="right", style="yellow")
    table.add_column("Price/GB", justify="right", style="blue")
    table.add_column("Monthly Cost", justify="right", style="green")

    # Sort tiers
    tier_order = ["hot", "warm", "cold", "frozen"]
    sorted_tiers = sorted(tier_costs.keys(), key=lambda t: (tier_order.index(t) if t in tier_order else 999, t))

    for tier in sorted_tiers:
        stats = tier_costs[tier]
        price = pricing.get(tier, pricing["unknown"])
        table.add_row(
            tier.upper(),
            f"{stats['size_gb']:.2f}",
            f"${price:.3f}",
            f"${stats['cost']:.2f}"
        )

    table.add_row("", "", "", "")
    table.add_row(
        "TOTAL",
        f"{sum(t['size_gb'] for t in tier_costs.values()):.2f}",
        "",
        f"${total_cost:.2f}"
    )

    console.print(table)
    console.print(f"\n[green]💰 Estimated monthly storage cost: ${total_cost:.2f}[/green]\n")

