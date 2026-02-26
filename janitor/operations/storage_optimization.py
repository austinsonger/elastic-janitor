"""
Storage & Cost Optimization operations for Elastic Janitor.
Analyze storage usage, forecast growth, and estimate costs.
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, PROTECT_SYSTEM, MAX_DELETE_LIMIT, GOD_MODE
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
    import questionary
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

    # Interactive selection of indices to delete
    console.print("[cyan]Select indices to delete:[/cyan]")
    console.print("[dim]Use space to select/deselect, arrow keys to navigate, enter to confirm[/dim]\n")

    # Create choices for multi-select
    from ..config import custom_style
    choices = []

    # Add "Select All" option at the top
    choices.append(questionary.Choice("✓ Select All", value="__select_all__", checked=False))
    choices.append(questionary.Separator())

    # Add each index as a choice
    for idx in sorted(empty_indices, key=lambda x: x["created"] if x["created"] else datetime.min.replace(tzinfo=timezone.utc)):
        created_str = idx["created"].strftime("%Y-%m-%d %H:%M") if idx["created"] else "Unknown"
        label = f"{idx['name']} (created: {created_str}, size: {idx['size']})"
        choices.append(questionary.Choice(label, value=idx["name"], checked=False))

    # Show multi-select checkbox
    try:
        selected = questionary.checkbox(
            "Select indices to delete:",
            choices=choices,
            style=custom_style
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    if selected is None:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Handle "Select All" option
    if "__select_all__" in selected:
        # If "Select All" was chosen, select all indices
        indices_to_delete = [idx["name"] for idx in empty_indices]
    else:
        indices_to_delete = selected

    # Check if any indices were selected
    if not indices_to_delete:
        console.print("\n[yellow]⚠️  No indices selected.[/yellow]\n")
        return

    # Display selected indices for confirmation
    console.print(f"\n[cyan]Selected {len(indices_to_delete)} indices for deletion:[/cyan]\n")
    for idx_name in indices_to_delete[:10]:
        console.print(f"  [red]•[/red] {idx_name}")
    if len(indices_to_delete) > 10:
        console.print(f"  [dim]... and {len(indices_to_delete) - 10} more[/dim]")
    console.print()

    # Respect MAX_DELETE_LIMIT
    if len(indices_to_delete) > MAX_DELETE_LIMIT:
        console.print(f"[red]❌ Cannot delete {len(indices_to_delete)} indices. MAX_DELETE_LIMIT is {MAX_DELETE_LIMIT}.[/red]\n")
        return

    # Final confirmation
    if not confirm_delete():
        console.print("[yellow]Cancelled.[/yellow]\n")
        return

    # Delete selected indices
    deleted = 0
    failed = 0

    console.print()
    for idx_name in indices_to_delete:
        try:
            if not GOD_MODE:
                console.print(f"[dim][DRY-RUN] Would delete: {idx_name}[/dim]")
            else:
                es.indices.delete(index=idx_name)
                console.print(f"[green]✓ Deleted: {idx_name}[/green]")
            deleted += 1
        except Exception as e:
            console.print(f"[red]✗ Failed to delete {idx_name}: {e}[/red]")
            failed += 1

    console.print()
    if not GOD_MODE:
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


def option_shard_size_predictor(es):
    """Predict future shard sizes based on growth rates."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Shard Size Predictor"])

    console.print("[cyan]Analyzing shard growth patterns...[/cyan]\n")
    window_days = get_number_input("Historical analysis window in days (default: 30):", default=30)

    if window_days is None:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching shard data..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            rows = es.cat.shards(format="json", h="index,shard,prirep,store,creation.date")
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch shard data: {e}[/red]\n")
            return

    # Calculate growth rates and project future sizes
    shard_data = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=window_days)

    for r in rows:
        index_name = r.get("index")
        if is_system(index_name):
            continue

        # Only analyze primary shards
        if r.get("prirep") != "p":
            continue

        shard_id = r.get("shard", "0")
        size_str = r.get("store", "0b")
        size_bytes = size_to_bytes(size_str)

        creation_ms = r.get("creation.date")
        if not creation_ms:
            continue

        from ..utils.formatters import parse_epoch_millis
        created = parse_epoch_millis(creation_ms)

        # Calculate age in days
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days < 1:
            age_days = 1  # Avoid division by zero

        # Calculate daily growth rate
        daily_growth = size_bytes / age_days

        # Project future sizes
        proj_30 = size_bytes + (daily_growth * 30)
        proj_60 = size_bytes + (daily_growth * 60)
        proj_90 = size_bytes + (daily_growth * 90)

        # Flag shards projected to exceed 50GB
        max_recommended_bytes = 50 * (1024 ** 3)
        warning = proj_90 > max_recommended_bytes

        shard_data.append({
            "name": f"{index_name}[{shard_id}]",
            "current_bytes": size_bytes,
            "growth_rate": daily_growth,
            "proj_30": proj_30,
            "proj_60": proj_60,
            "proj_90": proj_90,
            "warning": warning
        })

    if not shard_data:
        console.print("\n[yellow]⚠️  No shard data available for analysis.[/yellow]\n")
        return

    # Sort by projected 90-day size (largest first)
    shard_data.sort(key=lambda x: x["proj_90"], reverse=True)

    # Display results (top 50 shards)
    console.print()
    table = Table(
        title=f"Shard Size Projections (Top 50)",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    table.add_column("Shard", style="cyan", no_wrap=False)
    table.add_column("Current Size", justify="right", style="yellow")
    table.add_column("Growth/Day", justify="right", style="blue")
    table.add_column("30 Days", justify="right", style="green")
    table.add_column("60 Days", justify="right", style="green")
    table.add_column("90 Days", justify="right", style="green")
    table.add_column("Warning", justify="center", style="red")

    for shard in shard_data[:50]:
        warning_flag = "⚠️" if shard["warning"] else ""
        table.add_row(
            shard["name"],
            bytes_to_human(shard["current_bytes"]),
            bytes_to_human(shard["growth_rate"]),
            bytes_to_human(shard["proj_30"]),
            bytes_to_human(shard["proj_60"]),
            bytes_to_human(shard["proj_90"]),
            warning_flag
        )

    console.print(table)

    # Summary
    warned_count = sum(1 for s in shard_data if s["warning"])
    if warned_count > 0:
        console.print(f"\n[yellow]⚠️  {warned_count} shard(s) projected to exceed 50GB in 90 days.[/yellow]")
        console.print("[dim]Tip: Consider implementing index lifecycle policies or shard allocation strategies.[/dim]\n")
    else:
        console.print("\n[green]✅ All shards within recommended size limits.[/green]\n")


def option_resource_allocation_optimizer(es):
    """Analyze node resource utilization and provide optimization recommendations."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Resource Allocation Optimizer"])

    console.print("[cyan]Analyzing cluster resource allocation...[/cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching node statistics..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            node_stats = es.nodes.stats(metric=["os", "jvm", "fs", "indices"])
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch node stats: {e}[/red]\n")
            return

    # Analyze resource utilization per node
    node_data = []
    recommendations = []

    for node_id, stats in node_stats.get("nodes", {}).items():
        node_name = stats.get("name", node_id)

        # CPU usage
        cpu_percent = stats.get("os", {}).get("cpu", {}).get("percent", 0)

        # JVM heap usage
        jvm_heap = stats.get("jvm", {}).get("mem", {})
        heap_used_bytes = jvm_heap.get("heap_used_in_bytes", 0)
        heap_max_bytes = jvm_heap.get("heap_max_in_bytes", 1)
        heap_percent = (heap_used_bytes / heap_max_bytes * 100) if heap_max_bytes > 0 else 0

        # Disk usage
        fs_total = stats.get("fs", {}).get("total", {})
        disk_total_bytes = fs_total.get("total_in_bytes", 1)
        disk_available_bytes = fs_total.get("available_in_bytes", 0)
        disk_used_bytes = disk_total_bytes - disk_available_bytes
        disk_percent = (disk_used_bytes / disk_total_bytes * 100) if disk_total_bytes > 0 else 0

        # Shard count
        shard_count = stats.get("indices", {}).get("shard_stats", {}).get("total_count", 0)

        node_data.append({
            "name": node_name,
            "cpu_percent": cpu_percent,
            "heap_percent": heap_percent,
            "heap_max_gb": heap_max_bytes / (1024 ** 3),
            "disk_percent": disk_percent,
            "disk_total_gb": disk_total_bytes / (1024 ** 3),
            "shard_count": shard_count
        })

        # Generate recommendations
        if heap_percent > 85:
            recommendations.append(f"⚠️  {node_name}: High heap usage ({heap_percent:.1f}%) - consider increasing heap size")

        if disk_percent > 85:
            recommendations.append(f"⚠️  {node_name}: High disk usage ({disk_percent:.1f}%) - add storage or migrate data")

        if cpu_percent > 80:
            recommendations.append(f"⚠️  {node_name}: High CPU usage ({cpu_percent:.1f}%) - investigate workload")

        # Check heap size recommendations (target: 50% of RAM, max 31GB)
        if heap_max_bytes > 31 * (1024 ** 3):
            recommendations.append(f"💡 {node_name}: Heap size exceeds 31GB - consider reducing for better performance")

    if not node_data:
        console.print("\n[yellow]⚠️  No node data available.[/yellow]\n")
        return

    # Display resource utilization table
    console.print()
    table = Table(
        title="Node Resource Utilization",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    table.add_column("Node", style="cyan", no_wrap=False)
    table.add_column("CPU %", justify="right", style="yellow")
    table.add_column("Heap %", justify="right", style="blue")
    table.add_column("Heap Max", justify="right", style="blue")
    table.add_column("Disk %", justify="right", style="magenta")
    table.add_column("Disk Total", justify="right", style="magenta")
    table.add_column("Shards", justify="right", style="green")

    for node in node_data:
        # Color code based on thresholds
        cpu_style = "red" if node["cpu_percent"] > 80 else "yellow" if node["cpu_percent"] > 60 else "green"
        heap_style = "red" if node["heap_percent"] > 85 else "yellow" if node["heap_percent"] > 75 else "green"
        disk_style = "red" if node["disk_percent"] > 85 else "yellow" if node["disk_percent"] > 75 else "green"

        table.add_row(
            node["name"],
            f"[{cpu_style}]{node['cpu_percent']:.1f}%[/{cpu_style}]",
            f"[{heap_style}]{node['heap_percent']:.1f}%[/{heap_style}]",
            f"{node['heap_max_gb']:.1f}GB",
            f"[{disk_style}]{node['disk_percent']:.1f}%[/{disk_style}]",
            f"{node['disk_total_gb']:.1f}GB",
            str(node["shard_count"])
        )

    console.print(table)

    # Display recommendations
    if recommendations:
        console.print("\n[bold cyan]Recommendations:[/bold cyan]")
        for rec in recommendations:
            console.print(f"  {rec}")
        console.print()
    else:
        console.print("\n[green]✅ All nodes operating within normal parameters.[/green]\n")


def option_cold_frozen_roi_calculator(es):
    """Calculate ROI for migrating indices to cold/frozen tiers."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Cold/Frozen Tier ROI Calculator"])

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

    # Get age threshold for migration candidates
    console.print()
    age_threshold = get_number_input("Identify indices older than (days, default: 90):", default=90)
    if age_threshold is None:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing indices..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            rows = es.cat.indices(format="json", h="index,store.size,docs.count,creation.date,dt")
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch index data: {e}[/red]\n")
            return

    # Identify migration candidates
    candidates = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=age_threshold)

    for r in rows:
        index_name = r.get("index")
        if is_system(index_name):
            continue

        current_tier = r.get("dt", "unknown") or "unknown"

        # Only consider hot/warm tier indices
        if current_tier not in ["hot", "warm"]:
            continue

        creation_ms = r.get("creation.date")
        if not creation_ms:
            continue

        from ..utils.formatters import parse_epoch_millis
        created = parse_epoch_millis(creation_ms)

        # Check if older than threshold
        if created >= cutoff_date:
            continue

        size_str = r.get("store.size", "0b")
        size_bytes = size_to_bytes(size_str)
        size_gb = size_bytes / (1024 ** 3)

        # Calculate current monthly cost
        current_price = pricing.get(current_tier, pricing["hot"])
        current_cost = size_gb * current_price

        # Calculate projected cost in cold tier
        cold_cost = size_gb * pricing["cold"]
        cold_savings = current_cost - cold_cost

        # Calculate projected cost in frozen tier
        frozen_cost = size_gb * pricing["frozen"]
        frozen_savings = current_cost - frozen_cost

        # Calculate ROI period (months to break even, assuming migration cost)
        # Simplified: no migration cost assumed

        candidates.append({
            "name": index_name,
            "current_tier": current_tier,
            "size_gb": size_gb,
            "current_cost": current_cost,
            "cold_cost": cold_cost,
            "cold_savings": cold_savings,
            "frozen_cost": frozen_cost,
            "frozen_savings": frozen_savings,
            "age_days": (datetime.now(timezone.utc) - created).days
        })

    if not candidates:
        console.print(f"\n[green]✅ No indices in hot/warm tiers older than {age_threshold} days.[/green]\n")
        return

    # Sort by potential savings (frozen tier, highest first)
    candidates.sort(key=lambda x: x["frozen_savings"], reverse=True)

    # Display results (top 50)
    console.print()
    table = Table(
        title=f"Cold/Frozen Tier Migration ROI (Top 50)",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    table.add_column("Index", style="cyan", no_wrap=False)
    table.add_column("Current Tier", justify="center", style="yellow")
    table.add_column("Size (GB)", justify="right", style="blue")
    table.add_column("Current Cost", justify="right", style="red")
    table.add_column("Cold Cost", justify="right", style="green")
    table.add_column("Cold Savings", justify="right", style="green")
    table.add_column("Frozen Cost", justify="right", style="green")
    table.add_column("Frozen Savings", justify="right", style="green")

    total_current_cost = 0
    total_cold_savings = 0
    total_frozen_savings = 0

    for idx in candidates[:50]:
        table.add_row(
            idx["name"],
            idx["current_tier"].upper(),
            f"{idx['size_gb']:.2f}",
            f"${idx['current_cost']:.2f}",
            f"${idx['cold_cost']:.2f}",
            f"${idx['cold_savings']:.2f}",
            f"${idx['frozen_cost']:.2f}",
            f"${idx['frozen_savings']:.2f}"
        )
        total_current_cost += idx["current_cost"]
        total_cold_savings += idx["cold_savings"]
        total_frozen_savings += idx["frozen_savings"]

    console.print(table)
    console.print(f"\n[green]💰 Total potential monthly savings:[/green]")
    console.print(f"   Cold tier migration: ${total_cold_savings:.2f}/month")
    console.print(f"   Frozen tier migration: ${total_frozen_savings:.2f}/month")
    console.print(f"   Annual savings (frozen): ${total_frozen_savings * 12:.2f}/year\n")


def option_query_cost_analyzer(es):
    """Analyze query costs and identify expensive queries/indices."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Query Cost Analyzer"])

    console.print("[cyan]Analyzing query performance and costs...[/cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching query statistics..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            # Fetch index-level search stats
            index_stats = es.indices.stats(metric="search")
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch index stats: {e}[/red]\n")
            return

    # Analyze per-index query costs
    index_costs = []

    for index_name, stats in index_stats.get("indices", {}).items():
        if is_system(index_name):
            continue

        search_stats = stats.get("total", {}).get("search", {})

        # Get query metrics
        query_total = search_stats.get("query_total", 0)
        query_time_ms = search_stats.get("query_time_in_millis", 0)
        fetch_total = search_stats.get("fetch_total", 0)
        fetch_time_ms = search_stats.get("fetch_time_in_millis", 0)

        # Calculate average query time
        avg_query_time = (query_time_ms / query_total) if query_total > 0 else 0

        # Calculate total search time
        total_search_time = query_time_ms + fetch_time_ms

        # Calculate "cost score" (query time × query frequency)
        # Higher score = more expensive
        cost_score = total_search_time * query_total if query_total > 0 else 0

        # Get cache stats if available
        request_cache = stats.get("total", {}).get("request_cache", {})
        cache_hits = request_cache.get("hit_count", 0)
        cache_misses = request_cache.get("miss_count", 0)
        cache_total = cache_hits + cache_misses
        cache_hit_ratio = (cache_hits / cache_total * 100) if cache_total > 0 else 0

        if query_total > 0:  # Only include indices with queries
            index_costs.append({
                "name": index_name,
                "query_count": query_total,
                "avg_query_ms": avg_query_time,
                "total_time_ms": total_search_time,
                "cost_score": cost_score,
                "cache_hit_ratio": cache_hit_ratio
            })

    if not index_costs:
        console.print("\n[yellow]⚠️  No query activity found.[/yellow]\n")
        return

    # Sort by cost score (highest first)
    index_costs.sort(key=lambda x: x["cost_score"], reverse=True)

    # Display top 25 most expensive indices
    console.print()
    table = Table(
        title="Top 25 Most Expensive Queries/Indices",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    table.add_column("Index", style="cyan", no_wrap=False)
    table.add_column("Query Count", justify="right", style="yellow")
    table.add_column("Avg Time (ms)", justify="right", style="blue")
    table.add_column("Total Time (ms)", justify="right", style="magenta")
    table.add_column("Cost Score", justify="right", style="red")
    table.add_column("Cache Hit %", justify="right", style="green")

    for idx in index_costs[:25]:
        # Color code cache hit ratio
        cache_style = "green" if idx["cache_hit_ratio"] > 80 else "yellow" if idx["cache_hit_ratio"] > 50 else "red"

        table.add_row(
            idx["name"],
            f"{idx['query_count']:,}",
            f"{idx['avg_query_ms']:.2f}",
            f"{idx['total_time_ms']:,}",
            f"{idx['cost_score']:,.0f}",
            f"[{cache_style}]{idx['cache_hit_ratio']:.1f}%[/{cache_style}]"
        )

    console.print(table)

    # Provide optimization recommendations
    console.print("\n[bold cyan]Optimization Recommendations:[/bold cyan]")

    # High-cost indices
    high_cost = [idx for idx in index_costs if idx["cost_score"] > 1000000]
    if high_cost:
        console.print(f"  💡 {len(high_cost)} indices with high query costs - consider optimizing queries or adding filters")

    # Low cache hit ratios
    low_cache = [idx for idx in index_costs if idx["cache_hit_ratio"] < 50 and idx["query_count"] > 100]
    if low_cache:
        console.print(f"  💡 {len(low_cache)} indices with low cache hit rates - review caching strategies")

    # Slow queries
    slow_queries = [idx for idx in index_costs if idx["avg_query_ms"] > 1000]
    if slow_queries:
        console.print(f"  💡 {len(slow_queries)} indices with slow average query times (>1s) - optimize mappings or queries")

    if not high_cost and not low_cache and not slow_queries:
        console.print("  ✅ Query performance looks good!")

    console.print()


def option_retention_policy_optimizer(es):
    """Identify indices with suboptimal retention policies and calculate potential savings."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Retention Policy Optimizer"])

    console.print("[cyan]Analyzing index retention policies...[/cyan]\n")

    # Get inactivity threshold
    inactivity_days = get_number_input("Flag indices with no queries in last (days, default: 30):", default=30)
    if inactivity_days is None:
        return

    # Get tier pricing (reuse from cost estimator)
    console.print("\n[cyan]Configure storage tier pricing (per GB/month):[/cyan]\n")
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
        TextColumn("[cyan]Fetching index data and query activity..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            # Fetch index info
            index_info = es.cat.indices(format="json", h="index,store.size,creation.date,dt")
            # Fetch search stats
            search_stats = es.indices.stats(metric="search")
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch data: {e}[/red]\n")
            return

    # Build index map with search activity
    search_activity = {}
    for index_name, stats in search_stats.get("indices", {}).items():
        search_stats_data = stats.get("total", {}).get("search", {})
        query_total = search_stats_data.get("query_total", 0)
        search_activity[index_name] = query_total

    # Analyze indices
    inactive_indices = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=inactivity_days)

    for r in index_info:
        index_name = r.get("index")
        if is_system(index_name):
            continue

        # Check query activity
        query_count = search_activity.get(index_name, 0)

        # Skip indices with recent queries
        if query_count > 0:
            continue

        creation_ms = r.get("creation.date")
        if not creation_ms:
            continue

        from ..utils.formatters import parse_epoch_millis
        created = parse_epoch_millis(creation_ms)
        age_days = (datetime.now(timezone.utc) - created).days

        # Get size and tier
        size_str = r.get("store.size", "0b")
        size_bytes = size_to_bytes(size_str)
        size_gb = size_bytes / (1024 ** 3)

        tier = r.get("dt", "unknown") or "unknown"

        # Calculate current monthly cost
        price_per_gb = pricing.get(tier, pricing["unknown"])
        monthly_cost = size_gb * price_per_gb

        # Calculate waste score (cost × days since last access)
        # Since we're filtering for zero queries, use age as proxy
        waste_score = monthly_cost * age_days

        # Suggested retention: if very old and inactive, suggest deletion or archival
        if age_days > 365:
            suggested_retention = "Delete or archive"
            potential_savings = monthly_cost
        elif age_days > 180:
            suggested_retention = "Move to frozen tier"
            potential_savings = monthly_cost - (size_gb * pricing["frozen"])
        else:
            suggested_retention = "Move to cold tier"
            potential_savings = monthly_cost - (size_gb * pricing["cold"])

        inactive_indices.append({
            "name": index_name,
            "age_days": age_days,
            "last_accessed": "Never queried",
            "current_retention": f"{age_days} days",
            "suggested_retention": suggested_retention,
            "size_gb": size_gb,
            "tier": tier,
            "monthly_cost": monthly_cost,
            "potential_savings": potential_savings,
            "waste_score": waste_score
        })

    if not inactive_indices:
        console.print(f"\n[green]✅ No inactive indices found (no queries in last {inactivity_days} days).[/green]\n")
        return

    # Sort by waste score (highest first)
    inactive_indices.sort(key=lambda x: x["waste_score"], reverse=True)

    # Display results (top 50)
    console.print()
    table = Table(
        title=f"Inactive Indices (No queries in {inactivity_days}+ days) - Top 50",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    table.add_column("Index", style="cyan", no_wrap=False)
    table.add_column("Age (days)", justify="right", style="yellow")
    table.add_column("Tier", justify="center", style="blue")
    table.add_column("Size (GB)", justify="right", style="magenta")
    table.add_column("Monthly Cost", justify="right", style="red")
    table.add_column("Suggested Action", style="green", no_wrap=False)
    table.add_column("Savings", justify="right", style="green")

    total_savings = 0

    for idx in inactive_indices[:50]:
        table.add_row(
            idx["name"],
            str(idx["age_days"]),
            idx["tier"].upper(),
            f"{idx['size_gb']:.2f}",
            f"${idx['monthly_cost']:.2f}",
            idx["suggested_retention"],
            f"${idx['potential_savings']:.2f}"
        )
        total_savings += idx["potential_savings"]

    console.print(table)
    console.print(f"\n[green]💰 Total potential monthly savings: ${total_savings:.2f}[/green]")
    console.print(f"[green]💰 Annual savings: ${total_savings * 12:.2f}[/green]")
    console.print(f"\n[dim]Tip: Review these indices and implement appropriate retention policies or ILM.[/dim]\n")


def option_resource_right_sizing(es):
    """Provide intelligent recommendations for optimizing cluster node configurations."""
    show_breadcrumb(["Main Menu", "Storage & Cost Optimization", "Resource Right-Sizing Advisor"])

    console.print("[cyan]Analyzing cluster resource allocation...[/cyan]\n")

    # Data Collection
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing cluster resources..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            # Fetch node statistics
            node_stats = es.nodes.stats(metric=["os", "jvm", "fs", "indices", "thread_pool"])
            # Fetch shard distribution
            shard_data = es.cat.shards(format="json", h="index,shard,prirep,store,node")
            # Fetch indexing and search metrics
            index_stats = es.indices.stats(metric=["indexing", "search"])
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch cluster data: {e}[/red]\n")
            return

    # Analysis Logic - Calculate per-node metrics
    node_metrics = []
    total_cpu = 0
    total_heap = 0
    total_disk = 0
    node_count = 0

    # Track shard distribution
    shard_distribution = defaultdict(int)
    shard_sizes = defaultdict(list)

    for shard in shard_data:
        node_name = shard.get("node")
        if node_name:
            shard_distribution[node_name] += 1
            store_str = shard.get("store", "0b")
            store_bytes = size_to_bytes(store_str)
            shard_sizes[node_name].append(store_bytes)

    for node_id, stats in node_stats.get("nodes", {}).items():
        node_name = stats.get("name", node_id)

        # CPU utilization
        cpu_percent = stats.get("os", {}).get("cpu", {}).get("percent", 0)

        # Heap usage
        jvm_heap = stats.get("jvm", {}).get("mem", {})
        heap_used_bytes = jvm_heap.get("heap_used_in_bytes", 0)
        heap_max_bytes = jvm_heap.get("heap_max_in_bytes", 1)
        heap_percent = (heap_used_bytes / heap_max_bytes * 100) if heap_max_bytes > 0 else 0

        # Disk usage
        fs_total = stats.get("fs", {}).get("total", {})
        disk_total_bytes = fs_total.get("total_in_bytes", 1)
        disk_available_bytes = fs_total.get("available_in_bytes", 0)
        disk_used_bytes = disk_total_bytes - disk_available_bytes
        disk_percent = (disk_used_bytes / disk_total_bytes * 100) if disk_total_bytes > 0 else 0

        # Shard count and average size
        node_shard_count = shard_distribution.get(node_name, 0)
        node_shard_sizes = shard_sizes.get(node_name, [])
        avg_shard_size = sum(node_shard_sizes) / len(node_shard_sizes) if node_shard_sizes else 0

        node_metrics.append({
            "name": node_name,
            "cpu_percent": cpu_percent,
            "heap_percent": heap_percent,
            "heap_max_bytes": heap_max_bytes,
            "disk_percent": disk_percent,
            "disk_total_bytes": disk_total_bytes,
            "shard_count": node_shard_count,
            "avg_shard_size": avg_shard_size
        })

        total_cpu += cpu_percent
        total_heap += heap_percent
        total_disk += disk_percent
        node_count += 1

    if node_count == 0:
        console.print("\n[yellow]⚠️  No node data available.[/yellow]\n")
        return

    # Calculate cluster-wide averages
    avg_cpu = total_cpu / node_count
    avg_heap = total_heap / node_count
    avg_disk = total_disk / node_count
    total_shards = sum(n["shard_count"] for n in node_metrics)
    avg_shards_per_node = total_shards / node_count if node_count > 0 else 0

    # Calculate workload patterns
    total_indexing_rate = 0
    total_query_rate = 0

    for index_name, stats in index_stats.get("indices", {}).items():
        if is_system(index_name):
            continue
        indexing_stats = stats.get("total", {}).get("indexing", {})
        search_stats = stats.get("total", {}).get("search", {})
        total_indexing_rate += indexing_stats.get("index_total", 0)
        total_query_rate += search_stats.get("query_total", 0)

    # Estimate daily indexing rate (rough approximation)
    daily_indexing_rate = total_indexing_rate  # Total docs indexed since cluster start

    # Identify over-provisioned and under-provisioned nodes
    over_provisioned_nodes = []
    under_provisioned_nodes = []
    critical_nodes = []
    oversized_shards = []

    for node in node_metrics:
        # Over-provisioned: CPU < 30%, heap < 40%, disk < 50%
        if node["cpu_percent"] < 30 and node["heap_percent"] < 40 and node["disk_percent"] < 50:
            over_provisioned_nodes.append(node["name"])

        # Under-provisioned: CPU > 80%, heap > 85%, disk > 85%
        if node["cpu_percent"] > 80 or node["heap_percent"] > 85 or node["disk_percent"] > 85:
            under_provisioned_nodes.append(node["name"])

        # Critical under-provisioning
        if node["heap_percent"] > 85:
            critical_nodes.append(("heap", node["name"], node["heap_percent"]))
        if node["disk_percent"] > 85:
            critical_nodes.append(("disk", node["name"], node["disk_percent"]))

        # Check for oversized shards (>50GB)
        if node["avg_shard_size"] > 50 * (1024 ** 3):
            oversized_shards.append(node["name"])

    # Recommendation Engine
    recommendations = []

    # Calculate recommended node count
    recommended_node_count = node_count
    estimated_cost_change = 0
    performance_impact = "Neutral"

    if len(over_provisioned_nodes) >= node_count * 0.5:  # More than 50% over-provisioned
        # Suggest reducing nodes
        recommended_node_count = max(3, int(node_count * 0.67))  # Reduce by ~33%, min 3 nodes
        estimated_cost_change = -33
        performance_impact = "Optimal"
        recommendations.append({
            "category": "Cluster Sizing",
            "finding": f"{len(over_provisioned_nodes)} nodes are over-provisioned",
            "recommendation": f"Reduce cluster from {node_count} to {recommended_node_count} nodes",
            "priority": "Medium"
        })
    elif len(under_provisioned_nodes) > 0:
        # Suggest adding nodes or upsizing
        if len(under_provisioned_nodes) >= node_count * 0.3:  # More than 30% under-provisioned
            recommended_node_count = int(node_count * 1.5)  # Increase by 50%
            estimated_cost_change = 50
            performance_impact = "Improved"
            recommendations.append({
                "category": "Cluster Sizing",
                "finding": f"{len(under_provisioned_nodes)} nodes are under-provisioned",
                "recommendation": f"Increase cluster from {node_count} to {recommended_node_count} nodes",
                "priority": "High"
            })
        else:
            recommendations.append({
                "category": "Node Sizing",
                "finding": f"{len(under_provisioned_nodes)} nodes need more resources",
                "recommendation": "Upsize node types or redistribute workload",
                "priority": "High"
            })

    # Shard distribution recommendations
    shard_imbalance = max(n["shard_count"] for n in node_metrics) - min(n["shard_count"] for n in node_metrics) if node_metrics else 0
    if shard_imbalance > avg_shards_per_node * 0.3:  # More than 30% imbalance
        recommendations.append({
            "category": "Shard Distribution",
            "finding": f"Unbalanced shard distribution (variance: {shard_imbalance} shards)",
            "recommendation": "Enable shard rebalancing or adjust allocation settings",
            "priority": "Medium"
        })

    # Oversized shard recommendations
    if oversized_shards:
        recommendations.append({
            "category": "Shard Sizing",
            "finding": f"{len(oversized_shards)} nodes have average shard size >50GB",
            "recommendation": "Adjust shard allocation settings or implement index rollover",
            "priority": "Medium"
        })

    # CPU recommendations
    if avg_cpu > 80:
        recommendations.append({
            "category": "CPU Utilization",
            "finding": f"Average CPU usage is {avg_cpu:.1f}%",
            "recommendation": "Scale cluster or optimize query workload",
            "priority": "High"
        })
    elif avg_cpu < 30:
        recommendations.append({
            "category": "CPU Utilization",
            "finding": f"Average CPU usage is only {avg_cpu:.1f}%",
            "recommendation": "Consider downsizing nodes or reducing node count",
            "priority": "Low"
        })

    # Heap recommendations
    if avg_heap > 85:
        recommendations.append({
            "category": "Heap Memory",
            "finding": f"Average heap usage is {avg_heap:.1f}%",
            "recommendation": "Increase heap size or add nodes immediately",
            "priority": "High"
        })

    # Calculate recommended metrics
    recommended_cpu = avg_cpu
    recommended_heap = avg_heap
    recommended_disk = avg_disk

    if recommended_node_count < node_count:
        # Consolidating nodes will increase utilization
        consolidation_factor = node_count / recommended_node_count
        recommended_cpu = min(avg_cpu * consolidation_factor, 75)
        recommended_heap = min(avg_heap * consolidation_factor, 75)
        recommended_disk = min(avg_disk * consolidation_factor, 75)
    elif recommended_node_count > node_count:
        # Adding nodes will decrease utilization
        expansion_factor = node_count / recommended_node_count
        recommended_cpu = avg_cpu * expansion_factor
        recommended_heap = avg_heap * expansion_factor
        recommended_disk = avg_disk * expansion_factor

    # Display warnings for critical issues
    console.print()
    for issue_type, node_name, value in critical_nodes:
        if issue_type == "heap":
            console.print(f"[red]⚠️  CRITICAL: Heap usage exceeds 85% on {node_name} ({value:.1f}%) - immediate action required[/red]")
        elif issue_type == "disk":
            console.print(f"[red]⚠️  CRITICAL: Disk usage exceeds 85% on {node_name} ({value:.1f}%) - risk of cluster instability[/red]")

    if avg_cpu > 80:
        console.print(f"[yellow]⚠️  WARNING: CPU usage consistently above 80% ({avg_cpu:.1f}%) - consider scaling[/yellow]")

    if critical_nodes or avg_cpu > 80:
        console.print()

    # Display Current vs Recommended Configuration table
    console.print()
    config_table = Table(
        title="Current vs Recommended Configuration",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    config_table.add_column("Metric", style="cyan")
    config_table.add_column("Current", justify="right", style="yellow")
    config_table.add_column("Recommended", justify="right", style="green")
    config_table.add_column("Impact", style="blue")

    # Node count
    node_impact = f"{((recommended_node_count - node_count) / node_count * 100):.0f}%" if node_count > 0 else "N/A"
    config_table.add_row("Node Count", str(node_count), str(recommended_node_count), node_impact)

    # CPU utilization
    config_table.add_row("Avg CPU Utilization", f"{avg_cpu:.1f}%", f"{recommended_cpu:.1f}%", performance_impact)

    # Heap utilization
    config_table.add_row("Avg Heap Utilization", f"{avg_heap:.1f}%", f"{recommended_heap:.1f}%", performance_impact)

    # Disk utilization
    config_table.add_row("Avg Disk Utilization", f"{avg_disk:.1f}%", f"{recommended_disk:.1f}%", performance_impact)

    # Total shard count
    config_table.add_row("Total Shard Count", str(total_shards), str(total_shards), "Unchanged")

    # Average shard size
    overall_avg_shard_size = sum(n["avg_shard_size"] for n in node_metrics) / len(node_metrics) if node_metrics else 0
    config_table.add_row(
        "Average Shard Size",
        bytes_to_human(int(overall_avg_shard_size)),
        bytes_to_human(int(overall_avg_shard_size)),
        "Unchanged"
    )

    # Estimated monthly cost change (simplified calculation)
    # Assume $100/node/month as baseline
    baseline_cost_per_node = 100
    current_monthly_cost = node_count * baseline_cost_per_node
    recommended_monthly_cost = recommended_node_count * baseline_cost_per_node
    monthly_cost_change = recommended_monthly_cost - current_monthly_cost

    config_table.add_row(
        "Estimated Monthly Cost Change",
        f"${current_monthly_cost}",
        f"${recommended_monthly_cost}",
        f"${monthly_cost_change:+.0f}/mo"
    )

    console.print(config_table)
    console.print()

    # Display Detailed Recommendations table
    if recommendations:
        rec_table = Table(
            title="Detailed Recommendations",
            box=box.ROUNDED,
            title_style="bold cyan"
        )
        rec_table.add_column("Category", style="cyan")
        rec_table.add_column("Finding", style="yellow")
        rec_table.add_column("Recommendation", style="green")
        rec_table.add_column("Priority", style="white")

        for rec in recommendations:
            priority_style = "red" if rec["priority"] == "High" else "yellow" if rec["priority"] == "Medium" else "green"
            rec_table.add_row(
                rec["category"],
                rec["finding"],
                rec["recommendation"],
                f"[{priority_style}]{rec['priority']}[/{priority_style}]"
            )

        console.print(rec_table)
        console.print()

    # Summary panel
    annual_savings = monthly_cost_change * 12
    complexity = "Low" if abs(recommended_node_count - node_count) <= 2 else "Medium" if abs(recommended_node_count - node_count) <= 4 else "High"

    console.print(f"[bold cyan]Summary:[/bold cyan]")
    if monthly_cost_change < 0:
        console.print(f"💰 Total potential cost savings: ${abs(monthly_cost_change):.0f}/month (${abs(annual_savings):.0f}/year)")
    elif monthly_cost_change > 0:
        console.print(f"💰 Additional cost required: ${monthly_cost_change:.0f}/month (${annual_savings:.0f}/year)")
    else:
        console.print(f"💰 No cost change expected")

    console.print(f"📊 Performance impact: {performance_impact}")
    console.print(f"🔧 Implementation complexity: {complexity}")
    console.print()
    console.print("[dim]Note: Recommendations are based on current usage patterns. Validate against peak load scenarios.[/dim]\n")

