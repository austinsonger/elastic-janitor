"""
Data Quality & Governance Features for Elastic Janitor.
Provides data governance operations including schema evolution tracking, data lineage,
PII detection, data quality scoring, metadata management, and data dictionary.
"""
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import re
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, DRY_RUN_MODE, PROTECT_SYSTEM
from ..utils import (
    safe_input, is_system, confirm_action, show_breadcrumb,
    select_from_list, get_number_input, get_text_input, bytes_to_human
)
from ..core import get_all_indices_info
import questionary


def option_schema_evolution_tracker(es):
    """
    Track mapping changes over time across indices matching a pattern.
    Display a timeline table showing field additions, removals, and type changes.
    """
    show_breadcrumb(["Main Menu", "Data Quality & Governance", "Schema Evolution Tracker"])
    
    console.print()
    
    # Get index pattern
    pattern = get_text_input("Enter index pattern to track (e.g., logs-*): ", default="*")
    if not pattern:
        return
    
    # Get date range
    days = get_number_input("Number of days to look back (default: 30): ", default=30)
    if days is None:
        return
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    console.print()
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices and mappings..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            
            # Get all indices matching pattern
            indices_info = get_all_indices_info(es)
            
            # Filter by pattern and date
            import fnmatch
            matching_indices = {}
            for idx_name, idx_info in indices_info.items():
                if is_system(idx_name):
                    continue
                if fnmatch.fnmatch(idx_name, pattern) and idx_info['created'] >= cutoff:
                    matching_indices[idx_name] = idx_info
            
            if not matching_indices:
                console.print(f"[yellow]No indices found matching pattern '{pattern}' in the last {days} days.[/yellow]\n")
                return
            
            # Get mappings for all matching indices
            mappings_data = {}
            for idx_name in matching_indices.keys():
                try:
                    mapping = es.indices.get_mapping(index=idx_name)
                    mappings_data[idx_name] = mapping[idx_name]['mappings'].get('properties', {})
                except Exception as e:
                    console.print(f"[red]Error fetching mapping for {idx_name}: {e}[/red]")
    
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return
    
    # Analyze schema evolution
    all_fields = defaultdict(lambda: {'indices': [], 'types': set()})
    
    for idx_name, properties in mappings_data.items():
        fields = _extract_fields(properties)
        for field_name, field_type in fields.items():
            all_fields[field_name]['indices'].append(idx_name)
            all_fields[field_name]['types'].add(field_type)
    
    # Display results
    console.print(f"\n[bold cyan]Schema Evolution Analysis[/bold cyan]")
    console.print(f"Pattern: {pattern} | Time Range: Last {days} days | Indices: {len(matching_indices)}\n")
    
    # Table 1: Field additions/removals
    table = Table(title="Field Distribution", box=box.ROUNDED)
    table.add_column("Field Name", style="cyan")
    table.add_column("Type(s)", style="yellow")
    table.add_column("Index Count", style="green", justify="right")
    table.add_column("Coverage %", style="magenta", justify="right")
    table.add_column("Status", style="white")
    
    total_indices = len(matching_indices)
    
    for field_name, field_data in sorted(all_fields.items()):
        count = len(field_data['indices'])
        coverage = (count / total_indices) * 100
        types_str = ", ".join(sorted(field_data['types']))
        
        # Determine status
        if len(field_data['types']) > 1:
            status = "⚠️  Type Conflict"
        elif coverage < 50:
            status = "🆕 New/Sparse"
        elif coverage == 100:
            status = "✅ Universal"
        else:
            status = "📊 Partial"
        
        table.add_row(field_name, types_str, str(count), f"{coverage:.1f}%", status)
    
    console.print(table)
    
    # Identify divergent indices
    console.print(f"\n[bold cyan]Schema Divergence Analysis[/bold cyan]\n")
    
    # Find baseline (most common field set)
    field_sets = defaultdict(list)
    for idx_name, properties in mappings_data.items():
        fields = _extract_fields(properties)
        field_signature = frozenset(fields.keys())
        field_sets[field_signature].append(idx_name)
    
    if len(field_sets) > 1:
        # Sort by frequency
        sorted_sets = sorted(field_sets.items(), key=lambda x: len(x[1]), reverse=True)
        baseline_fields, baseline_indices = sorted_sets[0]
        
        console.print(f"[green]Baseline schema ({len(baseline_indices)} indices): {len(baseline_fields)} fields[/green]")
        
        divergent_table = Table(title="Divergent Indices", box=box.ROUNDED)
        divergent_table.add_column("Index", style="cyan")
        divergent_table.add_column("Fields", style="yellow", justify="right")
        divergent_table.add_column("Missing", style="red", justify="right")
        divergent_table.add_column("Extra", style="green", justify="right")

        for field_set, indices in sorted_sets[1:]:
            for idx_name in indices[:10]:  # Show first 10 divergent
                fields = _extract_fields(mappings_data[idx_name])
                missing = baseline_fields - field_set
                extra = field_set - baseline_fields
                divergent_table.add_row(
                    idx_name,
                    str(len(fields)),
                    str(len(missing)),
                    str(len(extra))
                )

        console.print(divergent_table)
    else:
        console.print("[green]✅ All indices have identical schemas![/green]")

    console.print()


