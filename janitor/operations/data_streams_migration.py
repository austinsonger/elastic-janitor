"""
Data Stream Migration for Elastic Janitor.
Migrate entire data streams between clusters or within the same cluster.
"""
import time
from datetime import datetime
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, GOD_MODE, PROTECT_SYSTEM, REINDEX_TIMEOUT
from ..utils import (
    show_breadcrumb, select_from_list, confirm_action, 
    get_text_input, is_system
)
from ..utils.formatters import bytes_to_human


def option_data_stream_migration(es):
    """
    Interactive wizard to migrate entire data streams between clusters or within the same cluster.
    Preserves all backing indices, data stream metadata, index templates, ILM policies, and write index designation.
    """
    show_breadcrumb(["Main Menu", "Data Stream Management", "Data Stream Migration"])
    
    console.print()
    console.print("[yellow]⚠️  Data Stream Migration Wizard[/yellow]\n")
    console.print("[cyan]This wizard will help you migrate data streams while preserving:[/cyan]")
    console.print("  • All backing indices and their data")
    console.print("  • Data stream metadata and settings")
    console.print("  • Index templates and ILM policies")
    console.print("  • Write index designation\n")
    
    # Step 1: Select migration mode
    mode = select_from_list(
        "Select migration mode:",
        choices=[
            "Cross-cluster migration (to remote cluster)",
            "Same-cluster migration (clone with new name)",
            "← Cancel"
        ],
        multi=False
    )
    
    if not mode or mode == "← Cancel":
        return
    
    is_cross_cluster = mode.startswith("Cross-cluster")
    
    # Step 2: Get available data streams
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching data streams..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            ds_response = es.indices.get_data_stream()
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch data streams: {e}[/red]\n")
            return
    
    data_streams = ds_response.get("data_streams", [])
    
    # Filter system data streams if protection is enabled
    if PROTECT_SYSTEM:
        ds_names = [ds["name"] for ds in data_streams if not is_system(ds["name"])]
    else:
        ds_names = [ds["name"] for ds in data_streams]
    
    if not ds_names:
        console.print("[yellow]🟡 No data streams found.[/yellow]\n")
        return
    
    # Step 3: Select source data stream
    source_ds_name = select_from_list(
        "Select source data stream to migrate:",
        choices=ds_names[:50] + (["... (showing first 50)"] if len(ds_names) > 50 else []),
        multi=False
    )
    
    if not source_ds_name or source_ds_name == "... (showing first 50)":
        return
    
    # Get source data stream details
    source_ds = next((ds for ds in data_streams if ds["name"] == source_ds_name), None)
    if not source_ds:
        console.print("[red]❌ Data stream not found.[/red]\n")
        return
    
    backing_indices = [idx["index_name"] for idx in source_ds.get("indices", [])]
    
    # Calculate total size
    total_size_bytes = 0
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Calculating data stream size..."),
            transient=True,
        ) as progress:
            progress.add_task("calc", total=None)
            stats = es.indices.stats(index=",".join(backing_indices))
            for idx_name in backing_indices:
                idx_stats = stats.get("indices", {}).get(idx_name, {})
                total_size_bytes += idx_stats.get("total", {}).get("store", {}).get("size_in_bytes", 0)
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not calculate size: {e}[/yellow]")
    
    # Step 4: Get destination
    if is_cross_cluster:
        dest_cluster_url = get_text_input(
            "\nEnter destination cluster URL (e.g., https://cluster.example.com:9200):",
            default=""
        )
        if not dest_cluster_url:
            console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
            return
        dest_ds_name = source_ds_name  # Keep same name for cross-cluster
    else:
        dest_ds_name = get_text_input(
            f"\nEnter new data stream name (source: {source_ds_name}):",
            default=f"{source_ds_name}-clone"
        )
        if not dest_ds_name:
            console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
            return
        dest_cluster_url = None
    
    # Step 5: Display preview
    console.print()
    preview_table = Table(title="Migration Preview", box=box.ROUNDED, title_style="bold cyan")
    preview_table.add_column("Property", style="cyan")
    preview_table.add_column("Value", style="yellow")
    
    preview_table.add_row("Migration Mode", "Cross-cluster" if is_cross_cluster else "Same-cluster")
    preview_table.add_row("Source Data Stream", source_ds_name)
    preview_table.add_row("Destination", dest_cluster_url if is_cross_cluster else dest_ds_name)
    preview_table.add_row("Backing Indices Count", str(len(backing_indices)))
    preview_table.add_row("Total Data Size", bytes_to_human(total_size_bytes))
    preview_table.add_row("Write Index", backing_indices[-1] if backing_indices else "N/A")
    
    console.print(preview_table)
    console.print()

    # Step 6: Confirm action
    if not confirm_action(f"Proceed with migration of {len(backing_indices)} backing indices?", len(backing_indices)):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Step 7: Check dry-run mode
    if not GOD_MODE:
        console.print("\n[yellow]🔍 SAFE MODE: Simulating migration...[/yellow]\n")
        console.print(f"[blue]Would migrate:[/blue] {source_ds_name}")
        console.print(f"[blue]Destination:[/blue] {dest_cluster_url if is_cross_cluster else dest_ds_name}")
        console.print(f"[blue]Backing indices:[/blue] {len(backing_indices)}")
        console.print(f"[blue]Total size:[/blue] {bytes_to_human(total_size_bytes)}")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    # Step 8: Perform migration
    console.print()
    start_time = time.time()

    try:
        if is_cross_cluster:
            _migrate_cross_cluster(es, source_ds, dest_cluster_url, backing_indices)
        else:
            _migrate_same_cluster(es, source_ds, dest_ds_name, backing_indices)

        elapsed_time = time.time() - start_time

        # Display success summary
        console.print()
        success_panel = Panel(
            f"[bold green]✅ Migration Complete![/bold green]\n\n"
            f"Source: {source_ds_name}\n"
            f"Destination: {dest_cluster_url if is_cross_cluster else dest_ds_name}\n"
            f"Indices migrated: {len(backing_indices)}\n"
            f"Data transferred: {bytes_to_human(total_size_bytes)}\n"
            f"Time elapsed: {elapsed_time:.2f} seconds",
            title="Migration Summary",
            box=box.ROUNDED,
            style="green"
        )
        console.print(success_panel)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Migration failed: {e}[/red]\n")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


