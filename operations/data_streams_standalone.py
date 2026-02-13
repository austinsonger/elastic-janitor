"""
Data stream operations for Elastic Janitor - Standalone Indices.
Cleaning standalone indices not part of data streams.
"""
from datetime import datetime, timezone, timedelta
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, DEFAULT_RETENTION_DAYS, MAX_DELETE_LIMIT, DRY_RUN_MODE
from ..utils import is_system, confirm_delete, safe_input, show_breadcrumb
from ..core import get_all_indices_info


def option_clean_standalone_indices(es):
    days_input = safe_input(
        f"How many days of data to KEEP? (standalone indices older than this will be deleted, default {DEFAULT_RETENTION_DAYS}): "
    ).strip()
    days = int(days_input) if days_input else DEFAULT_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    console.print()
    indices_info = get_all_indices_info(es)

    # Find all data stream backing indices so we can skip them
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing data streams..."),
        transient=True,
    ) as progress:
        progress.add_task("analyze", total=None)
        ds_response = es.indices.get_data_stream()
        data_streams = ds_response.get("data_streams", [])

    ds_backing = set()
    ds_write = set()

    for ds in data_streams:
        indices = ds.get("indices", [])
        if not indices:
            continue
        write_index = indices[-1]["index_name"]
        ds_write.add(write_index)
        for idx in indices:
            ds_backing.add(idx["index_name"])

    # Collect all standalone indices
    all_standalone = []

    for idx_name, idx_info in indices_info.items():
        # Skip system indices
        if PROTECT_SYSTEM and is_system(idx_name):
            continue

        # Skip data stream backing indices entirely
        if idx_name in ds_backing:
            continue

        # Skip current write indices (should already be in ds_backing, but extra safe)
        if idx_name in ds_write:
            continue

        all_standalone.append((idx_name, idx_info["created"], idx_info["size"], idx_info["size_bytes"], idx_info["tier"]))

    # Group indices by base name pattern (everything before the last dash or date pattern)
    # This helps identify if an index is the only one of its kind
    from collections import defaultdict
    index_groups = defaultdict(list)

    for idx_name, created, size, size_bytes, tier in all_standalone:
        # Simple grouping: use the full name as the group key
        # If there's only 1 index with this exact name, it's unique
        index_groups[idx_name].append((idx_name, created, size, size_bytes, tier))

    # Now separate into delete and keep lists
    # Rule: Never delete an index if it's the ONLY index (count == 1)
    delete_list = []
    keep_list = []
    protected_singles = []

    for idx_name, created, size, size_bytes, tier in all_standalone:
        # Check if this is the only index (no versioning, no duplicates)
        group_count = len(index_groups[idx_name])

        if group_count == 1:
            # This is the ONLY index with this name - always keep it
            protected_singles.append((idx_name, created, size, size_bytes, tier))
        elif created < cutoff:
            delete_list.append((idx_name, created, size, size_bytes, tier))
        else:
            keep_list.append((idx_name, created, size, size_bytes, tier))

    delete_list.sort(key=lambda x: x[1])
    keep_list.sort(key=lambda x: x[1], reverse=True)
    protected_singles.sort(key=lambda x: x[1], reverse=True)

    # Calculate totals
    total_delete_size = sum(size_bytes for _, _, _, size_bytes, _ in delete_list)
    total_keep_size = sum(size_bytes for _, _, _, size_bytes, _ in keep_list)
    total_protected_size = sum(size_bytes for _, _, _, size_bytes, _ in protected_singles)

    # Show summary
    console.print()
    standalone_summary = Table(title="STANDALONE INDICES - DELETION PREVIEW", box=box.DOUBLE_EDGE, title_style="bold cyan")
    standalone_summary.add_column("Category", style="cyan", no_wrap=True)
    standalone_summary.add_column("Count", justify="right")
    standalone_summary.add_column("Size", justify="right")

    standalone_summary.add_row(
        "Indices to DELETE",
        f"[red]{len(delete_list)}[/red]",
        f"[red bold]{bytes_to_human(total_delete_size)}[/red bold]"
    )
    standalone_summary.add_row(
        "Indices to KEEP (within retention)",
        f"[green]{len(keep_list)}[/green]",
        f"[green]{bytes_to_human(total_keep_size)}[/green]"
    )
    standalone_summary.add_row(
        "Indices PROTECTED (only copy)",
        f"[yellow]{len(protected_singles)}[/yellow]",
        f"[yellow]{bytes_to_human(total_protected_size)}[/yellow]"
    )

    console.print(standalone_summary)
    console.print()

    if not delete_list:
        console.print("[green]✅ No standalone indices eligible for deletion.[/green]\n")
        return

    if len(delete_list) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} indices in one run.[/red]\n")
        return

    now = datetime.now(timezone.utc)

    # Show protected singles (never deleted because they're the only copy)
    if protected_singles:
        console.print("[green]✅ PROTECTED STANDALONE INDICES (only copy - will NEVER be deleted):[/green]\n")
        display_count = min(10, len(protected_singles))
        for idx_name, created, size, size_bytes, tier in protected_singles[:display_count]:
            age_days = (now - created).days
            console.print(f"  [green]✅ {idx_name}[/green] | age: {age_days} days | size: {size} | tier: {tier} | created: {created.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        if len(protected_singles) > display_count:
            console.print(f"  [dim]... and {len(protected_singles) - display_count} more[/dim]\n")
        else:
            console.print()

    # Show indices to keep (within retention period)
    if keep_list:
        console.print("[green]✅ STANDALONE INDICES THAT WILL BE KEPT (within retention period):[/green]\n")
        display_count = min(10, len(keep_list))
        for idx_name, created, size, size_bytes, tier in keep_list[:display_count]:
            age_days = (now - created).days
            console.print(f"  [green]✅ {idx_name}[/green] | age: {age_days} days | size: {size} | tier: {tier} | created: {created.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        if len(keep_list) > display_count:
            console.print(f"  [dim]... and {len(keep_list) - display_count} more[/dim]\n")
        else:
            console.print()

    # Show indices to delete
    console.print("[red]❌ STANDALONE INDICES THAT WILL BE DELETED:[/red]\n")
    for idx_name, created, size, size_bytes, tier in delete_list:
        age_days = (now - created).days
        console.print(f"  [red]❌ {idx_name}[/red] | age: {age_days} days | size: {size} | tier: {tier} | created: {created.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    console.print()
    delete_summary = Table(box=box.DOUBLE_EDGE, show_header=False)
    delete_summary.add_column("Label", style="cyan")
    delete_summary.add_column("Value", style="red bold")
    delete_summary.add_row("TOTAL TO DELETE", f"{len(delete_list)} indices")
    delete_summary.add_row("SIZE TO RECLAIM", bytes_to_human(total_delete_size))
    console.print(delete_summary)
    console.print()

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(delete_list)} standalone indices:[/blue]\n")
        for idx_name, created, size, size_bytes, tier in delete_list[:10]:
            console.print(f"  [blue]•[/blue] {idx_name} ({size})")
        if len(delete_list) > 10:
            console.print(f"  [dim]... and {len(delete_list) - 10} more[/dim]")
        console.print(f"\n[blue]Total size to reclaim: {bytes_to_human(total_delete_size)}[/blue]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[red]Deleting indices...", total=len(delete_list))

        for idx_name, _, size, _, tier in delete_list:
            progress.update(task, description=f"[red]Deleting: {idx_name[:50]}...")
            es.indices.delete(index=idx_name, ignore_unavailable=True)
            progress.advance(task)

    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 3: Largest indices
# ------------------------------------------------------------



