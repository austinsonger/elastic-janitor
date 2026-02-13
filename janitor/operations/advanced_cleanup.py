"""
Advanced Cleanup Features for Elastic Janitor.
Provides advanced cleanup operations including orphaned documents, field-level cleanup,
mapping cleanup, wildcard deletion, time-series gap detection, and duplicate detection.
"""
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import fnmatch
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, PROTECT_SYSTEM, MAX_DELETE_LIMIT, DRY_RUN_MODE
from ..utils import (
    safe_input, is_system, confirm_delete, confirm_action, show_breadcrumb,
    size_to_bytes, bytes_to_human, get_number_input, get_text_input, select_from_list
)


def option_orphaned_document_cleanup(es):
    """Remove documents matching specific criteria with preview."""
    show_breadcrumb(["Main Menu", "Advanced Cleanup Features", "Orphaned Document Cleanup"])

    console.print("[cyan]Configure document cleanup criteria[/cyan]\n")

    # Get index pattern
    index_pattern = get_text_input("Index pattern (e.g., logs-*, my-index):", default="*")
    if not index_pattern:
        return

    # Get field name to check
    field_name = get_text_input("Field name to check for null/missing values:")
    if not field_name:
        return

    # Optional: date range filter
    use_date_filter = confirm_action("Add date range filter?")
    date_field = None
    days_old = None

    if use_date_filter:
        date_field = get_text_input("Date field name (e.g., @timestamp):", default="@timestamp")
        days_old = get_number_input("Documents older than (days):", default=90, min_val=1)
        if not date_field or days_old is None:
            return

    # Build query
    must_not = [{"exists": {"field": field_name}}]

    if use_date_filter and date_field and days_old:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
        must_not.append({
            "range": {
                date_field: {
                    "gte": cutoff.isoformat()
                }
            }
        })

    query = {
        "query": {
            "bool": {
                "must_not": must_not
            }
        }
    }

    # Preview matching documents
    console.print("\n[cyan]Searching for matching documents...[/cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Counting documents..."),
            transient=True,
        ) as progress:
            progress.add_task("count", total=None)
            count_result = es.count(index=index_pattern, body=query)

        total_count = count_result.get("count", 0)

        if total_count == 0:
            console.print("[yellow]🟡 No documents match the criteria.[/yellow]\n")
            return

        # Get sample documents
        sample_result = es.search(index=index_pattern, body=query, size=5)
        sample_docs = sample_result.get("hits", {}).get("hits", [])

        # Display preview
        console.print()
        table = Table(title="Orphaned Documents Preview", box=box.ROUNDED, title_style="bold yellow")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Total matching documents", f"[red]{total_count:,}[/red]")
        table.add_row("Index pattern", index_pattern)
        table.add_row("Missing field", field_name)
        if use_date_filter:
            table.add_row("Date filter", f"Older than {days_old} days")

        console.print(table)
        console.print()

        # Show sample documents
        if sample_docs:
            console.print("[cyan]Sample documents (first 5):[/cyan]\n")
            for i, doc in enumerate(sample_docs[:5], 1):
                console.print(f"[yellow]{i}. Index:[/yellow] {doc['_index']}")
                console.print(f"   [yellow]ID:[/yellow] {doc['_id']}")
                console.print(f"   [yellow]Source:[/yellow] {str(doc.get('_source', {}))[:200]}...")
                console.print()

        # Confirm deletion
        if not confirm_action(f"Delete {total_count:,} documents?"):
            console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if DRY_RUN_MODE:
            console.print("[yellow]🔍 DRY-RUN MODE: Would delete documents but no action taken.[/yellow]\n")
            return

        # Perform deletion
        console.print("\n[cyan]Deleting documents...[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Deleting..."),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("delete", total=100)

            delete_result = es.delete_by_query(
                index=index_pattern,
                body=query,
                conflicts="proceed",
                wait_for_completion=True
            )

            progress.update(task, completed=100)

        deleted = delete_result.get("deleted", 0)
        console.print(f"\n[green]✅ Successfully deleted {deleted:,} documents.[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_field_level_cleanup(es):
    """Enable bulk removal of specific fields from documents."""
    show_breadcrumb(["Main Menu", "Advanced Cleanup Features", "Field-Level Cleanup"])

    console.print("[cyan]Configure field removal[/cyan]\n")

    # Get index pattern
    index_pattern = get_text_input("Index pattern (e.g., logs-*, my-index):", default="*")
    if not index_pattern:
        return

    # Get fields to remove
    console.print("\n[yellow]Enter field names to remove (comma-separated):[/yellow]")
    fields_input = get_text_input("Fields:")
    if not fields_input:
        return

    fields_to_remove = [f.strip() for f in fields_input.split(",") if f.strip()]

    if not fields_to_remove:
        console.print("[yellow]⚠️  No fields specified.[/yellow]\n")
        return

    # Get affected indices
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing indices..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            # Get matching indices
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index,docs.count,store.size")

        if not indices_response:
            console.print("[yellow]🟡 No matching indices found.[/yellow]\n")
            return

        # Filter out system indices if protected
        indices = []
        total_docs = 0
        total_size = 0

        for idx in indices_response:
            idx_name = idx.get("index")
            if PROTECT_SYSTEM and is_system(idx_name):
                continue

            doc_count = int(idx.get("docs.count", 0) or 0)
            size_str = idx.get("store.size", "0b")
            size_bytes = size_to_bytes(size_str)

            indices.append({
                "name": idx_name,
                "docs": doc_count,
                "size": size_str,
                "size_bytes": size_bytes
            })
            total_docs += doc_count
            total_size += size_bytes

        if not indices:
            console.print("[yellow]🟡 No eligible indices found.[/yellow]\n")
            return

        # Display preview
        console.print()
        table = Table(title="Field Removal Preview", box=box.ROUNDED, title_style="bold yellow")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Matching indices", str(len(indices)))
        table.add_row("Total documents", f"{total_docs:,}")
        table.add_row("Total size", bytes_to_human(total_size))
        table.add_row("Fields to remove", ", ".join(fields_to_remove))

        console.print(table)
        console.print()

        # Show sample indices
        console.print("[cyan]Sample indices (first 10):[/cyan]\n")
        for idx in indices[:10]:
            console.print(f"  • {idx['name']} ({idx['docs']:,} docs, {idx['size']})")

        if len(indices) > 10:
            console.print(f"\n  ... and {len(indices) - 10} more\n")
        else:
            console.print()

        # Confirm operation
        if not confirm_action(f"Remove fields from {len(indices)} indices?"):
            console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if DRY_RUN_MODE:
            console.print("[yellow]🔍 DRY-RUN MODE: Would remove fields but no action taken.[/yellow]\n")
            return

        # Build update script
        script_source = "for (field in params.fields) { ctx._source.remove(field); }"

        # Perform field removal
        console.print("\n[cyan]Removing fields...[/cyan]\n")

        success_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Processing indices..."),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("remove", total=len(indices))

            for idx in indices:
                try:
                    result = es.update_by_query(
                        index=idx["name"],
                        body={
                            "script": {
                                "source": script_source,
                                "lang": "painless",
                                "params": {
                                    "fields": fields_to_remove
                                }
                            },
                            "query": {"match_all": {}}
                        },
                        conflicts="proceed",
                        wait_for_completion=True
                    )

                    updated = result.get("updated", 0)
                    if updated > 0:
                        success_count += 1

                except Exception as e:
                    console.print(f"[red]Error processing {idx['name']}: {str(e)}[/red]")
                    error_count += 1

                progress.update(task, advance=1)

        console.print(f"\n[green]✅ Successfully processed {success_count} indices.[/green]")
        if error_count > 0:
            console.print(f"[red]❌ Failed to process {error_count} indices.[/red]")
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_mapping_cleanup(es):
    """Identify and optionally remove unused fields from index mappings."""
    show_breadcrumb(["Main Menu", "Advanced Cleanup Features", "Mapping Cleanup"])

    console.print("[cyan]Analyze index mappings for unused fields[/cyan]\n")

    # Get index pattern
    index_pattern = get_text_input("Index pattern (e.g., logs-*, my-index):", default="*")
    if not index_pattern:
        return

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing mappings..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            # Get matching indices
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index")

        if not indices_response:
            console.print("[yellow]🟡 No matching indices found.[/yellow]\n")
            return

        # Filter out system indices
        indices = []
        for idx in indices_response:
            idx_name = idx.get("index")
            if PROTECT_SYSTEM and is_system(idx_name):
                continue
            indices.append(idx_name)

        if not indices:
            console.print("[yellow]🟡 No eligible indices found.[/yellow]\n")
            return

        console.print(f"\n[cyan]Analyzing {len(indices)} indices...[/cyan]\n")

        # Analyze each index
        unused_fields_report = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Scanning indices..."),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("scan", total=len(indices))

            for idx_name in indices:
                try:
                    # Get mapping
                    mapping_response = es.indices.get_mapping(index=idx_name)
                    mapping = mapping_response.get(idx_name, {}).get("mappings", {})
                    properties = mapping.get("properties", {})

                    if not properties:
                        progress.update(task, advance=1)
                        continue

                    # Get field stats
                    field_caps = es.field_caps(index=idx_name, fields="*")
                    existing_fields = set(field_caps.get("fields", {}).keys())

                    # Find unused fields
                    unused = []
                    for field_name in properties.keys():
                        # Check if field has any documents
                        try:
                            count_result = es.count(
                                index=idx_name,
                                body={
                                    "query": {
                                        "exists": {"field": field_name}
                                    }
                                }
                            )

                            if count_result.get("count", 0) == 0:
                                unused.append(field_name)
                        except:
                            # Field might not be searchable
                            pass

                    if unused:
                        unused_fields_report.append({
                            "index": idx_name,
                            "unused_fields": unused,
                            "total_fields": len(properties)
                        })

                except Exception as e:
                    console.print(f"[red]Error analyzing {idx_name}: {str(e)}[/red]")

                progress.update(task, advance=1)

        # Display results
        if not unused_fields_report:
            console.print("\n[green]✅ No unused fields found in any index.[/green]\n")
            return

        console.print()
        table = Table(title="Unused Fields Report", box=box.ROUNDED, title_style="bold yellow")
        table.add_column("Index", style="cyan")
        table.add_column("Total Fields", justify="right", style="blue")
        table.add_column("Unused Fields", justify="right", style="red")
        table.add_column("Unused Field Names", style="yellow")

        for report in unused_fields_report[:20]:
            table.add_row(
                report["index"],
                str(report["total_fields"]),
                str(len(report["unused_fields"])),
                ", ".join(report["unused_fields"][:5]) + ("..." if len(report["unused_fields"]) > 5 else "")
            )

        if len(unused_fields_report) > 20:
            table.add_row("...", "...", "...", f"... and {len(unused_fields_report) - 20} more indices")

        console.print(table)
        console.print()

        console.print("[yellow]ℹ️  Note: Removing fields from mappings requires reindexing.[/yellow]")
        console.print("[yellow]   This operation will create a report only.[/yellow]\n")

        # Option to export report
        if confirm_action("Export detailed report to file?"):
            filename = f"unused_fields_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w") as f:
                f.write("Unused Fields Report\n")
                f.write("=" * 80 + "\n\n")
                for report in unused_fields_report:
                    f.write(f"Index: {report['index']}\n")
                    f.write(f"Total Fields: {report['total_fields']}\n")
                    f.write(f"Unused Fields ({len(report['unused_fields'])}):\n")
                    for field in report['unused_fields']:
                        f.write(f"  - {field}\n")
                    f.write("\n")

            console.print(f"[green]✅ Report saved to {filename}[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_wildcard_index_deletion(es):
    """Delete indices matching complex wildcard patterns with enhanced safety checks."""
    show_breadcrumb(["Main Menu", "Advanced Cleanup Features", "Wildcard Index Deletion"])

    console.print("[cyan]Configure wildcard index deletion[/cyan]\n")
    console.print("[yellow]⚠️  This is a powerful operation. Use with caution![/yellow]\n")

    # Get wildcard patterns
    console.print("Enter wildcard patterns (comma-separated)")
    console.print("Examples: logs-*-2023-*, temp-*, old-data-*\n")
    patterns_input = get_text_input("Patterns:")
    if not patterns_input:
        return

    patterns = [p.strip() for p in patterns_input.split(",") if p.strip()]

    if not patterns:
        console.print("[yellow]⚠️  No patterns specified.[/yellow]\n")
        return

    try:
        # Get all indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            all_indices = es.cat.indices(format="json", h="index,docs.count,store.size")

        # Match indices against patterns
        matching_indices = []
        total_docs = 0
        total_size = 0

        for idx in all_indices:
            idx_name = idx.get("index")

            # Check if protected
            if PROTECT_SYSTEM and is_system(idx_name):
                continue

            # Check if matches any pattern
            matches = False
            for pattern in patterns:
                if fnmatch.fnmatch(idx_name, pattern):
                    matches = True
                    break

            if matches:
                doc_count = int(idx.get("docs.count", 0) or 0)
                size_str = idx.get("store.size", "0b")
                size_bytes = size_to_bytes(size_str)

                matching_indices.append({
                    "name": idx_name,
                    "docs": doc_count,
                    "size": size_str,
                    "size_bytes": size_bytes
                })
                total_docs += doc_count
                total_size += size_bytes

        if not matching_indices:
            console.print("[yellow]🟡 No indices match the specified patterns.[/yellow]\n")
            return

        # Check MAX_DELETE_LIMIT
        if len(matching_indices) > MAX_DELETE_LIMIT:
            console.print(f"\n[red]❌ Error: Matched {len(matching_indices)} indices, exceeds MAX_DELETE_LIMIT ({MAX_DELETE_LIMIT}).[/red]")
            console.print("[yellow]   Please use more specific patterns or increase MAX_DELETE_LIMIT.[/yellow]\n")
            return

        # Sort by name
        matching_indices.sort(key=lambda x: x["name"])

        # Display preview
        console.print()
        table = Table(title="Wildcard Deletion Preview", box=box.ROUNDED, title_style="bold red")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Patterns", ", ".join(patterns))
        table.add_row("Matching indices", f"[red]{len(matching_indices)}[/red]")
        table.add_row("Total documents", f"[red]{total_docs:,}[/red]")
        table.add_row("Total size", f"[red]{bytes_to_human(total_size)}[/red]")

        console.print(table)
        console.print()

        # Show matching indices
        console.print("[cyan]Matching indices:[/cyan]\n")
        for idx in matching_indices[:50]:
            console.print(f"  • {idx['name']} ({idx['docs']:,} docs, {idx['size']})")

        if len(matching_indices) > 50:
            console.print(f"\n  ... and {len(matching_indices) - 50} more\n")
        else:
            console.print()

        # Enhanced confirmation
        console.print("[red]⚠️  WARNING: This will permanently delete these indices![/red]\n")

        if not confirm_action(f"Proceed with deletion of {len(matching_indices)} indices?"):
            console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Require typing DELETE for extra safety
        if not confirm_delete():
            console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if DRY_RUN_MODE:
            console.print("[yellow]🔍 DRY-RUN MODE: Would delete indices but no action taken.[/yellow]\n")
            return

        # Perform deletion
        console.print("\n[cyan]Deleting indices...[/cyan]\n")

        success_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Deleting..."),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("delete", total=len(matching_indices))

            for idx in matching_indices:
                try:
                    es.indices.delete(index=idx["name"])
                    success_count += 1
                except Exception as e:
                    console.print(f"[red]Error deleting {idx['name']}: {str(e)}[/red]")
                    error_count += 1

                progress.update(task, advance=1)

        console.print(f"\n[green]✅ Successfully deleted {success_count} indices.[/green]")
        if error_count > 0:
            console.print(f"[red]❌ Failed to delete {error_count} indices.[/red]")
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_timeseries_gap_detector(es):
    """Analyze time-series indices/data streams to find missing time periods."""
    show_breadcrumb(["Main Menu", "Advanced Cleanup Features", "Time-Series Gap Detector"])

    console.print("[cyan]Analyze time-series data for gaps[/cyan]\n")

    # Get index pattern
    index_pattern = get_text_input("Index pattern (e.g., logs-*, metrics-*):", default="*")
    if not index_pattern:
        return

    # Get date field
    date_field = get_text_input("Date field name:", default="@timestamp")
    if not date_field:
        return

    # Get expected interval
    console.print("\nExpected time interval:")
    console.print("1) Hourly")
    console.print("2) Daily")
    console.print("3) Weekly")
    interval_choice = get_text_input("Select interval (1-3):", default="2")

    interval_map = {
        "1": ("1h", timedelta(hours=1), "hourly"),
        "2": ("1d", timedelta(days=1), "daily"),
        "3": ("1w", timedelta(weeks=1), "weekly")
    }

    if interval_choice not in interval_map:
        console.print("[yellow]⚠️  Invalid interval choice.[/yellow]\n")
        return

    interval_str, interval_delta, interval_name = interval_map[interval_choice]

    # Get time range
    days_back = get_number_input("Analyze last N days:", default=30, min_val=1)
    if days_back is None:
        return

    try:
        start_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        end_time = datetime.now(timezone.utc)

        console.print(f"\n[cyan]Analyzing {interval_name} data from {start_time.date()} to {end_time.date()}...[/cyan]\n")

        # Get date histogram aggregation
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching time-series data..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)

            agg_query = {
                "size": 0,
                "query": {
                    "range": {
                        date_field: {
                            "gte": start_time.isoformat(),
                            "lte": end_time.isoformat()
                        }
                    }
                },
                "aggs": {
                    "time_buckets": {
                        "date_histogram": {
                            "field": date_field,
                            "fixed_interval": interval_str,
                            "min_doc_count": 0,
                            "extended_bounds": {
                                "min": start_time.isoformat(),
                                "max": end_time.isoformat()
                            }
                        }
                    }
                }
            }

            result = es.search(index=index_pattern, body=agg_query)

        buckets = result.get("aggregations", {}).get("time_buckets", {}).get("buckets", [])

        if not buckets:
            console.print("[yellow]🟡 No data found in the specified time range.[/yellow]\n")
            return

        # Find gaps (buckets with 0 documents)
        gaps = []
        total_buckets = len(buckets)
        buckets_with_data = 0

        for bucket in buckets:
            doc_count = bucket.get("doc_count", 0)
            timestamp = bucket.get("key_as_string") or bucket.get("key")

            if doc_count == 0:
                gaps.append({
                    "timestamp": timestamp,
                    "datetime": datetime.fromtimestamp(bucket.get("key") / 1000, tz=timezone.utc)
                })
            else:
                buckets_with_data += 1

        # Display results
        console.print()
        table = Table(title="Time-Series Gap Analysis", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Index pattern", index_pattern)
        table.add_row("Date field", date_field)
        table.add_row("Interval", interval_name)
        table.add_row("Analysis period", f"{start_time.date()} to {end_time.date()}")
        table.add_row("Total time buckets", str(total_buckets))
        table.add_row("Buckets with data", f"[green]{buckets_with_data}[/green]")
        table.add_row("Gaps detected", f"[red]{len(gaps)}[/red]")

        if total_buckets > 0:
            coverage_pct = (buckets_with_data / total_buckets) * 100
            table.add_row("Data coverage", f"{coverage_pct:.1f}%")

        console.print(table)
        console.print()

        if gaps:
            console.print(f"[yellow]⚠️  Found {len(gaps)} gaps in time-series data[/yellow]\n")

            # Show first 20 gaps
            console.print("[cyan]Detected gaps (first 20):[/cyan]\n")
            for gap in gaps[:20]:
                console.print(f"  • {gap['datetime'].strftime('%Y-%m-%d %H:%M:%S UTC')}")

            if len(gaps) > 20:
                console.print(f"\n  ... and {len(gaps) - 20} more gaps\n")
            else:
                console.print()

            # Option to export report
            if confirm_action("Export detailed gap report to file?"):
                filename = f"timeseries_gaps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(filename, "w") as f:
                    f.write("Time-Series Gap Analysis Report\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Index Pattern: {index_pattern}\n")
                    f.write(f"Date Field: {date_field}\n")
                    f.write(f"Interval: {interval_name}\n")
                    f.write(f"Analysis Period: {start_time.date()} to {end_time.date()}\n")
                    f.write(f"Total Gaps: {len(gaps)}\n\n")
                    f.write("Detected Gaps:\n")
                    f.write("-" * 80 + "\n")
                    for gap in gaps:
                        f.write(f"{gap['datetime'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

                console.print(f"[green]✅ Report saved to {filename}[/green]\n")
        else:
            console.print("[green]✅ No gaps detected! Time-series data is complete.[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_duplicate_document_detector(es):
    """Find and optionally remove duplicate documents based on configurable field combinations."""
    show_breadcrumb(["Main Menu", "Advanced Cleanup Features", "Duplicate Document Detector"])

    console.print("[cyan]Configure duplicate document detection[/cyan]\n")

    # Get index pattern
    index_pattern = get_text_input("Index pattern (e.g., logs-*, my-index):", default="*")
    if not index_pattern:
        return

    # Get fields for duplicate detection
    console.print("\n[yellow]Enter field names to use for duplicate detection (comma-separated):[/yellow]")
    console.print("Example: user_id,event_type,timestamp\n")
    fields_input = get_text_input("Fields:")
    if not fields_input:
        return

    fields = [f.strip() for f in fields_input.split(",") if f.strip()]

    if not fields:
        console.print("[yellow]⚠️  No fields specified.[/yellow]\n")
        return

    try:
        console.print(f"\n[cyan]Searching for duplicates based on: {', '.join(fields)}...[/cyan]\n")

        # Build aggregation query to find duplicates
        # Create composite key from fields
        script_parts = []
        for field in fields:
            script_parts.append(f"(doc['{field}'].size() > 0 ? doc['{field}'].value.toString() : 'null')")

        script_source = " + '|' + ".join(script_parts)

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing documents..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            agg_query = {
                "size": 0,
                "aggs": {
                    "duplicates": {
                        "terms": {
                            "script": {
                                "source": script_source,
                                "lang": "painless"
                            },
                            "size": 10000,
                            "min_doc_count": 2
                        },
                        "aggs": {
                            "duplicate_docs": {
                                "top_hits": {
                                    "size": 100,
                                    "_source": False,
                                    "docvalue_fields": fields
                                }
                            }
                        }
                    }
                }
            }

            result = es.search(index=index_pattern, body=agg_query)

        duplicate_buckets = result.get("aggregations", {}).get("duplicates", {}).get("buckets", [])

        if not duplicate_buckets:
            console.print("[green]✅ No duplicate documents found.[/green]\n")
            return

        # Calculate statistics
        total_duplicate_groups = len(duplicate_buckets)
        total_duplicate_docs = sum(bucket.get("doc_count", 0) for bucket in duplicate_buckets)
        total_redundant_docs = sum(bucket.get("doc_count", 0) - 1 for bucket in duplicate_buckets)

        # Display results
        console.print()
        table = Table(title="Duplicate Documents Analysis", box=box.ROUNDED, title_style="bold yellow")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Index pattern", index_pattern)
        table.add_row("Detection fields", ", ".join(fields))
        table.add_row("Duplicate groups found", f"[yellow]{total_duplicate_groups}[/yellow]")
        table.add_row("Total duplicate documents", f"[yellow]{total_duplicate_docs}[/yellow]")
        table.add_row("Redundant documents", f"[red]{total_redundant_docs}[/red]")

        console.print(table)
        console.print()

        # Show sample duplicates
        console.print("[cyan]Sample duplicate groups (first 10):[/cyan]\n")
        for i, bucket in enumerate(duplicate_buckets[:10], 1):
            count = bucket.get("doc_count", 0)
            key = bucket.get("key", "")
            console.print(f"[yellow]{i}. Duplicate group:[/yellow] {count} documents")
            console.print(f"   [yellow]Key:[/yellow] {key}")

            # Show sample document IDs
            hits = bucket.get("duplicate_docs", {}).get("hits", {}).get("hits", [])
            if hits:
                doc_ids = [hit.get("_id") for hit in hits[:5]]
                console.print(f"   [yellow]Sample IDs:[/yellow] {', '.join(doc_ids[:3])}...")
            console.print()

        if total_duplicate_groups > 10:
            console.print(f"... and {total_duplicate_groups - 10} more duplicate groups\n")

        # Ask if user wants to remove duplicates
        if not confirm_action(f"Remove {total_redundant_docs} redundant documents?"):
            console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Ask which duplicates to keep
        console.print("\n[cyan]Which duplicate to keep?[/cyan]")
        console.print("1) Keep newest (by _id)")
        console.print("2) Keep oldest (by _id)")
        keep_choice = get_text_input("Select option (1-2):", default="1")

        if keep_choice not in ["1", "2"]:
            console.print("[yellow]⚠️  Invalid choice.[/yellow]\n")
            return

        keep_newest = (keep_choice == "1")

        if DRY_RUN_MODE:
            console.print("[yellow]🔍 DRY-RUN MODE: Would remove duplicates but no action taken.[/yellow]\n")
            return

        # Remove duplicates
        console.print("\n[cyan]Removing duplicate documents...[/cyan]\n")

        deleted_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Processing duplicates..."),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("remove", total=total_duplicate_groups)

            for bucket in duplicate_buckets:
                try:
                    hits = bucket.get("duplicate_docs", {}).get("hits", {}).get("hits", [])

                    if len(hits) < 2:
                        progress.update(task, advance=1)
                        continue

                    # Sort by _id to determine which to keep
                    sorted_hits = sorted(hits, key=lambda x: x.get("_id", ""))

                    if keep_newest:
                        # Keep last, delete others
                        to_delete = sorted_hits[:-1]
                    else:
                        # Keep first, delete others
                        to_delete = sorted_hits[1:]

                    # Delete documents
                    for hit in to_delete:
                        try:
                            es.delete(
                                index=hit.get("_index"),
                                id=hit.get("_id")
                            )
                            deleted_count += 1
                        except Exception as e:
                            error_count += 1

                except Exception as e:
                    console.print(f"[red]Error processing duplicate group: {str(e)}[/red]")
                    error_count += 1

                progress.update(task, advance=1)

        console.print(f"\n[green]✅ Successfully deleted {deleted_count} duplicate documents.[/green]")
        if error_count > 0:
            console.print(f"[red]❌ Failed to delete {error_count} documents.[/red]")
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")