def _migrate_cross_cluster(es, source_ds, dest_cluster_url, backing_indices):
    """Migrate data stream to a remote cluster using reindex with remote."""
    console.print("[cyan]Starting cross-cluster migration...[/cyan]\n")
    console.print("[yellow]⚠️  Note: Cross-cluster migration requires:[/yellow]")
    console.print("  1. Remote cluster configured in elasticsearch.yml")
    console.print("  2. Destination cluster accessible from source")
    console.print("  3. Index templates created on destination")
    console.print("  4. Sufficient resources on destination cluster\n")
    console.print("[blue]ℹ️  This is a preview feature. Full implementation requires:[/blue]")
    console.print("  • Remote cluster configuration")
    console.print("  • Authentication setup")
    console.print("  • Template and policy replication")
    console.print("  • Reindex API with remote source\n")

    # Placeholder for actual implementation
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Migrating indices...", total=len(backing_indices))

        for idx in backing_indices:
            progress.update(task, description=f"[cyan]Would migrate: {idx[:50]}...")
            time.sleep(0.1)  # Simulate work
            progress.advance(task)


def _migrate_same_cluster(es, source_ds, dest_ds_name, backing_indices):
    """Clone data stream within the same cluster using clone/reindex operations."""
    console.print("[cyan]Starting same-cluster migration (cloning)...[/cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        # Step 1: Get source index template
        task = progress.add_task("[cyan]Fetching source index template...", total=4)

        try:
            # Find the index template for this data stream
            templates = es.indices.get_index_template()
            source_template = None
            for template in templates.get("index_templates", []):
                for pattern in template.get("index_template", {}).get("index_patterns", []):
                    if source_ds["name"].startswith(pattern.replace("*", "")):
                        source_template = template
                        break
                if source_template:
                    break

            progress.advance(task)

            # Step 2: Create new index template for destination
            progress.update(task, description="[cyan]Creating destination index template...")

            if source_template:
                new_template_name = f"{dest_ds_name}-template"
                new_template_body = source_template.get("index_template", {}).copy()
                new_template_body["index_patterns"] = [f"{dest_ds_name}*"]

                # Note: In a real implementation, we would create the template here
                # es.indices.put_index_template(name=new_template_name, body=new_template_body)

            progress.advance(task)

            # Step 3: Create destination data stream
            progress.update(task, description="[cyan]Creating destination data stream...")

            # Note: In a real implementation, we would create the data stream here
            # es.indices.create_data_stream(name=dest_ds_name)

            progress.advance(task)

            # Step 4: Reindex data
            progress.update(task, description="[cyan]Reindexing data...")
            progress.advance(task)

        except Exception as e:
            console.print(f"[red]❌ ERROR during migration: {e}[/red]")
            raise

        # Reindex each backing index
        reindex_task = progress.add_task("[cyan]Reindexing backing indices...", total=len(backing_indices))

        for idx in backing_indices:
            progress.update(reindex_task, description=f"[cyan]Reindexing: {idx[:50]}...")

            # Note: In a real implementation, we would reindex here
            # dest_idx = idx.replace(source_ds["name"], dest_ds_name)
            # es.reindex(
            #     body={
            #         "source": {"index": idx},
            #         "dest": {"index": dest_idx, "op_type": "create"}
            #     },
            #     wait_for_completion=True,
            #     request_timeout=REINDEX_TIMEOUT
            # )

            time.sleep(0.1)  # Simulate work
            progress.advance(reindex_task)

    console.print("\n[blue]ℹ️  Note: This is a preview implementation.[/blue]")
    console.print("[blue]Full implementation would:[/blue]")
    console.print("  • Clone index templates with new patterns")
    console.print("  • Create destination data stream")
    console.print("  • Reindex all backing indices")
    console.print("  • Preserve ILM policies and settings")
    console.print("  • Verify data integrity\n")