def _extract_fields(properties, prefix=""):
    """Recursively extract all fields from mapping properties."""
    fields = {}
    for field_name, field_def in properties.items():
        full_name = f"{prefix}.{field_name}" if prefix else field_name
        field_type = field_def.get('type', 'object')
        fields[full_name] = field_type

        # Recurse into nested objects
        if 'properties' in field_def:
            nested = _extract_fields(field_def['properties'], full_name)
            fields.update(nested)

    return fields


def option_data_lineage_viewer(es):
    """
    Visualize data flow through ingest pipelines, transforms, and reindex operations.
    Display source → pipeline → destination relationships in a table.
    """
    show_breadcrumb(["Main Menu", "Data Quality & Governance", "Data Lineage Viewer"])

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching pipelines and indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)

            # Get all ingest pipelines
            pipelines = es.ingest.get_pipeline()

            # Get all indices with their settings
            indices_resp = es.indices.get(index="*", expand_wildcards="all")

    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return

    # Build lineage map
    lineage_map = []

    # Check which indices use which pipelines
    for idx_name, idx_data in indices_resp.items():
        if is_system(idx_name):
            continue

        settings = idx_data.get('settings', {}).get('index', {})
        default_pipeline = settings.get('default_pipeline')
        final_pipeline = settings.get('final_pipeline')

        if default_pipeline:
            lineage_map.append({
                'source': 'Ingest',
                'pipeline': default_pipeline,
                'destination': idx_name,
                'type': 'default'
            })

        if final_pipeline:
            lineage_map.append({
                'source': 'Ingest',
                'pipeline': final_pipeline,
                'destination': idx_name,
                'type': 'final'
            })

    # Display lineage
    console.print(f"\n[bold cyan]Data Lineage Visualization[/bold cyan]\n")

    if not lineage_map:
        console.print("[yellow]No pipeline attachments found.[/yellow]\n")
    else:
        table = Table(title="Pipeline → Index Relationships", box=box.ROUNDED)
        table.add_column("Source", style="cyan")
        table.add_column("Pipeline", style="yellow")
        table.add_column("Type", style="magenta")
        table.add_column("Destination", style="green")

        for item in lineage_map:
            table.add_row(
                item['source'],
                item['pipeline'],
                item['type'],
                item['destination']
            )

        console.print(table)

    # Show pipeline details
    console.print(f"\n[bold cyan]Pipeline Processors[/bold cyan]\n")

    active_pipelines = set(item['pipeline'] for item in lineage_map)

    if active_pipelines:
        proc_table = Table(title="Active Pipelines", box=box.ROUNDED)
        proc_table.add_column("Pipeline", style="cyan")
        proc_table.add_column("Processors", style="yellow")
        proc_table.add_column("Attached Indices", style="green", justify="right")

        for pipeline_name in sorted(active_pipelines):
            if pipeline_name in pipelines:
                processors = pipelines[pipeline_name].get('processors', [])
                proc_types = [list(p.keys())[0] for p in processors if p]
                attached_count = sum(1 for item in lineage_map if item['pipeline'] == pipeline_name)

                proc_table.add_row(
                    pipeline_name,
                    ", ".join(proc_types[:5]) + ("..." if len(proc_types) > 5 else ""),
                    str(attached_count)
                )

        console.print(proc_table)

    # Identify orphaned pipelines
    console.print(f"\n[bold cyan]Orphaned Pipelines[/bold cyan]\n")

    all_pipeline_names = set(pipelines.keys())
    orphaned = all_pipeline_names - active_pipelines

    if orphaned:
        orphan_table = Table(title="Unused Pipelines", box=box.ROUNDED)
        orphan_table.add_column("Pipeline", style="yellow")
        orphan_table.add_column("Processors", style="cyan", justify="right")

        for pipeline_name in sorted(orphaned):
            if not is_system(pipeline_name):
                processors = pipelines[pipeline_name].get('processors', [])
                orphan_table.add_row(pipeline_name, str(len(processors)))

        console.print(orphan_table)
    else:
        console.print("[green]✅ No orphaned pipelines found![/green]")

    console.print()


