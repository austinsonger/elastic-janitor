"""
Index management operations for Elastic Janitor - Part 2.
Advanced index operations (aliases, rollover, migration, optimization).
"""
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console
from ..utils import show_breadcrumb, select_from_list, confirm_action
from ..core import get_all_indices_info


def option_index_alias_management(es):
    """Complete alias management."""
    show_breadcrumb(["Main Menu", "Index Management", "Index Alias Management"])

    # Get all aliases
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching aliases..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        aliases_data = es.cat.aliases(format="json", h="alias,index")

    # Group by alias
    alias_groups = defaultdict(list)
    for item in aliases_data:
        alias_groups[item["alias"]].append(item["index"])

    console.print()
    console.print(f"[cyan]Total aliases: {len(alias_groups)}[/cyan]\n")

    # Display aliases
    table = Table(title="Index Aliases", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Alias", style="yellow")
    table.add_column("Indices", style="cyan")

    for alias, indices in sorted(alias_groups.items())[:50]:
        table.add_row(alias, ", ".join(indices))

    console.print(table)

    if len(alias_groups) > 50:
        console.print(f"\n[dim]Showing first 50 of {len(alias_groups)} aliases[/dim]\n")

    console.print()




def option_index_rollover_status(es):
    """Display indices eligible for rollover."""
    show_breadcrumb(["Main Menu", "Index Management", "Index Rollover Status"])

    # Get thresholds from user
    max_age_days = get_number_input("Maximum age threshold (days, default 30):", default=30)
    max_size_gb = get_number_input("Maximum size threshold (GB, default 50):", default=50)
    max_docs = get_number_input("Maximum document count (millions, default 100):", default=100)

    if max_age_days is None or max_size_gb is None or max_docs is None:
        return

    max_size_bytes = max_size_gb * 1024**3
    max_docs_count = max_docs * 1_000_000
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    # Get indices info
    indices_info = get_all_indices_info(es)

    # Find eligible indices
    eligible = []
    for idx_name, info in indices_info.items():
        if is_system(idx_name):
            continue

        age_days = (datetime.now(timezone.utc) - info["created"]).days
        size_bytes = info["size_bytes"]

        # Check if eligible for rollover
        reasons = []
        if age_days >= max_age_days:
            reasons.append(f"age: {age_days}d >= {max_age_days}d")
        if size_bytes >= max_size_bytes:
            reasons.append(f"size: {bytes_to_human(size_bytes)} >= {max_size_gb}GB")

        if reasons:
            eligible.append((idx_name, age_days, size_bytes, ", ".join(reasons)))

    if not eligible:
        console.print("\n[green]✅ No indices eligible for rollover based on current thresholds.[/green]\n")
        return

    console.print()
    table = Table(title=f"Indices Eligible for Rollover ({len(eligible)})", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Index", style="cyan")
    table.add_column("Age (days)", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Rollover Reasons", style="yellow")

    for idx_name, age, size, reasons in eligible[:50]:
        table.add_row(idx_name, str(age), bytes_to_human(size), reasons)

    console.print(table)

    if len(eligible) > 50:
        console.print(f"\n[dim]Showing first 50 of {len(eligible)} eligible indices[/dim]\n")

    console.print()




def option_cold_frozen_migration(es):
    """Bulk migrate indices to colder storage tiers."""
    show_breadcrumb(["Main Menu", "Index Management", "Cold/Frozen Tier Migration"])

    min_age_days = get_number_input("Migrate indices older than (days, default 90):", default=90)
    if min_age_days is None:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)

    # Get indices info
    indices_info = get_all_indices_info(es)

    # Find eligible indices (not already in cold/frozen)
    eligible = []
    for idx_name, info in indices_info.items():
        if is_system(idx_name):
            continue

        if info["created"] < cutoff and info["tier"] not in ["cold", "frozen"]:
            age_days = (datetime.now(timezone.utc) - info["created"]).days
            eligible.append((idx_name, age_days, info["size"], info["tier"]))

    if not eligible:
        console.print("\n[green]✅ No indices eligible for migration.[/green]\n")
        return

    console.print()
    console.print(f"[cyan]Found {len(eligible)} indices eligible for migration:[/cyan]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Age (days)", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Current Tier", style="yellow")

    for idx_name, age, size, tier in eligible[:20]:
        table.add_row(idx_name, str(age), size, tier)

    console.print(table)

    if len(eligible) > 20:
        console.print(f"\n[dim]Showing first 20 of {len(eligible)} eligible indices[/dim]\n")

    console.print("\n[yellow]Note: Tier migration requires ILM policies or manual tier preference updates.[/yellow]")
    console.print("[yellow]This is a preview feature. Actual migration would require additional implementation.[/yellow]\n")




def option_index_merge_optimization(es):
    """Force merge operations to optimize indices."""
    show_breadcrumb(["Main Menu", "Index Management", "Index Merge Optimization"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching segment information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        segments = es.cat.segments(format="json", h="index,shard,prirep,segment,size")

    # Count segments per index
    segment_counts = defaultdict(int)
    for seg in segments:
        if seg.get("prirep") == "p":  # Only count primary shards
            segment_counts[seg["index"]] += 1

    # Filter indices with many segments
    high_segment_indices = [(idx, count) for idx, count in segment_counts.items() if count > 10 and not is_system(idx)]
    high_segment_indices.sort(key=lambda x: x[1], reverse=True)

    if not high_segment_indices:
        console.print("\n[green]✅ No indices with high segment counts found.[/green]\n")
        return

    console.print()
    table = Table(title="Indices with High Segment Counts", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Index", style="cyan")
    table.add_column("Segment Count", justify="right", style="yellow")

    for idx, count in high_segment_indices[:30]:
        table.add_row(idx, str(count))

    console.print(table)

    if len(high_segment_indices) > 30:
        console.print(f"\n[dim]Showing first 30 of {len(high_segment_indices)} indices[/dim]\n")

    console.print("\n[yellow]⚠️  Warning: Force merge is resource-intensive and should only be done on read-only indices.[/yellow]")
    console.print("[yellow]This is a preview feature. Actual force merge would require confirmation and implementation.[/yellow]\n")


# ------------------------------------------------------------
# DATA STREAM MANAGEMENT FEATURES
# ------------------------------------------------------------



