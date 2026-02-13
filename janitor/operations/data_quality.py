"""
Data Quality & Validation operations for Elastic Janitor.
Analyze data quality issues including missing fields, type inconsistencies,
null values, and high cardinality fields.
"""
from collections import defaultdict
import fnmatch
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, DRY_RUN_MODE
from ..utils import (
    show_breadcrumb, safe_input, confirm_action, get_number_input,
    get_text_input, is_system, get_index_pattern_selection
)
from ..utils.formatters import bytes_to_human


def option_missing_field_analyzer(es):
    """Analyze documents across indices to identify missing required fields."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Missing Field Analyzer"])

    console.print("\n[cyan]Analyzing missing required fields...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get required fields
    console.print("\n[yellow]Enter required field names (comma-separated):[/yellow]")
    fields_input = safe_input("Required fields: ").strip()

    if not fields_input:
        console.print("\n[yellow]⚠️  No fields specified.[/yellow]\n")
        return

    required_fields = [f.strip() for f in fields_input.split(",") if f.strip()]

    if not required_fields:
        console.print("\n[yellow]⚠️  No valid fields specified.[/yellow]\n")
        return

    try:
        # Get matching indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index,docs.count")

        indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if is_system(index_name):
                continue
            doc_count = int(idx.get("docs.count", "0") or 0)
            if doc_count > 0:
                indices.append({"name": index_name, "doc_count": doc_count})

        if not indices:
            console.print("\n[yellow]🟡 No matching indices found.[/yellow]\n")
            return

        console.print(f"\n[cyan]Found {len(indices)} indices to analyze[/cyan]\n")

        # Confirm before proceeding
        if not confirm_action(f"Analyze {len(indices)} indices for missing fields?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Analyze each index
        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Analyzing indices...", total=len(indices))

            for idx_info in indices:
                index_name = idx_info["name"]
                doc_count = idx_info["doc_count"]

                progress.update(task, description=f"[cyan]Analyzing: {index_name[:50]}...")

                field_stats = {}

                for field in required_fields:
                    # Count documents missing this field
                    try:
                        query = {
                            "query": {
                                "bool": {
                                    "must_not": {
                                        "exists": {"field": field}
                                    }
                                }
                            }
                        }

                        count_response = es.count(index=index_name, body=query)
                        missing_count = count_response.get("count", 0)
                        missing_pct = (missing_count / doc_count * 100) if doc_count > 0 else 0

                        field_stats[field] = {
                            "missing": missing_count,
                            "percentage": missing_pct
                        }
                    except Exception as e:
                        field_stats[field] = {
                            "missing": "ERROR",
                            "percentage": 0,
                            "error": str(e)
                        }

                results.append({
                    "index": index_name,
                    "doc_count": doc_count,
                    "field_stats": field_stats
                })

                progress.advance(task)

        # Display results
        console.print("\n")
        table = Table(
            title="Missing Field Analysis Results",
            box=box.ROUNDED,
            title_style="bold cyan"
        )

        table.add_column("Index", style="cyan", no_wrap=True)
        table.add_column("Total Docs", style="white", justify="right")

        for field in required_fields:
            table.add_column(f"{field}\n(Missing)", style="yellow", justify="right")
            table.add_column(f"{field}\n(%)", style="red", justify="right")

        for result in results:
            row = [
                result["index"],
                f"{result['doc_count']:,}"
            ]

            for field in required_fields:
                stats = result["field_stats"].get(field, {})
                if "error" in stats:
                    row.append("ERROR")
                    row.append("-")
                else:
                    missing = stats.get("missing", 0)
                    pct = stats.get("percentage", 0)
                    row.append(f"{missing:,}")
                    row.append(f"{pct:.1f}%")

            table.add_row(*row)

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not analyze missing fields: {e}[/red]\n")


def option_data_type_inconsistency_detector(es):
    """Find type conflicts and mapping inconsistencies across indices."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Data Type Inconsistency Detector"])

    console.print("\n[cyan]Detecting data type inconsistencies...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    try:
        # Get matching indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index")

        indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if is_system(index_name):
                continue
            indices.append(index_name)

        if not indices:
            console.print("\n[yellow]🟡 No matching indices found.[/yellow]\n")
            return

        console.print(f"\n[cyan]Found {len(indices)} indices to analyze[/cyan]\n")

        # Confirm before proceeding
        if not confirm_action(f"Analyze mappings for {len(indices)} indices?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Fetch mappings for all indices
        field_types = defaultdict(lambda: defaultdict(list))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Fetching mappings...", total=len(indices))

            for index_name in indices:
                progress.update(task, description=f"[cyan]Fetching: {index_name[:50]}...")

                try:
                    mapping = es.indices.get_mapping(index=index_name)

                    # Extract field types from mapping
                    index_mapping = mapping.get(index_name, {}).get("mappings", {})
                    properties = index_mapping.get("properties", {})

                    def extract_fields(props, prefix=""):
                        for field_name, field_def in props.items():
                            full_name = f"{prefix}{field_name}" if prefix else field_name
                            field_type = field_def.get("type", "object")

                            if field_type:
                                field_types[full_name][field_type].append(index_name)

                            # Recursively process nested fields
                            if "properties" in field_def:
                                extract_fields(field_def["properties"], f"{full_name}.")

                    extract_fields(properties)

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not fetch mapping for {index_name}: {e}[/yellow]")

                progress.advance(task)

        # Find fields with type conflicts
        conflicts = []
        for field_name, types_dict in field_types.items():
            if len(types_dict) > 1:
                conflicts.append({
                    "field": field_name,
                    "types": types_dict
                })

        if not conflicts:
            console.print("\n[green]✅ No type inconsistencies found![/green]\n")
            return

        # Display conflicts
        console.print(f"\n[yellow]⚠️  Found {len(conflicts)} fields with type conflicts[/yellow]\n")

        for conflict in conflicts:
            field_name = conflict["field"]
            types_dict = conflict["types"]

            panel_content = ""
            for field_type, index_list in types_dict.items():
                panel_content += f"[cyan]{field_type}[/cyan]: {len(index_list)} indices\n"
                for idx in index_list[:5]:  # Show first 5 indices
                    panel_content += f"  • {idx}\n"
                if len(index_list) > 5:
                    panel_content += f"  ... and {len(index_list) - 5} more\n"

            console.print(Panel(
                panel_content.strip(),
                title=f"[bold red]⚠️  Field: {field_name}[/bold red]",
                box=box.ROUNDED,
                border_style="red"
            ))
            console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not detect type inconsistencies: {e}[/red]\n")



def option_null_value_statistics(es):
    """Analyze the prevalence of null/empty fields."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Null Value Statistics"])

    console.print("\n[cyan]Analyzing null value statistics...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get threshold
    threshold = get_number_input(
        "Flag fields with null rate above (%):",
        default=50,
        min_val=0,
        max_val=100
    )

    if threshold is None:
        return

    try:
        # Get matching indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index,docs.count")

        indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if is_system(index_name):
                continue
            doc_count = int(idx.get("docs.count", "0") or 0)
            if doc_count > 0:
                indices.append({"name": index_name, "doc_count": doc_count})

        if not indices:
            console.print("\n[yellow]🟡 No matching indices found.[/yellow]\n")
            return

        console.print(f"\n[cyan]Found {len(indices)} indices to analyze[/cyan]\n")

        # Confirm before proceeding
        if not confirm_action(f"Analyze null values for {len(indices)} indices?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Analyze each index
        all_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Analyzing indices...", total=len(indices))

            for idx_info in indices:
                index_name = idx_info["name"]
                doc_count = idx_info["doc_count"]

                progress.update(task, description=f"[cyan]Analyzing: {index_name[:50]}...")

                try:
                    # Get field mappings
                    mapping = es.indices.get_mapping(index=index_name)
                    index_mapping = mapping.get(index_name, {}).get("mappings", {})
                    properties = index_mapping.get("properties", {})

                    # Get field stats using field_caps API
                    field_caps = es.field_caps(index=index_name, fields="*")

                    field_results = []

                    for field_name in field_caps.get("fields", {}).keys():
                        # Skip metadata fields
                        if field_name.startswith("_"):
                            continue

                        try:
                            # Count documents with this field
                            exists_query = {
                                "query": {
                                    "exists": {"field": field_name}
                                }
                            }
                            exists_count = es.count(index=index_name, body=exists_query).get("count", 0)

                            # Calculate null percentage
                            null_count = doc_count - exists_count
                            null_pct = (null_count / doc_count * 100) if doc_count > 0 else 0

                            if null_pct >= threshold:
                                # Estimate storage savings
                                stats = es.indices.stats(index=index_name)
                                total_size = stats["indices"][index_name]["total"]["store"]["size_in_bytes"]
                                estimated_savings = total_size * (null_pct / 100)

                                field_results.append({
                                    "field": field_name,
                                    "null_count": null_count,
                                    "null_pct": null_pct,
                                    "estimated_savings": estimated_savings
                                })
                        except Exception:
                            # Skip fields that cause errors
                            pass

                    if field_results:
                        all_results.append({
                            "index": index_name,
                            "doc_count": doc_count,
                            "fields": sorted(field_results, key=lambda x: x["null_pct"], reverse=True)
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        if not all_results:
            console.print(f"\n[green]✅ No fields found with null rate above {threshold}%[/green]\n")
            return

        # Display results
        console.print(f"\n[yellow]⚠️  Found sparse fields (null rate > {threshold}%)[/yellow]\n")

        for result in all_results:
            index_name = result["index"]
            doc_count = result["doc_count"]
            fields = result["fields"]

            table = Table(
                title=f"Index: {index_name} ({doc_count:,} docs)",
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            table.add_column("Field", style="cyan")
            table.add_column("Null Count", style="yellow", justify="right")
            table.add_column("Null %", style="red", justify="right")
            table.add_column("Est. Savings", style="green", justify="right")

            for field_info in fields[:20]:  # Show top 20
                table.add_row(
                    field_info["field"],
                    f"{field_info['null_count']:,}",
                    f"{field_info['null_pct']:.1f}%",
                    bytes_to_human(field_info["estimated_savings"])
                )

            console.print(table)
            console.print()

            if len(fields) > 20:
                console.print(f"[dim]... and {len(fields) - 20} more fields[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not analyze null values: {e}[/red]\n")



def option_cardinality_analysis(es):
    """Identify high-cardinality fields that may affect performance."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Cardinality Analysis"])

    console.print("\n[cyan]Analyzing field cardinality...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get threshold
    threshold = get_number_input(
        "Flag fields with cardinality above:",
        default=10000,
        min_val=1
    )

    if threshold is None:
        return

    # Get sample size
    sample_size = get_number_input(
        "Sample size for cardinality estimation (0 for all docs):",
        default=10000,
        min_val=0
    )

    if sample_size is None:
        return

    try:
        # Get matching indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index,docs.count")

        indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if is_system(index_name):
                continue
            doc_count = int(idx.get("docs.count", "0") or 0)
            if doc_count > 0:
                indices.append({"name": index_name, "doc_count": doc_count})

        if not indices:
            console.print("\n[yellow]🟡 No matching indices found.[/yellow]\n")
            return

        console.print(f"\n[cyan]Found {len(indices)} indices to analyze[/cyan]\n")

        # Confirm before proceeding
        if not confirm_action(f"Analyze cardinality for {len(indices)} indices?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Analyze each index
        all_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Analyzing indices...", total=len(indices))

            for idx_info in indices:
                index_name = idx_info["name"]
                doc_count = idx_info["doc_count"]

                progress.update(task, description=f"[cyan]Analyzing: {index_name[:50]}...")

                try:
                    # Get field mappings to identify keyword/text fields
                    mapping = es.indices.get_mapping(index=index_name)
                    index_mapping = mapping.get(index_name, {}).get("mappings", {})
                    properties = index_mapping.get("properties", {})

                    # Get field capabilities
                    field_caps = es.field_caps(index=index_name, fields="*")

                    high_cardinality_fields = []

                    for field_name, field_info in field_caps.get("fields", {}).items():
                        # Skip metadata fields
                        if field_name.startswith("_"):
                            continue

                        # Focus on keyword and text fields
                        field_types = list(field_info.keys())
                        if not any(t in ["keyword", "text"] for t in field_types):
                            continue

                        try:
                            # Use cardinality aggregation to estimate unique values
                            agg_query = {
                                "size": 0,
                                "aggs": {
                                    "unique_count": {
                                        "cardinality": {
                                            "field": field_name,
                                            "precision_threshold": 40000
                                        }
                                    }
                                }
                            }

                            # Add sampling if requested
                            if sample_size > 0 and doc_count > sample_size:
                                agg_query["query"] = {
                                    "function_score": {
                                        "query": {"match_all": {}},
                                        "random_score": {},
                                        "boost_mode": "replace"
                                    }
                                }
                                agg_query["size"] = 0
                                # Use a simple approach: just limit the aggregation
                                search_result = es.search(index=index_name, body=agg_query, size=0)
                            else:
                                search_result = es.search(index=index_name, body=agg_query)

                            cardinality = search_result["aggregations"]["unique_count"]["value"]

                            if cardinality >= threshold:
                                # Calculate cardinality ratio
                                cardinality_ratio = (cardinality / doc_count * 100) if doc_count > 0 else 0

                                # Estimate memory impact (rough estimate: 1KB per unique value)
                                memory_estimate = cardinality * 1024

                                # Determine field type
                                field_type = field_types[0] if field_types else "unknown"

                                high_cardinality_fields.append({
                                    "field": field_name,
                                    "cardinality": int(cardinality),
                                    "cardinality_ratio": cardinality_ratio,
                                    "field_type": field_type,
                                    "memory_estimate": memory_estimate
                                })
                        except Exception:
                            # Skip fields that cause errors (e.g., text fields without keyword)
                            pass

                    if high_cardinality_fields:
                        all_results.append({
                            "index": index_name,
                            "doc_count": doc_count,
                            "fields": sorted(high_cardinality_fields, key=lambda x: x["cardinality"], reverse=True)
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        if not all_results:
            console.print(f"\n[green]✅ No high-cardinality fields found (threshold: {threshold:,})[/green]\n")
            return

        # Display results
        console.print(f"\n[yellow]⚠️  Found high-cardinality fields (> {threshold:,} unique values)[/yellow]\n")

        for result in all_results:
            index_name = result["index"]
            doc_count = result["doc_count"]
            fields = result["fields"]

            table = Table(
                title=f"Index: {index_name} ({doc_count:,} docs)",
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            table.add_column("Field", style="cyan")
            table.add_column("Type", style="white")
            table.add_column("Unique Values", style="yellow", justify="right")
            table.add_column("Ratio", style="magenta", justify="right")
            table.add_column("Est. Memory", style="red", justify="right")
            table.add_column("Recommendation", style="green")

            for field_info in fields[:15]:  # Show top 15
                # Generate recommendation
                if field_info["cardinality_ratio"] > 80:
                    recommendation = "Consider text type"
                elif field_info["field_type"] == "keyword" and field_info["cardinality"] > 100000:
                    recommendation = "Exclude from aggs"
                else:
                    recommendation = "Monitor"

                table.add_row(
                    field_info["field"],
                    field_info["field_type"],
                    f"{field_info['cardinality']:,}",
                    f"{field_info['cardinality_ratio']:.1f}%",
                    bytes_to_human(field_info["memory_estimate"]),
                    recommendation
                )

            console.print(table)
            console.print()

            if len(fields) > 15:
                console.print(f"[dim]... and {len(fields) - 15} more fields[/dim]\n")

        # Display optimization suggestions
        console.print(Panel(
            "[bold cyan]Optimization Suggestions:[/bold cyan]\n\n"
            "• [yellow]Consider text type[/yellow]: Fields with very high cardinality ratio (>80%) "
            "might be better as 'text' type if full-text search is needed\n"
            "• [yellow]Exclude from aggs[/yellow]: High-cardinality keyword fields can be excluded "
            "from aggregations using 'eager_global_ordinals: false'\n"
            "• [yellow]Monitor[/yellow]: Keep an eye on these fields as they may impact performance",
            title="[bold green]💡 Tips[/bold green]",
            box=box.ROUNDED,
            border_style="green"
        ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not analyze cardinality: {e}[/red]\n")

