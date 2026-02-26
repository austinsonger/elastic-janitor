"""
Data stream operations for Elastic Janitor - Preview.
Preview data streams and their backing indices.
"""
from datetime import datetime, timezone, timedelta
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, PROTECT_SYSTEM, DEFAULT_RETENTION_DAYS
from ..utils import show_breadcrumb, safe_input, is_system, bytes_to_human, paginate_items
from ..core import get_index_creation, get_all_indices_info


def option_preview_data_streams(es):
    days_input = safe_input(
        f"How many days of data to KEEP? (indices older than this will be shown, default {DEFAULT_RETENTION_DAYS}): "
    ).strip()
    days = int(days_input) if days_input else DEFAULT_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    console.print()
    indices_info = get_all_indices_info(es)

    with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching data streams..."), transient=True) as progress:
        progress.add_task("fetch", total=None)
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
    preview_summary = Table(title=f"PREVIEW: Data streams with indices older than {days} days", box=box.DOUBLE_EDGE, title_style="bold cyan")
    preview_summary.add_column("Metric", style="cyan", no_wrap=True)
    preview_summary.add_column("Value", style="yellow")

    preview_summary.add_row("Data streams with eligible indices", str(sum(1 for s in summaries if s['eligible'])))
    preview_summary.add_row("Total backing indices eligible for deletion", f"[red]{total_eligible}[/red]")
    preview_summary.add_row("Total size to reclaim", f"[red bold]{bytes_to_human(total_size_bytes)}[/red bold]")

    console.print(preview_summary)
    console.print()

    if total_eligible == 0:
        console.print("[green]✅ No indices eligible for deletion with current retention settings.[/green]\n")
        return

    # Show detailed preview with pagination
    streams_with_eligible = [s for s in summaries if s["eligible"]]

    # Render function for each data stream preview
    def render_stream_preview(s, index):
        stream_size_bytes = sum(size_bytes for _, _, _, size_bytes, _ in s["eligible"])

        console.print(f"[bold cyan]Data Stream {index}:[/bold cyan] {s['name']}")
        console.print(f"  Total backing indices: {s['total_backing']}")
        console.print(f"  Indices eligible for deletion: [red]{len(s['eligible'])}[/red]")
        console.print(f"  Total size to reclaim: [red bold]{bytes_to_human(stream_size_bytes)}[/red bold]")
        console.print()
        console.print(f"  [green]CURRENT WRITE INDEX (PROTECTED - WILL NOT BE DELETED):[/green]")

        # Show write index info
        write_idx_info = indices_info.get(s['write_index'])
        if write_idx_info:
            write_age_days = (now - write_idx_info['created']).days
            console.print(f"    [green]{s['write_index']}[/green] | age: {write_age_days} days | size: {write_idx_info['size']} | tier: {write_idx_info['tier']} | created: {write_idx_info['created'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        else:
            console.print(f"    [green]{s['write_index']}[/green]")

        console.print()
        console.print(f"  [red]BACKING INDICES THAT WOULD BE DELETED:[/red]")

        for idx_name, created, size, size_bytes, tier in s["eligible"]:
            age_days = (now - created).days
            console.print(f"    [red]{idx_name}[/red] | age: {age_days} days | size: {size} | tier: {tier} | created: {created.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        console.print()

    # Display with pagination
    paginate_items(streams_with_eligible, render_stream_preview, page_size=10, title="DETAILED VIEW")

    console.print()
    final_preview_summary = Table(title="SUMMARY", box=box.DOUBLE_EDGE, title_style="bold yellow")
    final_preview_summary.add_column("Metric", style="cyan", no_wrap=True)
    final_preview_summary.add_column("Value", style="yellow")
    final_preview_summary.add_row("Total backing indices eligible for deletion", f"[red]{total_eligible}[/red]")
    final_preview_summary.add_row("Total size to reclaim", f"[red bold]{bytes_to_human(total_size_bytes)}[/red bold]")
    console.print(final_preview_summary)
    console.print(f"\n[blue]ℹ️  Note: This is a preview only. Use option 1 to actually delete indices.[/blue]\n")


# ------------------------------------------------------------
# NEW INDEX MANAGEMENT FEATURES
# ------------------------------------------------------------



