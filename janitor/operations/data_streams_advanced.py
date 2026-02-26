"""
Data stream operations for Elastic Janitor - Advanced Operations.
Reindexing, cloning, and write index rotation for data streams.
"""
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, GOD_MODE
from ..utils import show_breadcrumb, select_from_list, confirm_action, get_text_input


def option_backing_index_reindexing(es):
    """Provide an interactive wizard to reindex old backing indices with updated mappings or pipelines."""
    show_breadcrumb(["Main Menu", "Data Stream Management", "Backing Index Reindexing"])

    console.print()
    console.print("[yellow]⚠️  Reindexing Wizard[/yellow]\n")

    # Get data streams
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching data streams..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        ds_response = es.indices.get_data_stream()

    data_streams = ds_response.get("data_streams", [])
    ds_names = [ds["name"] for ds in data_streams if not (PROTECT_SYSTEM and is_system(ds["name"]))]

    if not ds_names:
        console.print("[yellow]🟡 No data streams found.[/yellow]\n")
        return

    # Select data stream
    selected_ds = select_from_list(
        "Select data stream to reindex:",
        choices=ds_names[:50] + (["... (showing first 50)"] if len(ds_names) > 50 else []),
        multi=False
    )

    if not selected_ds or selected_ds == "... (showing first 50)":
        return

    # Get backing indices for selected data stream
    ds_info = next((ds for ds in data_streams if ds["name"] == selected_ds), None)
    if not ds_info:
        console.print("[red]❌ Data stream not found.[/red]\n")
        return

    backing_indices = [idx["index_name"] for idx in ds_info.get("indices", [])]

    if not backing_indices:
        console.print("[yellow]🟡 No backing indices found.[/yellow]\n")
        return

    console.print(f"\n[cyan]Backing indices for {selected_ds}:[/cyan]\n")
    for idx in backing_indices:
        console.print(f"  • {idx}")

    # Select indices to reindex
    selected_indices = select_from_list(
        "\nSelect backing indices to reindex (use space to select, enter to confirm):",
        choices=backing_indices,
        multi=True
    )

    if not selected_indices:
        return

    console.print(f"\n[yellow]Selected {len(selected_indices)} indices for reindexing.[/yellow]\n")
    console.print("[yellow]⚠️  Note: This is a preview feature. Actual reindexing requires:[/yellow]")
    console.print("  1. Create new index with updated mappings/settings")
    console.print("  2. Use _reindex API to copy data")
    console.print("  3. Verify data integrity")
    console.print("  4. Update aliases if needed")
    console.print("  5. Delete old index\n")
    console.print("[blue]ℹ️  For production use, implement full reindexing logic with error handling.[/blue]\n")




def option_data_stream_cloning(es):
    """Clone entire data streams (including settings and mappings) for testing or backup purposes."""
    show_breadcrumb(["Main Menu", "Data Stream Management", "Data Stream Cloning"])

    console.print()
    console.print("[yellow]⚠️  Data Stream Cloning Wizard[/yellow]\n")

    # Get data streams
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching data streams..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        ds_response = es.indices.get_data_stream()

    data_streams = ds_response.get("data_streams", [])
    ds_names = [ds["name"] for ds in data_streams if not (PROTECT_SYSTEM and is_system(ds["name"]))]

    if not ds_names:
        console.print("[yellow]🟡 No data streams found.[/yellow]\n")
        return

    # Select source data stream
    source_ds = select_from_list(
        "Select source data stream to clone:",
        choices=ds_names[:50] + (["... (showing first 50)"] if len(ds_names) > 50 else []),
        multi=False
    )

    if not source_ds or source_ds == "... (showing first 50)":
        return

    # Get target name
    target_ds = get_text_input(f"\nEnter target data stream name (source: {source_ds}):", default=f"{source_ds}-clone")

    if not target_ds:
        return

    console.print(f"\n[cyan]Cloning plan:[/cyan]")
    console.print(f"  Source: {source_ds}")
    console.print(f"  Target: {target_ds}\n")

    console.print("[yellow]⚠️  Note: This is a preview feature. Actual cloning requires:[/yellow]")
    console.print("  1. Get source data stream template and settings")
    console.print("  2. Create new index template for target data stream")
    console.print("  3. Create target data stream")
    console.print("  4. Optionally reindex data from source to target")
    console.print("  5. Verify clone integrity\n")
    console.print("[blue]ℹ️  For production use, implement full cloning logic with error handling.[/blue]\n")




def option_write_index_rotation(es):
    """Manually trigger rollover for selected data streams."""
    show_breadcrumb(["Main Menu", "Data Stream Management", "Write Index Rotation"])

    console.print()
    console.print("[yellow]⚠️  Manual Rollover Wizard[/yellow]\n")

    # Get data streams
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching data streams..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        ds_response = es.indices.get_data_stream()

    data_streams = ds_response.get("data_streams", [])
    ds_names = [ds["name"] for ds in data_streams if not (PROTECT_SYSTEM and is_system(ds["name"]))]

    if not ds_names:
        console.print("[yellow]🟡 No data streams found.[/yellow]\n")
        return

    # Select data streams to rollover
    selected_streams = select_from_list(
        "Select data streams to rollover (use space to select, enter to confirm):",
        choices=ds_names[:50] + (["... (showing first 50)"] if len(ds_names) > 50 else []),
        multi=True
    )

    if not selected_streams or "... (showing first 50)" in selected_streams:
        return

    selected_streams = [s for s in selected_streams if s != "... (showing first 50)"]

    console.print(f"\n[cyan]Selected {len(selected_streams)} data streams for rollover:[/cyan]\n")
    for ds in selected_streams:
        console.print(f"  • {ds}")

    console.print()

    if not confirm_action(f"Trigger rollover for {len(selected_streams)} data stream(s)?", len(selected_streams)):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global GOD_MODE
    if not GOD_MODE:
        console.print("\n[yellow]🔍 SAFE MODE: Simulating rollover operations...[/yellow]\n")
        for ds in selected_streams:
            console.print(f"  [blue]Would rollover:[/blue] {ds}")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    # Perform actual rollover
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Rolling over data streams...", total=len(selected_streams))

        for ds in selected_streams:
            progress.update(task, description=f"[cyan]Rolling over: {ds[:50]}...")
            try:
                es.indices.rollover(alias=ds)
            except Exception as e:
                console.print(f"[red]ERROR rolling over {ds}: {e}[/red]")
            progress.advance(task)

    console.print("\n[green]✅ Rollover complete.[/green]\n")


# ------------------------------------------------------------
# GLOBAL FEATURES
# ------------------------------------------------------------