def option_pii_detection(es):
    """
    Scan sample documents for PII patterns.
    Detect: email addresses, SSNs, phone numbers, credit cards, IP addresses.
    """
    show_breadcrumb(["Main Menu", "Data Quality & Governance", "PII Detection"])

    console.print()

    # Get index pattern
    pattern = get_text_input("Enter index pattern to scan (e.g., logs-*): ", default="*")
    if not pattern:
        return

    # Get sample size
    sample_size = get_number_input("Sample size per index (default: 1000): ", default=1000)
    if sample_size is None:
        return

    # PII patterns
    pii_patterns = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    }

    # Ask for custom patterns
    add_custom = confirm_action("Add custom PII patterns?")
    if add_custom:
        custom_name = get_text_input("Pattern name: ")
        custom_regex = get_text_input("Regex pattern: ")
        if custom_name and custom_regex:
            pii_patterns[custom_name] = custom_regex

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Scanning for PII..."),
            transient=True,
        ) as progress:
            progress.add_task("scan", total=None)

            # Get matching indices
            indices_info = get_all_indices_info(es)
            import fnmatch
            matching_indices = [name for name in indices_info.keys()
                              if fnmatch.fnmatch(name, pattern) and not is_system(name)]

            if not matching_indices:
                console.print(f"[yellow]No indices found matching pattern '{pattern}'.[/yellow]\n")
                return

            # Scan each index
            pii_findings = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'examples': []}))

            for idx_name in matching_indices[:10]:  # Limit to 10 indices
                try:
                    # Sample documents
                    result = es.search(
                        index=idx_name,
                        size=sample_size,
                        query={"match_all": {}}
                    )

                    docs = result.get('hits', {}).get('hits', [])

                    # Scan each document
                    for doc in docs:
                        source = doc.get('_source', {})
                        _scan_for_pii(source, pii_patterns, pii_findings, idx_name)

                except Exception as e:
                    console.print(f"[red]Error scanning {idx_name}: {e}[/red]")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")
        return

    # Display findings
    console.print(f"\n[bold cyan]PII Detection Results[/bold cyan]\n")

    if not pii_findings:
        console.print("[green]✅ No PII patterns detected![/green]\n")
        return

    for idx_name, field_findings in pii_findings.items():
        console.print(f"\n[bold yellow]Index:[/bold yellow] {idx_name}")

        table = Table(box=box.ROUNDED)
        table.add_column("Field", style="cyan")
        table.add_column("PII Type", style="red")
        table.add_column("Matches", style="yellow", justify="right")
        table.add_column("Example (Redacted)", style="dim")

        for field_name, pii_types in field_findings.items():
            for pii_type, data in pii_types.items():
                example = data['examples'][0] if data['examples'] else "N/A"
                # Redact example
                if len(example) > 10:
                    example = example[:3] + "***" + example[-3:]
                else:
                    example = "***"

                table.add_row(
                    field_name,
                    pii_type,
                    str(data['count']),
                    example
                )

        console.print(table)

    console.print()


