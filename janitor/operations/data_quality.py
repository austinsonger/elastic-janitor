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
from ..config import console, GOD_MODE
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


def option_timestamp_validation_detector(es):
    """Detect timestamp issues including missing @timestamp, future timestamps, ingestion lag, and precision loss."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Timestamp Validation & Drift Detector"])

    console.print("\n[cyan]Analyzing timestamp quality...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get lag threshold
    lag_threshold_minutes = get_number_input(
        "Flag documents with ingestion lag above (minutes):",
        default=60,
        min_val=1
    )

    if lag_threshold_minutes is None:
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
        if not confirm_action(f"Analyze timestamp quality for {len(indices)} indices?"):
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
                    issues = []

                    # 1. Check for missing @timestamp
                    missing_query = {
                        "query": {
                            "bool": {
                                "must_not": {"exists": {"field": "@timestamp"}}
                            }
                        }
                    }
                    missing_count = es.count(index=index_name, body=missing_query).get("count", 0)
                    missing_pct = (missing_count / doc_count * 100) if doc_count > 0 else 0

                    if missing_count > 0:
                        issues.append({
                            "type": "Missing @timestamp",
                            "count": missing_count,
                            "percentage": missing_pct,
                            "severity": "HIGH"
                        })

                    # 2. Check for future timestamps
                    future_query = {
                        "query": {
                            "range": {
                                "@timestamp": {"gte": "now"}
                            }
                        }
                    }
                    future_count = es.count(index=index_name, body=future_query).get("count", 0)
                    future_pct = (future_count / doc_count * 100) if doc_count > 0 else 0

                    if future_count > 0:
                        issues.append({
                            "type": "Future timestamps",
                            "count": future_count,
                            "percentage": future_pct,
                            "severity": "MEDIUM"
                        })

                    # 3. Check for ingestion lag (if event.ingested exists)
                    # First check if event.ingested field exists
                    field_caps = es.field_caps(index=index_name, fields="event.ingested,@timestamp")
                    has_ingested = "event.ingested" in field_caps.get("fields", {})

                    if has_ingested:
                        lag_query = {
                            "size": 0,
                            "query": {
                                "bool": {
                                    "must": [
                                        {"exists": {"field": "@timestamp"}},
                                        {"exists": {"field": "event.ingested"}}
                                    ]
                                }
                            },
                            "aggs": {
                                "lag_stats": {
                                    "stats": {
                                        "script": {
                                            "source": "(doc['event.ingested'].value.millis - doc['@timestamp'].value.millis) / 60000.0",
                                            "lang": "painless"
                                        }
                                    }
                                }
                            }
                        }

                        lag_result = es.search(index=index_name, body=lag_query)
                        lag_stats = lag_result.get("aggregations", {}).get("lag_stats", {})

                        if lag_stats.get("count", 0) > 0:
                            avg_lag = lag_stats.get("avg", 0)
                            max_lag = lag_stats.get("max", 0)

                            if avg_lag > lag_threshold_minutes:
                                issues.append({
                                    "type": "High ingestion lag",
                                    "count": f"Avg: {avg_lag:.1f}m, Max: {max_lag:.1f}m",
                                    "percentage": 0,
                                    "severity": "MEDIUM"
                                })

                    # 4. Check for timestamp precision loss (all ending in .000Z)
                    precision_query = {
                        "size": 100,
                        "query": {"exists": {"field": "@timestamp"}},
                        "_source": ["@timestamp"]
                    }

                    precision_result = es.search(index=index_name, body=precision_query)
                    hits = precision_result.get("hits", {}).get("hits", [])

                    if hits:
                        precision_loss_count = 0
                        for hit in hits:
                            timestamp_str = str(hit.get("_source", {}).get("@timestamp", ""))
                            if ".000Z" in timestamp_str or not "." in timestamp_str:
                                precision_loss_count += 1

                        precision_loss_pct = (precision_loss_count / len(hits) * 100)

                        if precision_loss_pct > 90:  # More than 90% have precision loss
                            issues.append({
                                "type": "Timestamp precision loss",
                                "count": f"{precision_loss_pct:.0f}% of samples",
                                "percentage": precision_loss_pct,
                                "severity": "LOW"
                            })

                    if issues:
                        all_results.append({
                            "index": index_name,
                            "doc_count": doc_count,
                            "issues": issues
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        if not all_results:
            console.print(f"\n[green]✅ No timestamp issues found![/green]\n")
            return

        # Display results
        console.print(f"\n[yellow]⚠️  Found timestamp issues in {len(all_results)} indices[/yellow]\n")

        for result in all_results:
            index_name = result["index"]
            doc_count = result["doc_count"]
            issues = result["issues"]

            table = Table(
                title=f"Index: {index_name} ({doc_count:,} docs)",
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            table.add_column("Issue Type", style="cyan")
            table.add_column("Count/Value", style="yellow", justify="right")
            table.add_column("Percentage", style="red", justify="right")
            table.add_column("Severity", style="magenta")

            for issue in issues:
                severity_color = {
                    "HIGH": "[bold red]HIGH[/bold red]",
                    "MEDIUM": "[yellow]MEDIUM[/yellow]",
                    "LOW": "[dim]LOW[/dim]"
                }.get(issue["severity"], issue["severity"])

                count_str = str(issue["count"]) if isinstance(issue["count"], str) else f"{issue['count']:,}"
                pct_str = f"{issue['percentage']:.1f}%" if issue["percentage"] > 0 else "-"

                table.add_row(
                    issue["type"],
                    count_str,
                    pct_str,
                    severity_color
                )

            console.print(table)
            console.print()

        # Display recommendations
        console.print(Panel(
            "[bold cyan]Recommendations:[/bold cyan]\n\n"
            "• [yellow]Missing @timestamp[/yellow]: Add date processor with fallback to event.ingested in ingest pipeline\n"
            "• [yellow]Future timestamps[/yellow]: Add validation in pipeline to reject or fix timestamps > now\n"
            "• [yellow]High ingestion lag[/yellow]: Check AWS Firehose buffer settings, cluster performance, or pipeline complexity\n"
            "• [yellow]Precision loss[/yellow]: Update date processor format to include milliseconds (e.g., 'yyyy-MM-dd'T'HH:mm:ss.SSSZ')",
            title="[bold green]💡 Tips[/bold green]",
            box=box.ROUNDED,
            border_style="green"
        ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not analyze timestamps: {e}[/red]\n")


def option_field_explosion_detector(es):
    """Detect excessive field counts, rapid field growth, and schema bloat issues."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Field Explosion & Schema Bloat Detector"])

    console.print("\n[cyan]Analyzing field explosion and schema bloat...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get threshold
    field_count_threshold = get_number_input(
        "Flag indices with field count above:",
        default=1000,
        min_val=100
    )

    if field_count_threshold is None:
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

        # Sort indices by name for time-series analysis
        indices.sort(key=lambda x: x["name"])

        console.print(f"\n[cyan]Found {len(indices)} indices to analyze[/cyan]\n")

        # Confirm before proceeding
        if not confirm_action(f"Analyze field counts for {len(indices)} indices?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Analyze each index
        all_results = []
        field_count_history = []

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
                    # Get mapping
                    mapping = es.indices.get_mapping(index=index_name)
                    index_mapping = mapping.get(index_name, {}).get("mappings", {})
                    properties = index_mapping.get("properties", {})

                    # Count total fields recursively
                    def count_fields(props, depth=0, max_depth_tracker={"max": 0}):
                        count = 0
                        current_depth = depth + 1
                        if current_depth > max_depth_tracker["max"]:
                            max_depth_tracker["max"] = current_depth

                        for field_name, field_def in props.items():
                            count += 1
                            if "properties" in field_def:
                                count += count_fields(field_def["properties"], current_depth, max_depth_tracker)
                            elif "fields" in field_def:
                                count += len(field_def["fields"])

                        return count

                    max_depth_tracker = {"max": 0}
                    total_fields = count_fields(properties, max_depth_tracker=max_depth_tracker)
                    max_nesting_depth = max_depth_tracker["max"]

                    # Track field count history for growth analysis
                    field_count_history.append({
                        "index": index_name,
                        "field_count": total_fields
                    })

                    # Check for issues
                    issues = []

                    if total_fields >= field_count_threshold:
                        issues.append({
                            "type": "Excessive field count",
                            "value": total_fields,
                            "severity": "HIGH" if total_fields > 2000 else "MEDIUM"
                        })

                    if max_nesting_depth > 5:
                        issues.append({
                            "type": "Deep nesting",
                            "value": f"{max_nesting_depth} levels",
                            "severity": "MEDIUM" if max_nesting_depth > 10 else "LOW"
                        })

                    # Detect field naming inconsistencies
                    field_names = []

                    def collect_field_names(props, prefix=""):
                        for field_name, field_def in props.items():
                            full_name = f"{prefix}{field_name}" if prefix else field_name
                            field_names.append(full_name)
                            if "properties" in field_def:
                                collect_field_names(field_def["properties"], f"{full_name}.")

                    collect_field_names(properties)

                    # Check for similar field names (potential duplicates)
                    similar_fields = []
                    for i, name1 in enumerate(field_names):
                        for name2 in field_names[i+1:]:
                            # Check for similar names (case-insensitive, underscore vs dot)
                            normalized1 = name1.lower().replace("_", ".").replace("-", ".")
                            normalized2 = name2.lower().replace("_", ".").replace("-", ".")
                            if normalized1 == normalized2 and name1 != name2:
                                similar_fields.append((name1, name2))

                    if similar_fields and len(similar_fields) > 5:
                        issues.append({
                            "type": "Field naming inconsistencies",
                            "value": f"{len(similar_fields)} pairs",
                            "severity": "LOW"
                        })

                    if issues:
                        all_results.append({
                            "index": index_name,
                            "doc_count": doc_count,
                            "total_fields": total_fields,
                            "max_depth": max_nesting_depth,
                            "issues": issues,
                            "similar_fields": similar_fields[:5]  # Show first 5
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        # Analyze field growth over time
        growth_issues = []
        if len(field_count_history) >= 2:
            for i in range(1, len(field_count_history)):
                prev = field_count_history[i-1]
                curr = field_count_history[i]

                if prev["field_count"] > 0:
                    growth_pct = ((curr["field_count"] - prev["field_count"]) / prev["field_count"]) * 100

                    if growth_pct > 50:  # More than 50% growth
                        growth_issues.append({
                            "from_index": prev["index"],
                            "to_index": curr["index"],
                            "from_count": prev["field_count"],
                            "to_count": curr["field_count"],
                            "growth_pct": growth_pct
                        })

        if not all_results and not growth_issues:
            console.print(f"\n[green]✅ No field explosion issues found![/green]\n")
            return

        # Display results
        if all_results:
            console.print(f"\n[yellow]⚠️  Found field explosion issues in {len(all_results)} indices[/yellow]\n")

            for result in all_results:
                index_name = result["index"]
                doc_count = result["doc_count"]
                total_fields = result["total_fields"]
                max_depth = result["max_depth"]
                issues = result["issues"]

                table = Table(
                    title=f"Index: {index_name} ({doc_count:,} docs, {total_fields} fields, max depth: {max_depth})",
                    box=box.ROUNDED,
                    title_style="bold cyan"
                )

                table.add_column("Issue Type", style="cyan")
                table.add_column("Value", style="yellow", justify="right")
                table.add_column("Severity", style="magenta")

                for issue in issues:
                    severity_color = {
                        "HIGH": "[bold red]HIGH[/bold red]",
                        "MEDIUM": "[yellow]MEDIUM[/yellow]",
                        "LOW": "[dim]LOW[/dim]"
                    }.get(issue["severity"], issue["severity"])

                    table.add_row(
                        issue["type"],
                        str(issue["value"]),
                        severity_color
                    )

                console.print(table)

                # Show similar fields if any
                if result.get("similar_fields"):
                    console.print("[dim]Similar field names (potential duplicates):[/dim]")
                    for name1, name2 in result["similar_fields"]:
                        console.print(f"  [yellow]•[/yellow] {name1} ≈ {name2}")

                console.print()

        # Display growth issues
        if growth_issues:
            console.print(f"\n[yellow]⚠️  Detected rapid field growth in {len(growth_issues)} index transitions[/yellow]\n")

            growth_table = Table(
                title="Field Count Growth Analysis",
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            growth_table.add_column("From Index", style="cyan")
            growth_table.add_column("To Index", style="cyan")
            growth_table.add_column("From Count", style="white", justify="right")
            growth_table.add_column("To Count", style="yellow", justify="right")
            growth_table.add_column("Growth %", style="red", justify="right")

            for growth in growth_issues[:10]:  # Show top 10
                growth_table.add_row(
                    growth["from_index"],
                    growth["to_index"],
                    f"{growth['from_count']:,}",
                    f"{growth['to_count']:,}",
                    f"+{growth['growth_pct']:.1f}%"
                )

            console.print(growth_table)
            console.print()

        # Display recommendations
        console.print(Panel(
            "[bold cyan]Recommendations:[/bold cyan]\n\n"
            "• [yellow]Excessive field count[/yellow]: Disable dynamic mapping and use explicit mappings\n"
            "• [yellow]Deep nesting[/yellow]: Flatten nested objects or use flattened field type\n"
            "• [yellow]Field naming inconsistencies[/yellow]: Normalize field names in ingest pipeline\n"
            "• [yellow]Rapid field growth[/yellow]: Investigate data sources causing new fields, implement field name validation\n"
            "• [yellow]Prevention[/yellow]: Set index.mapping.total_fields.limit to prevent runaway field creation",
            title="[bold green]💡 Tips[/bold green]",
            box=box.ROUNDED,
            border_style="green"
        ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not analyze field explosion: {e}[/red]\n")


def option_duplicate_document_analyzer(es):
    """Detect exact and near-duplicate documents using composite aggregations."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Duplicate Document Analyzer"])

    console.print("\n[cyan]Detecting duplicate documents...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get fields to check for duplicates
    console.print("\n[yellow]Enter fields to check for duplicates (comma-separated):[/yellow]")
    console.print("[dim]Common choices: message,@timestamp or message.keyword,@timestamp[/dim]")
    fields_input = safe_input("Fields (default: message.keyword,@timestamp): ").strip()

    if not fields_input:
        fields_input = "message.keyword,@timestamp"

    duplicate_fields = [f.strip() for f in fields_input.split(",") if f.strip()]

    if not duplicate_fields:
        console.print("\n[yellow]⚠️  No valid fields specified.[/yellow]\n")
        return

    # Get sample size
    sample_size = get_number_input(
        "Maximum duplicates to find per index (0 for all):",
        default=1000,
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
        if not confirm_action(f"Search for duplicates in {len(indices)} indices?"):
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
                    # Check if fields exist in this index
                    field_caps = es.field_caps(index=index_name, fields=",".join(duplicate_fields))
                    available_fields = list(field_caps.get("fields", {}).keys())

                    # Filter to only available fields
                    valid_fields = [f for f in duplicate_fields if f in available_fields]

                    if not valid_fields:
                        console.print(f"[yellow]⚠️  Fields not found in {index_name}, skipping[/yellow]")
                        progress.advance(task)
                        continue

                    # Build composite aggregation sources
                    sources = []
                    for field in valid_fields:
                        sources.append({
                            field.replace(".", "_"): {"terms": {"field": field}}
                        })

                    # Use composite aggregation to find duplicates
                    agg_query = {
                        "size": 0,
                        "aggs": {
                            "duplicates": {
                                "composite": {
                                    "size": sample_size if sample_size > 0 else 1000,
                                    "sources": sources
                                }
                            }
                        }
                    }

                    search_result = es.search(index=index_name, body=agg_query)
                    buckets = search_result.get("aggregations", {}).get("duplicates", {}).get("buckets", [])

                    # Filter buckets with more than 1 document
                    duplicate_buckets = [b for b in buckets if b.get("doc_count", 0) > 1]

                    if duplicate_buckets:
                        total_duplicates = sum(b["doc_count"] - 1 for b in duplicate_buckets)  # Subtract 1 to count only extras
                        duplicate_pct = (total_duplicates / doc_count * 100) if doc_count > 0 else 0

                        # Get index size for storage calculation
                        stats = es.indices.stats(index=index_name)
                        total_size = stats["indices"][index_name]["total"]["store"]["size_in_bytes"]
                        estimated_waste = total_size * (duplicate_pct / 100)

                        all_results.append({
                            "index": index_name,
                            "doc_count": doc_count,
                            "duplicate_groups": len(duplicate_buckets),
                            "total_duplicates": total_duplicates,
                            "duplicate_pct": duplicate_pct,
                            "estimated_waste": estimated_waste,
                            "sample_duplicates": duplicate_buckets[:5]  # Show first 5
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        if not all_results:
            console.print(f"\n[green]✅ No duplicate documents found![/green]\n")
            return

        # Display results
        console.print(f"\n[yellow]⚠️  Found duplicates in {len(all_results)} indices[/yellow]\n")

        for result in all_results:
            index_name = result["index"]
            doc_count = result["doc_count"]
            duplicate_groups = result["duplicate_groups"]
            total_duplicates = result["total_duplicates"]
            duplicate_pct = result["duplicate_pct"]
            estimated_waste = result["estimated_waste"]

            table = Table(
                title=f"Index: {index_name} ({doc_count:,} docs)",
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="yellow", justify="right")

            table.add_row("Duplicate Groups", f"{duplicate_groups:,}")
            table.add_row("Total Duplicate Docs", f"{total_duplicates:,}")
            table.add_row("Duplicate Percentage", f"{duplicate_pct:.2f}%")
            table.add_row("Estimated Storage Waste", bytes_to_human(estimated_waste))

            console.print(table)

            # Show sample duplicates
            if result.get("sample_duplicates"):
                console.print("\n[dim]Sample duplicate groups:[/dim]")
                for i, bucket in enumerate(result["sample_duplicates"][:3], 1):
                    key_str = ", ".join([f"{k}={v}" for k, v in bucket.get("key", {}).items()])
                    console.print(f"  [yellow]{i}.[/yellow] {key_str[:100]}... ({bucket['doc_count']} copies)")

            console.print()

        # Display recommendations
        console.print(Panel(
            "[bold cyan]Recommendations:[/bold cyan]\n\n"
            "• [yellow]Add fingerprint processor[/yellow]: Use fingerprint processor in ingest pipeline to generate document IDs\n"
            "  Example: {\"fingerprint\": {\"fields\": [\"message\", \"@timestamp\"], \"target_field\": \"_id\"}}\n"
            "• [yellow]Configure AWS Firehose[/yellow]: Enable document ID generation to prevent retry duplicates\n"
            "• [yellow]Cleanup existing duplicates[/yellow]: Use _delete_by_query with aggregations to remove duplicates\n"
            "• [yellow]Monitor ingestion[/yellow]: Set up alerts for sudden increases in duplicate rate",
            title="[bold green]💡 Tips[/bold green]",
            box=box.ROUNDED,
            border_style="green"
        ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not detect duplicates: {e}[/red]\n")


def option_field_value_anomaly_detector(es):
    """Detect field value anomalies including base64 encoding, truncation, and encoding issues."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Field Value Anomaly Detector"])

    console.print("\n[cyan]Detecting field value anomalies...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get field to analyze
    console.print("\n[yellow]Enter field to analyze for anomalies:[/yellow]")
    console.print("[dim]Common choices: message, message.keyword, log.original[/dim]")
    field_name = safe_input("Field name (default: message): ").strip()

    if not field_name:
        field_name = "message"

    # Get sample size
    sample_size = get_number_input(
        "Sample size for analysis (per index):",
        default=1000,
        min_val=100
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
        if not confirm_action(f"Analyze field values in {len(indices)} indices?"):
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
                    # Check if field exists
                    field_caps = es.field_caps(index=index_name, fields=field_name)
                    if field_name not in field_caps.get("fields", {}):
                        progress.advance(task)
                        continue

                    anomalies = []

                    # 1. Check for base64-encoded data
                    base64_query = {
                        "size": 0,
                        "query": {
                            "bool": {
                                "must": [
                                    {"exists": {"field": field_name}},
                                    {"regexp": {field_name: "^[A-Za-z0-9+/]{40,}={0,2}$"}}
                                ]
                            }
                        }
                    }

                    try:
                        base64_count = es.count(index=index_name, body=base64_query).get("count", 0)
                        base64_pct = (base64_count / doc_count * 100) if doc_count > 0 else 0

                        if base64_count > 0:
                            anomalies.append({
                                "type": "Base64-encoded data",
                                "count": base64_count,
                                "percentage": base64_pct,
                                "severity": "MEDIUM"
                            })
                    except Exception:
                        # Regexp might not be supported on all field types
                        pass

                    # 2. Check for invalid UTF-8 characters (replacement character)
                    utf8_query = {
                        "size": 0,
                        "query": {
                            "bool": {
                                "must": [
                                    {"exists": {"field": field_name}},
                                    {"wildcard": {field_name: "*\ufffd*"}}
                                ]
                            }
                        }
                    }

                    try:
                        utf8_count = es.count(index=index_name, body=utf8_query).get("count", 0)
                        utf8_pct = (utf8_count / doc_count * 100) if doc_count > 0 else 0

                        if utf8_count > 0:
                            anomalies.append({
                                "type": "Invalid UTF-8 characters",
                                "count": utf8_count,
                                "percentage": utf8_pct,
                                "severity": "LOW"
                            })
                    except Exception:
                        pass

                    # 3. Sample documents for truncation and length analysis
                    sample_query = {
                        "size": min(sample_size, 1000),
                        "query": {"exists": {"field": field_name}},
                        "_source": [field_name]
                    }

                    sample_result = es.search(index=index_name, body=sample_query)
                    hits = sample_result.get("hits", {}).get("hits", [])

                    if hits:
                        truncated_count = 0
                        empty_count = 0
                        length_stats = []

                        for hit in hits:
                            source = hit.get("_source", {})
                            field_value = source.get(field_name, "")

                            # Handle both string and array values
                            if isinstance(field_value, list):
                                field_value = " ".join(str(v) for v in field_value)
                            else:
                                field_value = str(field_value)

                            # Check for empty strings
                            if field_value == "":
                                empty_count += 1
                                continue

                            length_stats.append(len(field_value))

                            # Check for truncation indicators
                            # JSON truncation: ends without closing bracket
                            if field_value.startswith("{") and not field_value.rstrip().endswith("}"):
                                truncated_count += 1
                            elif field_value.startswith("[") and not field_value.rstrip().endswith("]"):
                                truncated_count += 1
                            # Message truncation: very long and ends abruptly
                            elif len(field_value) > 5000 and not field_value[-1] in ".!?\n":
                                truncated_count += 1

                        # Calculate statistics
                        if length_stats:
                            avg_length = sum(length_stats) / len(length_stats)
                            max_length = max(length_stats)
                            min_length = min(length_stats)

                            # Check for truncation
                            truncated_pct = (truncated_count / len(hits) * 100)
                            if truncated_count > 0:
                                anomalies.append({
                                    "type": "Truncated messages",
                                    "count": f"{truncated_pct:.1f}% of sample",
                                    "percentage": truncated_pct,
                                    "severity": "MEDIUM"
                                })

                            # Check for empty strings
                            empty_pct = (empty_count / len(hits) * 100)
                            if empty_count > 0:
                                anomalies.append({
                                    "type": "Empty strings",
                                    "count": f"{empty_pct:.1f}% of sample",
                                    "percentage": empty_pct,
                                    "severity": "LOW"
                                })

                            # Check for unusual length patterns
                            if max_length > 100000:  # Very large messages
                                anomalies.append({
                                    "type": "Extremely large values",
                                    "count": f"Max: {max_length:,} chars",
                                    "percentage": 0,
                                    "severity": "MEDIUM"
                                })

                    if anomalies:
                        all_results.append({
                            "index": index_name,
                            "doc_count": doc_count,
                            "field": field_name,
                            "anomalies": anomalies
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        if not all_results:
            console.print(f"\n[green]✅ No field value anomalies found![/green]\n")
            return

        # Display results
        console.print(f"\n[yellow]⚠️  Found field value anomalies in {len(all_results)} indices[/yellow]\n")

        for result in all_results:
            index_name = result["index"]
            doc_count = result["doc_count"]
            field = result["field"]
            anomalies = result["anomalies"]

            table = Table(
                title=f"Index: {index_name} ({doc_count:,} docs) - Field: {field}",
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            table.add_column("Anomaly Type", style="cyan")
            table.add_column("Count/Value", style="yellow", justify="right")
            table.add_column("Percentage", style="red", justify="right")
            table.add_column("Severity", style="magenta")

            for anomaly in anomalies:
                severity_color = {
                    "HIGH": "[bold red]HIGH[/bold red]",
                    "MEDIUM": "[yellow]MEDIUM[/yellow]",
                    "LOW": "[dim]LOW[/dim]"
                }.get(anomaly["severity"], anomaly["severity"])

                count_str = str(anomaly["count"]) if isinstance(anomaly["count"], str) else f"{anomaly['count']:,}"
                pct_str = f"{anomaly['percentage']:.1f}%" if anomaly["percentage"] > 0 else "-"

                table.add_row(
                    anomaly["type"],
                    count_str,
                    pct_str,
                    severity_color
                )

            console.print(table)
            console.print()

        # Display recommendations
        console.print(Panel(
            "[bold cyan]Recommendations:[/bold cyan]\n\n"
            "• [yellow]Base64-encoded data[/yellow]: Add decode processor in ingest pipeline\n"
            "  Example: {\"decode\": {\"field\": \"message\", \"target_field\": \"decoded_message\"}}\n"
            "• [yellow]Invalid UTF-8[/yellow]: Configure proper encoding in AWS Firehose or add conversion processor\n"
            "• [yellow]Truncated messages[/yellow]: Increase CloudWatch/Firehose message size limits or split large messages\n"
            "• [yellow]Empty strings[/yellow]: Add validation in pipeline to reject or flag empty messages\n"
            "• [yellow]Extremely large values[/yellow]: Add truncate processor or increase http.max_content_length",
            title="[bold green]💡 Tips[/bold green]",
            box=box.ROUNDED,
            border_style="green"
        ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not detect field value anomalies: {e}[/red]\n")


def option_ingestion_health_monitor(es):
    """Monitor ingestion health including stale data streams, ingestion lag, and time-series gaps."""
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Ingestion Health & Freshness Monitor"])

    console.print("\n[cyan]Monitoring ingestion health and freshness...[/cyan]\n")

    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get staleness threshold
    staleness_hours = get_number_input(
        "Flag indices with no data in last X hours:",
        default=24,
        min_val=1
    )

    if staleness_hours is None:
        return

    # Get gap threshold
    gap_threshold_minutes = get_number_input(
        "Flag time gaps larger than X minutes:",
        default=60,
        min_val=1
    )

    if gap_threshold_minutes is None:
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
        if not confirm_action(f"Analyze ingestion health for {len(indices)} indices?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Analyze each index
        all_results = []
        import datetime

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
                    issues = []

                    # 1. Check for stale data (no recent documents)
                    max_timestamp_query = {
                        "size": 0,
                        "query": {"exists": {"field": "@timestamp"}},
                        "aggs": {
                            "max_timestamp": {"max": {"field": "@timestamp"}},
                            "min_timestamp": {"min": {"field": "@timestamp"}}
                        }
                    }

                    timestamp_result = es.search(index=index_name, body=max_timestamp_query)
                    aggs = timestamp_result.get("aggregations", {})

                    max_ts = aggs.get("max_timestamp", {}).get("value")
                    min_ts = aggs.get("min_timestamp", {}).get("value")

                    if max_ts:
                        # Convert to datetime
                        max_dt = datetime.datetime.fromtimestamp(max_ts / 1000.0, tz=datetime.timezone.utc)
                        now = datetime.datetime.now(datetime.timezone.utc)
                        hours_since_last = (now - max_dt).total_seconds() / 3600

                        if hours_since_last > staleness_hours:
                            issues.append({
                                "type": "Stale data stream",
                                "value": f"{hours_since_last:.1f} hours since last document",
                                "severity": "HIGH" if hours_since_last > 168 else "MEDIUM"  # 1 week
                            })

                        # 2. Check for ingestion lag (if event.ingested exists)
                        field_caps = es.field_caps(index=index_name, fields="event.ingested,@timestamp")
                        has_ingested = "event.ingested" in field_caps.get("fields", {})

                        if has_ingested:
                            lag_query = {
                                "size": 0,
                                "query": {
                                    "bool": {
                                        "must": [
                                            {"exists": {"field": "@timestamp"}},
                                            {"exists": {"field": "event.ingested"}}
                                        ]
                                    }
                                },
                                "aggs": {
                                    "lag_stats": {
                                        "stats": {
                                            "script": {
                                                "source": "(doc['event.ingested'].value.millis - doc['@timestamp'].value.millis) / 60000.0",
                                                "lang": "painless"
                                            }
                                        }
                                    }
                                }
                            }

                            lag_result = es.search(index=index_name, body=lag_query)
                            lag_stats = lag_result.get("aggregations", {}).get("lag_stats", {})

                            if lag_stats.get("count", 0) > 0:
                                avg_lag = lag_stats.get("avg", 0)
                                max_lag = lag_stats.get("max", 0)

                                if avg_lag > 60:  # More than 1 hour average lag
                                    issues.append({
                                        "type": "High ingestion lag",
                                        "value": f"Avg: {avg_lag:.1f}m, Max: {max_lag:.1f}m",
                                        "severity": "MEDIUM"
                                    })

                        # 3. Check for time-series gaps
                        if min_ts and max_ts:
                            # Calculate appropriate interval based on data range
                            time_range_hours = (max_ts - min_ts) / (1000 * 3600)

                            if time_range_hours > 0:
                                # Use appropriate interval
                                if time_range_hours < 24:
                                    interval = "1h"
                                elif time_range_hours < 168:  # 1 week
                                    interval = "6h"
                                else:
                                    interval = "1d"

                                gap_query = {
                                    "size": 0,
                                    "query": {"exists": {"field": "@timestamp"}},
                                    "aggs": {
                                        "timeline": {
                                            "date_histogram": {
                                                "field": "@timestamp",
                                                "fixed_interval": interval,
                                                "min_doc_count": 0
                                            }
                                        }
                                    }
                                }

                                gap_result = es.search(index=index_name, body=gap_query)
                                buckets = gap_result.get("aggregations", {}).get("timeline", {}).get("buckets", [])

                                # Find gaps (buckets with 0 documents)
                                gaps = [b for b in buckets if b.get("doc_count", 0) == 0]

                                if gaps and len(gaps) > 0:
                                    gap_pct = (len(gaps) / len(buckets) * 100) if buckets else 0

                                    if gap_pct > 10:  # More than 10% gaps
                                        issues.append({
                                            "type": "Time-series gaps",
                                            "value": f"{len(gaps)} gaps ({gap_pct:.1f}% of timeline)",
                                            "severity": "MEDIUM" if gap_pct > 25 else "LOW"
                                        })

                        # 4. Check for ingestion rate anomalies
                        rate_query = {
                            "size": 0,
                            "query": {"exists": {"field": "@timestamp"}},
                            "aggs": {
                                "hourly_rate": {
                                    "date_histogram": {
                                        "field": "@timestamp",
                                        "fixed_interval": "1h"
                                    },
                                    "aggs": {
                                        "rate_stats": {
                                            "stats_bucket": {
                                                "buckets_path": "_count"
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        try:
                            rate_result = es.search(index=index_name, body=rate_query)
                            hourly_buckets = rate_result.get("aggregations", {}).get("hourly_rate", {}).get("buckets", [])

                            if len(hourly_buckets) >= 10:  # Need enough data points
                                doc_counts = [b.get("doc_count", 0) for b in hourly_buckets if b.get("doc_count", 0) > 0]

                                if doc_counts:
                                    avg_rate = sum(doc_counts) / len(doc_counts)
                                    max_rate = max(doc_counts)
                                    min_rate = min(doc_counts)

                                    # Check for sudden drops (min < 50% of avg)
                                    if min_rate < (avg_rate * 0.5) and avg_rate > 10:
                                        issues.append({
                                            "type": "Ingestion rate drop",
                                            "value": f"Min: {min_rate:.0f}/h, Avg: {avg_rate:.0f}/h",
                                            "severity": "MEDIUM"
                                        })

                                    # Check for sudden spikes (max > 200% of avg)
                                    if max_rate > (avg_rate * 2) and avg_rate > 10:
                                        issues.append({
                                            "type": "Ingestion rate spike",
                                            "value": f"Max: {max_rate:.0f}/h, Avg: {avg_rate:.0f}/h",
                                            "severity": "LOW"
                                        })
                        except Exception:
                            # Stats bucket aggregation might fail
                            pass

                    if issues:
                        all_results.append({
                            "index": index_name,
                            "doc_count": doc_count,
                            "issues": issues,
                            "last_ingestion": max_dt.isoformat() if max_ts else "Unknown"
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        if not all_results:
            console.print(f"\n[green]✅ All data streams are healthy![/green]\n")
            return

        # Display results
        console.print(f"\n[yellow]⚠️  Found ingestion health issues in {len(all_results)} indices[/yellow]\n")

        for result in all_results:
            index_name = result["index"]
            doc_count = result["doc_count"]
            issues = result["issues"]
            last_ingestion = result["last_ingestion"]

            table = Table(
                title=f"Index: {index_name} ({doc_count:,} docs) - Last: {last_ingestion}",
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            table.add_column("Issue Type", style="cyan")
            table.add_column("Details", style="yellow")
            table.add_column("Severity", style="magenta")

            for issue in issues:
                severity_color = {
                    "HIGH": "[bold red]HIGH[/bold red]",
                    "MEDIUM": "[yellow]MEDIUM[/yellow]",
                    "LOW": "[dim]LOW[/dim]"
                }.get(issue["severity"], issue["severity"])

                table.add_row(
                    issue["type"],
                    issue["value"],
                    severity_color
                )

            console.print(table)
            console.print()

        # Display recommendations
        console.print(Panel(
            "[bold cyan]Recommendations:[/bold cyan]\n\n"
            "• [yellow]Stale data stream[/yellow]: Check AWS Firehose/ESF configuration, verify log source is active\n"
            "• [yellow]High ingestion lag[/yellow]: Reduce Firehose buffer interval, check cluster performance, optimize pipeline\n"
            "• [yellow]Time-series gaps[/yellow]: Investigate log source interruptions, check for network issues\n"
            "• [yellow]Ingestion rate anomalies[/yellow]: Review application behavior, check for batch processing or failures\n"
            "• [yellow]Monitoring[/yellow]: Set up CloudWatch alarms for Firehose metrics and Elasticsearch ingestion rate",
            title="[bold green]💡 Tips[/bold green]",
            box=box.ROUNDED,
            border_style="green"
        ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not monitor ingestion health: {e}[/red]\n")






