"""
Data stream operations for Elastic Janitor - Cleanup Operations.
Cleaning and deleting data streams and standalone indices.
"""
from datetime import datetime, timezone, timedelta
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, DEFAULT_RETENTION_DAYS, MAX_DELETE_LIMIT, DRY_RUN_MODE
from ..utils import is_system, confirm_delete, safe_input, show_breadcrumb
from ..core import get_all_indices_info


def option_clean_data_streams(es):
    days_input = safe_input(
        f"Retention cutoff in days? (default {DEFAULT_RETENTION_DAYS}): "
    ).strip()
    days = int(days_input) if days_input else DEFAULT_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    console.print()
    indices_info = get_all_indices_info(es)

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching data streams..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch_ds", total=None)
        ds_response = es.indices.get_data_stream()

    data_streams = ds_response.get("data_streams", [])

    if not data_streams:
        console.print("[yellow]🟡 No data streams found.[/yellow]\n")
        return

    summaries = []

    for ds in data_streams:
        ds_name = ds["name"]

        if PROTECT_SYSTEM and is_system(ds_name):
            continue

        indices = ds.get("indices", [])
        if not indices:
            continue

        write_index = indices[-1]["index_name"]
        backing = [x["index_name"] for x in indices]

        eligible = []
        for idx_name in backing:
            if idx_name == write_index:
                continue

            idx_info = indices_info.get(idx_name)
            if not idx_info:
                continue

            created = idx_info["created"]
            if created < cutoff:
                eligible.append((idx_name, created, idx_info["size"], idx_info["size_bytes"], idx_info["tier"]))

        summaries.append({
            "name": ds_name,
            "total_backing": len(backing),
            "write_index": write_index,
            "eligible": eligible
        })

    summaries.sort(key=lambda x: len(x["eligible"]), reverse=True)

    # Calculate totals first
    now = datetime.now(timezone.utc)
    total_eligible = 0
    total_size_bytes = 0

    for s in summaries:
        if s["eligible"]:
            total_eligible += len(s["eligible"])
            stream_size_bytes = sum(size_bytes for _, _, _, size_bytes, _ in s["eligible"])
            total_size_bytes += stream_size_bytes

    # Show summary first
    console.print()
    summary_table = Table(title="DATA STREAMS - DELETION PREVIEW SUMMARY", box=box.DOUBLE_EDGE, title_style="bold cyan")
    summary_table.add_column("Metric", style="cyan", no_wrap=True)
    summary_table.add_column("Value", style="yellow")

    summary_table.add_row("Data streams with eligible indices", str(sum(1 for s in summaries if s['eligible'])))
    summary_table.add_row("Total backing indices eligible for deletion", f"[red]{total_eligible}[/red]")
    summary_table.add_row("Total size to reclaim", f"[red bold]{bytes_to_human(total_size_bytes)}[/red bold]")

    console.print(summary_table)
    console.print()

    # Show detailed preview with pagination
    streams_with_eligible = [s for s in summaries if s["eligible"]]

    if not streams_with_eligible:
        console.print("[green]✅ No indices eligible for deletion.[/green]\n")
        return

    page_size = 3  # Show 3 data streams at a time
    total_pages = (len(streams_with_eligible) + page_size - 1) // page_size
    current_page = 0

    while current_page < total_pages:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(streams_with_eligible))

        console.print()
        console.print(Panel(f"[bold cyan]DETAILED VIEW - Page {current_page + 1} of {total_pages}[/bold cyan]", box=box.DOUBLE))
        console.print()

        for i in range(start_idx, end_idx):
            s = streams_with_eligible[i]
            stream_size_bytes = sum(size_bytes for _, _, _, size_bytes, _ in s["eligible"])

            console.print(f"[bold cyan]Data Stream {i+1}:[/bold cyan] {s['name']}")
            console.print(f"  Total backing indices: {s['total_backing']}")
            console.print(f"  Indices eligible for deletion: [red]{len(s['eligible'])}[/red]")
            console.print(f"  Total size to reclaim: [red bold]{bytes_to_human(stream_size_bytes)}[/red bold]")
            console.print()
            console.print(f"  [green]✅ CURRENT WRITE INDEX (PROTECTED - WILL NOT BE DELETED):[/green]")

            # Show write index info
            write_idx_info = indices_info.get(s['write_index'])
            if write_idx_info:
                write_age_days = (now - write_idx_info['created']).days
                console.print(f"    [green]✅ {s['write_index']}[/green] | age: {write_age_days} days | size: {write_idx_info['size']} | tier: {write_idx_info['tier']} | created: {write_idx_info['created'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
            else:
                console.print(f"    [green]✅ {s['write_index']}[/green]")

            console.print()
            console.print(f"  [red]❌ BACKING INDICES THAT WOULD BE DELETED:[/red]")

            for idx_name, created, size, size_bytes, tier in s["eligible"]:
                age_days = (now - created).days
                console.print(f"    [red]❌ {idx_name}[/red] | age: {age_days} days | size: {size} | tier: {tier} | created: {created.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            console.print()

        # Pagination prompt
        if current_page < total_pages - 1:
            console.print("[cyan]" + "─" * 80 + "[/cyan]")
            choice = safe_input("Press Enter for next page, or 'q' to finish viewing: ").strip().lower()
            if choice in ('q', 'quit', 'exit'):
                break
            current_page += 1
        else:
            current_page += 1

    console.print()
    final_summary = Table(title="SUMMARY", box=box.DOUBLE_EDGE, title_style="bold yellow")
    final_summary.add_column("Metric", style="cyan", no_wrap=True)
    final_summary.add_column("Value", style="yellow")
    final_summary.add_row("Total backing indices eligible for deletion", f"[red]{total_eligible}[/red]")
    final_summary.add_row("Total size to reclaim", f"[red bold]{bytes_to_human(total_size_bytes)}[/red bold]")
    console.print(final_summary)
    console.print()

    if total_eligible == 0:
        console.print("[green]✅ No indices eligible for deletion.[/green]\n")
        return

    console.print("\n[cyan]Select streams to clean:[/cyan]")
    console.print("  [blue]•[/blue] number (example: 5)")
    console.print("  [blue]•[/blue] multiple (example: 1,4,9)")
    console.print("  [blue]•[/blue] all")
    console.print("  [blue]•[/blue] q (quit without deleting)\n")

    choice = safe_input("Selection: ").strip().lower()
    if choice in ("q", "quit", "exit"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    selected = []
    if choice == "all":
        selected = [s for s in summaries if s["eligible"]]
    else:
        try:
            nums = [int(x.strip()) for x in choice.split(",") if x.strip()]
        except ValueError:
            console.print("[red]❌ Invalid selection.[/red]\n")
            return

        for n in nums:
            if n < 1 or n > len(summaries):
                console.print(f"[red]❌ Invalid selection: {n}[/red]")
                return
            if summaries[n - 1]["eligible"]:
                selected.append(summaries[n - 1])
            else:
                console.print(f"[yellow]⚠️  Warning: Data stream #{n} has no eligible indices to delete, skipping.[/yellow]")

    if not selected:
        console.print("\n[yellow]🟡 No data streams with eligible indices selected.[/yellow]\n")
        return

    delete_list = []
    for s in selected:
        for idx_name, created, size, size_bytes, tier in s["eligible"]:
            delete_list.append((s["name"], idx_name, created, size, size_bytes, tier))

    delete_list.sort(key=lambda x: x[2])

    if not delete_list:
        console.print("\n[yellow]🟡 No eligible backing indices found in selected streams.[/yellow]\n")
        return

    if len(delete_list) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} indices in one run.[/red]\n")
        return

    # Show final confirmation summary
    console.print()
    confirm_panel = Panel(
        f"[bold red]READY TO DELETE {len(delete_list)} BACKING INDICES FROM {len(selected)} DATA STREAM(S)[/bold red]",
        box=box.DOUBLE_EDGE,
        style="red"
    )
    console.print(confirm_panel)

    for s in selected:
        console.print(f"  [red]•[/red] {s['name']}: [red]{len(s['eligible'])} indices[/red]")

    console.print()

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(delete_list)} backing indices:[/blue]\n")
        for ds_name, idx_name, created, size, size_bytes, tier in delete_list[:10]:
            console.print(f"  [blue]•[/blue] {idx_name} ({size})")
        if len(delete_list) > 10:
            console.print(f"  [dim]... and {len(delete_list) - 10} more[/dim]")
        console.print(f"\n[blue]Total size to reclaim: {bytes_to_human(sum(size_bytes for _, _, _, _, size_bytes, _ in delete_list))}[/blue]")
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

        for ds_name, idx_name, _, size, _, tier in delete_list:
            progress.update(task, description=f"[red]Deleting: {idx_name[:50]}...")
            es.indices.delete(index=idx_name, ignore_unavailable=True)
            progress.advance(task)

    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 2: Clean standalone indices
# ------------------------------------------------------------



