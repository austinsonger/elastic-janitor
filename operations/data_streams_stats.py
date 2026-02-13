"""
Data stream operations for Elastic Janitor - Statistics & Lifecycle.
Statistics and lifecycle viewing for data streams.
"""
from datetime import datetime, timezone
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box
from ..config import console
from ..utils import show_breadcrumb


def option_data_stream_statistics(es):
    """Display ingestion rates, document counts, total size, and growth trends for each data stream."""
    show_breadcrumb(["Main Menu", "Data Stream Management", "Data Stream Statistics"])

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching data streams..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        ds_response = es.indices.get_data_stream()

    data_streams = ds_response.get("data_streams", [])

    if not data_streams:
        console.print("[yellow]🟡 No data streams found.[/yellow]\n")
        return

    # Get indices info for all backing indices
    indices_info = get_all_indices_info(es)

    # Collect statistics for each data stream
    stats_list = []
    now = datetime.now(timezone.utc)

    for ds in data_streams:
        ds_name = ds["name"]
        if PROTECT_SYSTEM and is_system(ds_name):
            continue

        indices = ds.get("indices", [])
        if not indices:
            continue

        total_docs = 0
        total_size_bytes = 0
        oldest_date = None
        newest_date = None

        for idx in indices:
            idx_name = idx["index_name"]
            idx_info = indices_info.get(idx_name)
            if idx_info:
                total_size_bytes += idx_info["size_bytes"]
                created = idx_info["created"]

                if oldest_date is None or created < oldest_date:
                    oldest_date = created
                if newest_date is None or created > newest_date:
                    newest_date = created

        # Calculate age and ingestion rate
        if oldest_date and newest_date:
            age_days = (now - oldest_date).days
            if age_days > 0:
                ingestion_rate = total_size_bytes / age_days  # bytes per day
            else:
                ingestion_rate = 0
        else:
            age_days = 0
            ingestion_rate = 0

        stats_list.append({
            "name": ds_name,
            "backing_count": len(indices),
            "total_size_bytes": total_size_bytes,
            "age_days": age_days,
            "ingestion_rate": ingestion_rate,
            "oldest_date": oldest_date,
            "newest_date": newest_date
        })

    # Sort by total size
    stats_list.sort(key=lambda x: x["total_size_bytes"], reverse=True)

    # Display statistics with pagination
    page_size = 3
    total_pages = (len(stats_list) + page_size - 1) // page_size
    current_page = 0

    while current_page < total_pages:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(stats_list))

        console.print()
        console.print(Panel(f"[bold cyan]DATA STREAM STATISTICS - Page {current_page + 1} of {total_pages}[/bold cyan]", box=box.DOUBLE))
        console.print()

        for i in range(start_idx, end_idx):
            stat = stats_list[i]

            console.print(f"[bold cyan]Data Stream {i+1}:[/bold cyan] {stat['name']}")
            console.print(f"  Backing indices: {stat['backing_count']}")
            console.print(f"  Total size: [yellow]{bytes_to_human(stat['total_size_bytes'])}[/yellow]")
            console.print(f"  Age: {stat['age_days']} days")
            if stat['ingestion_rate'] > 0:
                console.print(f"  Avg ingestion rate: [green]{bytes_to_human(stat['ingestion_rate'])}/day[/green]")
            if stat['oldest_date']:
                console.print(f"  Oldest index: {stat['oldest_date'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
            if stat['newest_date']:
                console.print(f"  Newest index: {stat['newest_date'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
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




def option_data_stream_lifecycle_viewer(es):
    """Show ILM/Data Stream Lifecycle (DSL) policy status, current phase, and age for each data stream's backing indices."""
    show_breadcrumb(["Main Menu", "Data Stream Management", "Data Stream Lifecycle Viewer"])

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching data streams and lifecycle information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        ds_response = es.indices.get_data_stream()

    data_streams = ds_response.get("data_streams", [])

    if not data_streams:
        console.print("[yellow]🟡 No data streams found.[/yellow]\n")
        return

    indices_info = get_all_indices_info(es)
    now = datetime.now(timezone.utc)

    # Collect lifecycle info for each data stream
    lifecycle_data = []

    for ds in data_streams:
        ds_name = ds["name"]
        if PROTECT_SYSTEM and is_system(ds_name):
            continue

        indices = ds.get("indices", [])
        if not indices:
            continue

        # Get ILM explain for backing indices
        backing_indices = [idx["index_name"] for idx in indices]

        try:
            ilm_explain = es.ilm.explain_lifecycle(index=",".join(backing_indices))
        except Exception:
            ilm_explain = {"indices": {}}

        lifecycle_data.append({
            "name": ds_name,
            "backing_indices": backing_indices,
            "ilm_explain": ilm_explain.get("indices", {})
        })

    # Display with pagination
    page_size = 3
    total_pages = (len(lifecycle_data) + page_size - 1) // page_size
    current_page = 0

    while current_page < total_pages:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(lifecycle_data))

        console.print()
        console.print(Panel(f"[bold cyan]DATA STREAM LIFECYCLE - Page {current_page + 1} of {total_pages}[/bold cyan]", box=box.DOUBLE))
        console.print()

        for i in range(start_idx, end_idx):
            ds_data = lifecycle_data[i]

            console.print(f"[bold cyan]Data Stream {i+1}:[/bold cyan] {ds_data['name']}")
            console.print(f"  Backing indices: {len(ds_data['backing_indices'])}")
            console.print()

            # Display lifecycle info for each backing index
            for idx_name in ds_data['backing_indices'][:5]:  # Show first 5
                ilm_info = ds_data['ilm_explain'].get(idx_name, {})
                idx_info = indices_info.get(idx_name)

                age_days = (now - idx_info["created"]).days if idx_info else 0

                policy = ilm_info.get("policy", "N/A")
                phase = ilm_info.get("phase", "N/A")
                action = ilm_info.get("action", "N/A")
                managed = ilm_info.get("managed", False)

                console.print(f"    [cyan]{idx_name}[/cyan]")
                console.print(f"      Age: {age_days} days")
                console.print(f"      Managed: {'Yes' if managed else 'No'}")
                if managed:
                    console.print(f"      Policy: {policy}")
                    console.print(f"      Phase: {phase}")
                    console.print(f"      Action: {action}")
                console.print()

            if len(ds_data['backing_indices']) > 5:
                console.print(f"    [dim]... and {len(ds_data['backing_indices']) - 5} more backing indices[/dim]\n")

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