def _scan_for_pii(obj, patterns, findings, idx_name, prefix=""):
    """Recursively scan object for PII patterns."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            field_path = f"{prefix}.{key}" if prefix else key
            _scan_for_pii(value, patterns, findings, idx_name, field_path)
    elif isinstance(obj, list):
        for item in obj:
            _scan_for_pii(item, patterns, findings, idx_name, prefix)
    elif isinstance(obj, str):
        for pii_type, pattern in patterns.items():
            matches = re.findall(pattern, obj)
            if matches:
                findings[idx_name][prefix][pii_type]['count'] += len(matches)
                if not findings[idx_name][prefix][pii_type]['examples']:
                    findings[idx_name][prefix][pii_type]['examples'].append(matches[0])


def option_data_quality_scoring(es):
    """
    Score indices (0-100) based on: completeness, consistency, validity.
    Display scores in a sortable table with breakdown by metric.
    """
    show_breadcrumb(["Main Menu", "Data Quality & Governance", "Data Quality Scoring"])

    console.print()

    # Get index pattern
    pattern = get_text_input("Enter index pattern to score (e.g., logs-*): ", default="*")
    if not pattern:
        return

    # Get sample size
    sample_size = get_number_input("Sample size per index (default: 1000): ", default=1000)
    if sample_size is None:
        return

    # Get threshold
    threshold = get_number_input("Quality threshold (0-100, default: 70): ", default=70)
    if threshold is None:
        return

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing data quality..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            # Get matching indices
            indices_info = get_all_indices_info(es)
            import fnmatch
            matching_indices = [name for name in indices_info.keys()
                              if fnmatch.fnmatch(name, pattern) and not is_system(name)]

            if not matching_indices:
                console.print(f"[yellow]No indices found matching pattern '{pattern}'.[/yellow]\n")
                return

            # Score each index
            scores = []

            for idx_name in matching_indices[:20]:  # Limit to 20 indices
                try:
                    # Get mapping
                    mapping = es.indices.get_mapping(index=idx_name)
                    properties = mapping[idx_name]['mappings'].get('properties', {})

                    # Sample documents
                    result = es.search(
                        index=idx_name,
                        size=sample_size,
                        query={"match_all": {}}
                    )

                    docs = result.get('hits', {}).get('hits', [])

                    if not docs:
                        continue

                    # Calculate metrics
                    completeness = _calculate_completeness(docs, properties)
                    consistency = _calculate_consistency(docs, properties)
                    validity = _calculate_validity(docs, properties)

                    overall = (completeness + consistency + validity) / 3

                    scores.append({
                        'index': idx_name,
                        'overall': overall,
                        'completeness': completeness,
                        'consistency': consistency,
                        'validity': validity,
                        'status': '✅' if overall >= threshold else '⚠️'
                    })

                except Exception as e:
                    console.print(f"[red]Error scoring {idx_name}: {e}[/red]")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")
        return

    # Display scores
    console.print(f"\n[bold cyan]Data Quality Scores[/bold cyan]\n")

    if not scores:
        console.print("[yellow]No data to score.[/yellow]\n")
        return

    # Sort by overall score
    scores.sort(key=lambda x: x['overall'], reverse=True)

    table = Table(title=f"Quality Scores (Threshold: {threshold})", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Overall", style="bold", justify="right")
    table.add_column("Completeness", style="green", justify="right")
    table.add_column("Consistency", style="yellow", justify="right")
    table.add_column("Validity", style="magenta", justify="right")
    table.add_column("Status", style="white")

    for score in scores:
        table.add_row(
            score['index'],
            f"{score['overall']:.1f}",
            f"{score['completeness']:.1f}",
            f"{score['consistency']:.1f}",
            f"{score['validity']:.1f}",
            score['status']
        )

    console.print(table)

    # Show recommendations for low-scoring indices
    low_scores = [s for s in scores if s['overall'] < threshold]
    if low_scores:
        console.print(f"\n[bold yellow]Recommendations for {len(low_scores)} indices below threshold:[/bold yellow]\n")
        for score in low_scores[:5]:
            console.print(f"[yellow]• {score['index']}:[/yellow]")
            if score['completeness'] < threshold:
                console.print("  - Improve completeness: Add validation to ensure required fields are populated")
            if score['consistency'] < threshold:
                console.print("  - Improve consistency: Standardize data types and formats across documents")
            if score['validity'] < threshold:
                console.print("  - Improve validity: Add validation rules to ensure data meets expected formats")

    console.print()


def _calculate_completeness(docs, properties):
    """Calculate completeness score (% of non-null fields)."""
    if not docs or not properties:
        return 100.0

    total_fields = len(properties)
    total_filled = 0

    for doc in docs:
        source = doc.get('_source', {})
        filled = sum(1 for field in properties.keys() if field in source and source[field] is not None)
        total_filled += filled

    return (total_filled / (total_fields * len(docs))) * 100 if total_fields > 0 else 100.0


def _calculate_consistency(docs, properties):
    """Calculate consistency score (type uniformity)."""
    if not docs:
        return 100.0

    field_types = defaultdict(set)

    for doc in docs:
        source = doc.get('_source', {})
        for field, value in source.items():
            if value is not None:
                field_types[field].add(type(value).__name__)

    # Score based on fields with single type
    consistent_fields = sum(1 for types in field_types.values() if len(types) == 1)
    total_fields = len(field_types)

    return (consistent_fields / total_fields) * 100 if total_fields > 0 else 100.0


def _calculate_validity(docs, properties):
    """Calculate validity score (format compliance)."""
    # Simplified validity check - could be enhanced with specific format rules
    if not docs:
        return 100.0

    # For now, just check that values match expected types from mapping
    valid_count = 0
    total_count = 0

    for doc in docs:
        source = doc.get('_source', {})
        for field, value in source.items():
            if field in properties and value is not None:
                total_count += 1
                # Simple type check
                expected_type = properties[field].get('type', 'text')
                if _is_valid_type(value, expected_type):
                    valid_count += 1

    return (valid_count / total_count) * 100 if total_count > 0 else 100.0


def _is_valid_type(value, expected_type):
    """Check if value matches expected Elasticsearch type."""
    type_map = {
        'text': (str,),
        'keyword': (str,),
        'long': (int,),
        'integer': (int,),
        'short': (int,),
        'byte': (int,),
        'double': (float, int),
        'float': (float, int),
        'boolean': (bool,),
        'date': (str,),  # Dates are usually strings in JSON
    }

    expected_python_types = type_map.get(expected_type, (str, int, float, bool))
    return isinstance(value, expected_python_types)


def option_metadata_management(es):
    """
    Tag indices with custom metadata: owner, purpose, sensitivity_level, department, retention_policy.
    Store metadata in index settings under index.metadata.*.
    """
    show_breadcrumb(["Main Menu", "Data Quality & Governance", "Metadata Management"])

    console.print()

    action = questionary.select(
        "Select action:",
        choices=[
            questionary.Choice("📝 Add/Update Metadata", value="add"),
            questionary.Choice("🔍 Search by Metadata", value="search"),
            questionary.Choice("📋 List All Metadata", value="list"),
            questionary.Choice("🗑️  Remove Metadata", value="remove"),
            questionary.Separator(),
            questionary.Choice("← Back", value="back")
        ]
    ).ask()

    if not action or action == "back":
        return

    if action == "add":
        _add_metadata(es)
    elif action == "search":
        _search_by_metadata(es)
    elif action == "list":
        _list_metadata(es)
    elif action == "remove":
        _remove_metadata(es)


def _add_metadata(es):
    """Add or update metadata for indices."""
    console.print()

    # Get index pattern
    pattern = get_text_input("Enter index pattern (e.g., logs-*): ", default="*")
    if not pattern:
        return

    # Get metadata fields
    owner = get_text_input("Owner (e.g., team-name): ", default="")
    purpose = get_text_input("Purpose (e.g., application-logs): ", default="")
    sensitivity = questionary.select(
        "Sensitivity Level:",
        choices=["public", "internal", "confidential", "restricted"]
    ).ask()
    department = get_text_input("Department: ", default="")
    retention = get_text_input("Retention Policy (e.g., 90d): ", default="")

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Updating metadata..."),
            transient=True,
        ) as progress:
            progress.add_task("update", total=None)

            # Get matching indices
            indices_info = get_all_indices_info(es)
            import fnmatch
            matching_indices = [name for name in indices_info.keys()
                              if fnmatch.fnmatch(name, pattern) and not is_system(name)]

            if not matching_indices:
                console.print(f"[yellow]No indices found matching pattern '{pattern}'.[/yellow]\n")
                return

            # Confirm action
            if not confirm_action(f"Update metadata for {len(matching_indices)} indices?"):
                console.print("[yellow]Cancelled.[/yellow]\n")
                return

            # Build metadata settings
            metadata_settings = {}
            if owner:
                metadata_settings['index.metadata.owner'] = owner
            if purpose:
                metadata_settings['index.metadata.purpose'] = purpose
            if sensitivity:
                metadata_settings['index.metadata.sensitivity_level'] = sensitivity
            if department:
                metadata_settings['index.metadata.department'] = department
            if retention:
                metadata_settings['index.metadata.retention_policy'] = retention

            if not metadata_settings:
                console.print("[yellow]No metadata provided.[/yellow]\n")
                return

            # Update indices
            updated = 0
            for idx_name in matching_indices:
                try:
                    if not DRY_RUN_MODE:
                        es.indices.put_settings(
                            index=idx_name,
                            body={"index": {"metadata": {
                                k.replace('index.metadata.', ''): v
                                for k, v in metadata_settings.items()
                            }}}
                        )
                    updated += 1
                except Exception as e:
                    console.print(f"[red]Error updating {idx_name}: {e}[/red]")

            if DRY_RUN_MODE:
                console.print(f"[yellow]DRY RUN: Would update metadata for {updated} indices[/yellow]\n")
            else:
                console.print(f"[green]✅ Updated metadata for {updated} indices[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")


def _search_by_metadata(es):
    """Search indices by metadata tags."""
    console.print()

    # Get search criteria
    search_field = questionary.select(
        "Search by:",
        choices=["owner", "purpose", "sensitivity_level", "department", "retention_policy"]
    ).ask()

    if not search_field:
        return

    search_value = get_text_input(f"Enter {search_field} value: ")
    if not search_value:
        return

    console.print()

    try:
        # Get all indices
        indices_resp = es.indices.get(index="*", expand_wildcards="all")

        matching = []
        for idx_name, idx_data in indices_resp.items():
            if is_system(idx_name):
                continue

            metadata = idx_data.get('settings', {}).get('index', {}).get('metadata', {})
            if metadata.get(search_field) == search_value:
                matching.append((idx_name, metadata))

        if not matching:
            console.print(f"[yellow]No indices found with {search_field}={search_value}[/yellow]\n")
            return

        console.print(f"[bold cyan]Found {len(matching)} indices with {search_field}={search_value}[/bold cyan]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Index", style="cyan")
        table.add_column("Owner", style="yellow")
        table.add_column("Purpose", style="green")
        table.add_column("Sensitivity", style="red")

        for idx_name, metadata in matching:
            table.add_row(
                idx_name,
                metadata.get('owner', 'N/A'),
                metadata.get('purpose', 'N/A'),
                metadata.get('sensitivity_level', 'N/A')
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")


def _list_metadata(es):
    """List all indices with metadata."""
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching metadata..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)

            indices_resp = es.indices.get(index="*", expand_wildcards="all")

        indices_with_metadata = []
        for idx_name, idx_data in indices_resp.items():
            if is_system(idx_name):
                continue

            metadata = idx_data.get('settings', {}).get('index', {}).get('metadata', {})
            if metadata:
                indices_with_metadata.append((idx_name, metadata))

        if not indices_with_metadata:
            console.print("[yellow]No indices with metadata found.[/yellow]\n")
            return

        console.print(f"\n[bold cyan]Indices with Metadata ({len(indices_with_metadata)})[/bold cyan]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Index", style="cyan")
        table.add_column("Owner", style="yellow")
        table.add_column("Purpose", style="green")
        table.add_column("Sensitivity", style="red")
        table.add_column("Department", style="magenta")
        table.add_column("Retention", style="blue")

        for idx_name, metadata in indices_with_metadata:
            table.add_row(
                idx_name,
                metadata.get('owner', ''),
                metadata.get('purpose', ''),
                metadata.get('sensitivity_level', ''),
                metadata.get('department', ''),
                metadata.get('retention_policy', '')
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")


def _remove_metadata(es):
    """Remove metadata from indices."""
    console.print()

    pattern = get_text_input("Enter index pattern: ", default="*")
    if not pattern:
        return

    console.print()

    try:
        # Get matching indices
        indices_info = get_all_indices_info(es)
        import fnmatch
        matching_indices = [name for name in indices_info.keys()
                          if fnmatch.fnmatch(name, pattern) and not is_system(name)]

        if not matching_indices:
            console.print(f"[yellow]No indices found matching pattern '{pattern}'.[/yellow]\n")
            return

        if not confirm_action(f"Remove all metadata from {len(matching_indices)} indices?"):
            console.print("[yellow]Cancelled.[/yellow]\n")
            return

        removed = 0
        for idx_name in matching_indices:
            try:
                if not DRY_RUN_MODE:
                    # Remove metadata by setting to null
                    es.indices.put_settings(
                        index=idx_name,
                        body={"index": {"metadata": None}}
                    )
                removed += 1
            except Exception as e:
                console.print(f"[red]Error removing metadata from {idx_name}: {e}[/red]")

        if DRY_RUN_MODE:
            console.print(f"[yellow]DRY RUN: Would remove metadata from {removed} indices[/yellow]\n")
        else:
            console.print(f"[green]✅ Removed metadata from {removed} indices[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")


def option_data_dictionary(es):
    """
    Maintain field documentation (description, examples, data_type, business_owner).
    Store dictionary in a dedicated .elastic-janitor-dictionary index.
    """
    show_breadcrumb(["Main Menu", "Data Quality & Governance", "Data Dictionary"])

    console.print()

    action = questionary.select(
        "Select action:",
        choices=[
            questionary.Choice("📖 View Dictionary", value="view"),
            questionary.Choice("➕ Add/Edit Field Definition", value="add"),
            questionary.Choice("📤 Export Dictionary", value="export"),
            questionary.Choice("🔍 Search Fields", value="search"),
            questionary.Separator(),
            questionary.Choice("← Back", value="back")
        ]
    ).ask()

    if not action or action == "back":
        return

    dictionary_index = ".elastic-janitor-dictionary"

    # Ensure dictionary index exists
    try:
        if not es.indices.exists(index=dictionary_index):
            if not DRY_RUN_MODE:
                es.indices.create(
                    index=dictionary_index,
                    body={
                        "mappings": {
                            "properties": {
                                "index_pattern": {"type": "keyword"},
                                "field_name": {"type": "keyword"},
                                "description": {"type": "text"},
                                "data_type": {"type": "keyword"},
                                "business_owner": {"type": "keyword"},
                                "examples": {"type": "text"},
                                "created_at": {"type": "date"},
                                "updated_at": {"type": "date"}
                            }
                        }
                    }
                )
    except Exception as e:
        console.print(f"[red]Error creating dictionary index: {e}[/red]\n")
        return

    if action == "view":
        _view_dictionary(es, dictionary_index)
    elif action == "add":
        _add_field_definition(es, dictionary_index)
    elif action == "export":
        _export_dictionary(es, dictionary_index)
    elif action == "search":
        _search_dictionary(es, dictionary_index)


def _view_dictionary(es, dictionary_index):
    """View all field definitions."""
    console.print()

    index_pattern = get_text_input("Filter by index pattern (or * for all): ", default="*")

    console.print()

    try:
        # Search dictionary
        query = {"match_all": {}}
        if index_pattern != "*":
            query = {"wildcard": {"index_pattern": index_pattern}}

        result = es.search(
            index=dictionary_index,
            query=query,
            size=1000,
            sort=[{"index_pattern": "asc"}, {"field_name": "asc"}]
        )

        docs = result.get('hits', {}).get('hits', [])

        if not docs:
            console.print("[yellow]No field definitions found.[/yellow]\n")
            return

        console.print(f"[bold cyan]Data Dictionary ({len(docs)} fields)[/bold cyan]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Index Pattern", style="cyan")
        table.add_column("Field", style="yellow")
        table.add_column("Type", style="green")
        table.add_column("Description", style="white")
        table.add_column("Owner", style="magenta")

        for doc in docs:
            source = doc['_source']
            table.add_row(
                source.get('index_pattern', ''),
                source.get('field_name', ''),
                source.get('data_type', ''),
                source.get('description', '')[:50] + "..." if len(source.get('description', '')) > 50 else source.get('description', ''),
                source.get('business_owner', '')
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")


def _add_field_definition(es, dictionary_index):
    """Add or edit a field definition."""
    console.print()

    index_pattern = get_text_input("Index pattern (e.g., logs-*): ")
    if not index_pattern:
        return

    field_name = get_text_input("Field name (e.g., user.email): ")
    if not field_name:
        return

    description = get_text_input("Description: ")
    data_type = get_text_input("Data type (e.g., keyword, text, long): ")
    business_owner = get_text_input("Business owner: ")
    examples = get_text_input("Examples (comma-separated): ")

    console.print()

    try:
        doc_id = f"{index_pattern}:{field_name}"

        doc = {
            "index_pattern": index_pattern,
            "field_name": field_name,
            "description": description,
            "data_type": data_type,
            "business_owner": business_owner,
            "examples": examples,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Check if exists
        exists = False
        try:
            es.get(index=dictionary_index, id=doc_id)
            exists = True
        except:
            doc["created_at"] = datetime.now(timezone.utc).isoformat()

        if not DRY_RUN_MODE:
            es.index(
                index=dictionary_index,
                id=doc_id,
                body=doc
            )

        action_word = "Updated" if exists else "Added"
        if DRY_RUN_MODE:
            console.print(f"[yellow]DRY RUN: Would {action_word.lower()} field definition[/yellow]\n")
        else:
            console.print(f"[green]✅ {action_word} field definition for {field_name}[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")


def _export_dictionary(es, dictionary_index):
    """Export dictionary to JSON or CSV."""
    console.print()

    format_choice = questionary.select(
        "Export format:",
        choices=["JSON", "CSV"]
    ).ask()

    if not format_choice:
        return

    console.print()

    try:
        result = es.search(
            index=dictionary_index,
            query={"match_all": {}},
            size=10000,
            sort=[{"index_pattern": "asc"}, {"field_name": "asc"}]
        )

        docs = result.get('hits', {}).get('hits', [])

        if not docs:
            console.print("[yellow]No data to export.[/yellow]\n")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format_choice == "JSON":
            import json
            filename = f"data_dictionary_{timestamp}.json"
            data = [doc['_source'] for doc in docs]

            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)

            console.print(f"[green]✅ Exported {len(docs)} definitions to {filename}[/green]\n")

        else:  # CSV
            import csv
            filename = f"data_dictionary_{timestamp}.csv"

            with open(filename, 'w', newline='') as f:
                if docs:
                    fieldnames = docs[0]['_source'].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for doc in docs:
                        writer.writerow(doc['_source'])

            console.print(f"[green]✅ Exported {len(docs)} definitions to {filename}[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")


def _search_dictionary(es, dictionary_index):
    """Search field definitions."""
    console.print()

    search_term = get_text_input("Search term (searches in field names and descriptions): ")
    if not search_term:
        return

    console.print()

    try:
        result = es.search(
            index=dictionary_index,
            query={
                "multi_match": {
                    "query": search_term,
                    "fields": ["field_name", "description", "index_pattern"]
                }
            },
            size=100
        )

        docs = result.get('hits', {}).get('hits', [])

        if not docs:
            console.print(f"[yellow]No results found for '{search_term}'.[/yellow]\n")
            return

        console.print(f"[bold cyan]Search Results ({len(docs)} matches)[/bold cyan]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Index Pattern", style="cyan")
        table.add_column("Field", style="yellow")
        table.add_column("Type", style="green")
        table.add_column("Description", style="white")

        for doc in docs:
            source = doc['_source']
            table.add_row(
                source.get('index_pattern', ''),
                source.get('field_name', ''),
                source.get('data_type', ''),
                source.get('description', '')[:60] + "..." if len(source.get('description', '')) > 60 else source.get('description', '')
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]\n")

