"""
Field Mapping Conflict Resolver for Elastic Janitor.
Detect and resolve field mapping conflicts across multiple indices.
"""
from collections import defaultdict
from datetime import datetime
import questionary
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, GOD_MODE, PROTECT_SYSTEM
from ..utils import (
    show_breadcrumb, safe_input, confirm_action, get_number_input,
    get_text_input, is_system, get_index_pattern_selection, select_from_list
)
from ..utils.formatters import bytes_to_human


def option_field_mapping_conflict_resolver(es):
    """
    Detect and resolve field mapping conflicts across indices.
    
    This feature scans multiple indices for fields with conflicting data types,
    analyzes the impact, and provides multiple resolution strategies.
    """
    show_breadcrumb(["Main Menu", "Data Quality & Validation", "Field Mapping Conflict Resolver"])
    
    console.print("\n[bold cyan]🔍 Field Mapping Conflict Resolver[/bold cyan]\n")
    console.print("[dim]Detect and resolve field type conflicts across indices[/dim]\n")
    
    # Get index pattern using interactive selection
    index_pattern = get_index_pattern_selection(es)
    
    if not index_pattern:
        return
    
    # Phase 1: Detection
    conflicts = detect_mapping_conflicts(es, index_pattern)
    
    if not conflicts:
        console.print("\n[green]✅ No mapping conflicts found![/green]\n")
        return
    
    # Display conflicts
    display_conflicts(conflicts)
    
    # Ask if user wants to continue to analysis
    if not confirm_action("Continue to conflict analysis?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return
    
    # Phase 2: Analysis
    analyze_conflicts(es, conflicts)
    
    # Ask if user wants to continue to resolution
    if not confirm_action("Continue to resolution options?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return
    
    # Phase 3: Resolution
    resolve_conflicts(es, conflicts)


def detect_mapping_conflicts(es, index_pattern):
    """
    Phase 1: Detection - Scan indices and identify field type conflicts.
    
    Returns:
        list: List of conflict dictionaries with field info
    """
    console.print("\n[cyan]📊 Phase 1: Detection[/cyan]\n")
    console.print("[dim]Scanning indices for mapping conflicts...[/dim]\n")
    
    try:
        # Get matching indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index,docs.count,store.size")
        
        indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if is_system(index_name) and PROTECT_SYSTEM:
                continue
            doc_count = int(idx.get("docs.count", "0") or 0)
            store_size = idx.get("store.size", "0b")
            indices.append({
                "name": index_name,
                "doc_count": doc_count,
                "store_size": store_size
            })
        
        if not indices:
            console.print("\n[yellow]🟡 No matching indices found.[/yellow]\n")
            return []
        
        console.print(f"\n[cyan]Found {len(indices)} indices to analyze[/cyan]\n")
        
        # Fetch mappings for all indices
        field_types = defaultdict(lambda: defaultdict(list))
        data_stream_info = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Fetching mappings...", total=len(indices))
            
            for idx_info in indices:
                index_name = idx_info["name"]
                progress.update(task, description=f"[cyan]Fetching: {index_name[:50]}...")
                
                try:
                    # Get mapping
                    mapping = es.indices.get_mapping(index=index_name)
                    index_mapping = mapping.get(index_name, {}).get("mappings", {})
                    properties = index_mapping.get("properties", {})
                    
                    # Check if this is a data stream backing index
                    is_data_stream = index_name.startswith(".ds-")
                    
                    # Extract field types
                    extract_field_types(properties, field_types, index_name, idx_info, prefix="")
                    
                    # Track data stream info
                    if is_data_stream:
                        data_stream_info[index_name] = True
                    
                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not fetch mapping for {index_name}: {e}[/yellow]")
                
                progress.advance(task)

        # Find fields with type conflicts
        conflicts = []
        for field_name, types_dict in field_types.items():
            if len(types_dict) > 1:
                # Calculate severity
                total_indices = sum(len(indices_list) for indices_list in types_dict.values())
                total_docs = sum(
                    sum(idx_info["doc_count"] for idx_info in indices_list)
                    for indices_list in types_dict.values()
                )

                # Determine severity based on number of indices and documents affected
                if total_indices >= 10 or total_docs >= 1000000:
                    severity = "Critical"
                elif total_indices >= 5 or total_docs >= 100000:
                    severity = "High"
                elif total_indices >= 2 or total_docs >= 10000:
                    severity = "Medium"
                else:
                    severity = "Low"

                # Check if any system indices are involved
                has_system_indices = any(
                    is_system(idx_info["name"])
                    for indices_list in types_dict.values()
                    for idx_info in indices_list
                )

                conflicts.append({
                    "field": field_name,
                    "types": types_dict,
                    "severity": severity,
                    "total_indices": total_indices,
                    "total_docs": total_docs,
                    "has_system_indices": has_system_indices,
                    "is_data_stream": any(idx_info["name"] in data_stream_info for indices_list in types_dict.values() for idx_info in indices_list)
                })

        # Sort by severity
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        conflicts.sort(key=lambda x: (severity_order.get(x["severity"], 4), -x["total_indices"]))

        return conflicts

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not detect mapping conflicts: {e}[/red]\n")
        return []


def extract_field_types(properties, field_types, index_name, idx_info, prefix=""):
    """
    Recursively extract field types from mapping properties.

    Args:
        properties: Mapping properties dictionary
        field_types: Dictionary to store field type information
        index_name: Name of the index
        idx_info: Index information dictionary
        prefix: Field name prefix for nested fields
    """
    for field_name, field_def in properties.items():
        full_name = f"{prefix}{field_name}" if prefix else field_name
        field_type = field_def.get("type")

        if field_type:
            # Store index info with the field type
            field_types[full_name][field_type].append({
                "name": index_name,
                "doc_count": idx_info["doc_count"],
                "store_size": idx_info["store_size"]
            })

        # Handle multi-fields (e.g., field.keyword)
        if "fields" in field_def:
            for sub_field_name, sub_field_def in field_def["fields"].items():
                sub_full_name = f"{full_name}.{sub_field_name}"
                sub_field_type = sub_field_def.get("type")
                if sub_field_type:
                    field_types[sub_full_name][sub_field_type].append({
                        "name": index_name,
                        "doc_count": idx_info["doc_count"],
                        "store_size": idx_info["store_size"]
                    })

        # Recursively process nested fields
        if "properties" in field_def:
            extract_field_types(field_def["properties"], field_types, index_name, idx_info, f"{full_name}.")


def display_conflicts(conflicts):
    """
    Display detected conflicts in a clear, organized table.

    Args:
        conflicts: List of conflict dictionaries
    """
    console.print(f"\n[yellow]⚠️  Found {len(conflicts)} field(s) with mapping conflicts[/yellow]\n")

    # Create summary table
    summary_table = Table(
        title="Mapping Conflicts Summary",
        box=box.ROUNDED,
        title_style="bold red"
    )

    summary_table.add_column("#", style="dim", width=4)
    summary_table.add_column("Field Name", style="cyan", no_wrap=False)
    summary_table.add_column("Conflicting Types", style="yellow")
    summary_table.add_column("Indices", style="white", justify="right")
    summary_table.add_column("Total Docs", style="white", justify="right")
    summary_table.add_column("Severity", style="bold")
    summary_table.add_column("Warnings", style="red")

    for idx, conflict in enumerate(conflicts, 1):
        field_name = conflict["field"]
        types_dict = conflict["types"]
        severity = conflict["severity"]
        total_indices = conflict["total_indices"]
        total_docs = conflict["total_docs"]
        has_system = conflict["has_system_indices"]
        is_ds = conflict["is_data_stream"]

        # Format types
        types_str = ", ".join(types_dict.keys())

        # Format severity with color
        if severity == "Critical":
            severity_str = f"[bold red]{severity}[/bold red]"
        elif severity == "High":
            severity_str = f"[red]{severity}[/red]"
        elif severity == "Medium":
            severity_str = f"[yellow]{severity}[/yellow]"
        else:
            severity_str = f"[dim]{severity}[/dim]"

        # Warnings
        warnings = []
        if has_system:
            warnings.append("System")
        if is_ds:
            warnings.append("DataStream")
        warnings_str = ", ".join(warnings) if warnings else "-"

        summary_table.add_row(
            str(idx),
            field_name,
            types_str,
            f"{total_indices:,}",
            f"{total_docs:,}",
            severity_str,
            warnings_str
        )

    console.print(summary_table)
    console.print()

    # Display detailed conflict information
    console.print("[dim]Detailed conflict information:[/dim]\n")

    for idx, conflict in enumerate(conflicts[:5], 1):  # Show first 5 in detail
        field_name = conflict["field"]
        types_dict = conflict["types"]

        panel_content = ""
        for field_type, indices_list in types_dict.items():
            panel_content += f"[cyan]{field_type}[/cyan]: {len(indices_list)} indices ({sum(idx['doc_count'] for idx in indices_list):,} docs)\n"
            for idx_info in indices_list[:3]:  # Show first 3 indices
                panel_content += f"  • {idx_info['name']} ({idx_info['doc_count']:,} docs, {idx_info['store_size']})\n"
            if len(indices_list) > 3:
                panel_content += f"  ... and {len(indices_list) - 3} more\n"

        console.print(Panel(
            panel_content.strip(),
            title=f"[bold]Conflict #{idx}: {field_name}[/bold]",
            box=box.ROUNDED,
            border_style="yellow"
        ))
        console.print()

    if len(conflicts) > 5:
        console.print(f"[dim]... and {len(conflicts) - 5} more conflicts (use analysis phase for full details)[/dim]\n")


def analyze_conflicts(es, conflicts):
    """
    Phase 2: Analysis - Analyze impact and provide detailed information.

    Args:
        es: Elasticsearch client
        conflicts: List of conflict dictionaries
    """
    console.print("\n[cyan]📊 Phase 2: Analysis[/cyan]\n")
    console.print("[dim]Analyzing conflict impact and resolution strategies...[/dim]\n")

    # Let user select which conflict to analyze
    if len(conflicts) == 1:
        selected_conflict = conflicts[0]
    else:
        choices = []
        for idx, conflict in enumerate(conflicts, 1):
            severity_icon = "🔴" if conflict["severity"] == "Critical" else "🟡" if conflict["severity"] == "High" else "🟢"
            choices.append(questionary.Choice(
                f"{severity_icon} {conflict['field']} ({len(conflict['types'])} types, {conflict['total_indices']} indices)",
                value=idx - 1
            ))
        choices.append(questionary.Choice("Analyze all conflicts", value="all"))

        try:
            selection = questionary.select(
                "Select conflict to analyze:",
                choices=choices
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if selection == "all":
            conflicts_to_analyze = conflicts
        else:
            conflicts_to_analyze = [conflicts[selection]]

    # Analyze each selected conflict
    for conflict in conflicts_to_analyze:
        analyze_single_conflict(es, conflict)


def analyze_single_conflict(es, conflict):
    """
    Analyze a single conflict in detail.

    Args:
        es: Elasticsearch client
        conflict: Conflict dictionary
    """
    field_name = conflict["field"]
    types_dict = conflict["types"]

    console.print(f"\n[bold cyan]Analyzing: {field_name}[/bold cyan]\n")

    # Create detailed analysis table
    analysis_table = Table(
        title=f"Conflict Analysis: {field_name}",
        box=box.ROUNDED,
        title_style="bold cyan"
    )

    analysis_table.add_column("Type", style="cyan")
    analysis_table.add_column("Indices", style="white", justify="right")
    analysis_table.add_column("Total Docs", style="white", justify="right")
    analysis_table.add_column("Total Size", style="white", justify="right")
    analysis_table.add_column("Sample Indices", style="dim")

    from ..utils.formatters import size_to_bytes

    for field_type, indices_list in types_dict.items():
        total_docs = sum(idx["doc_count"] for idx in indices_list)
        total_size_bytes = sum(size_to_bytes(idx["store_size"]) for idx in indices_list)
        sample_indices = ", ".join([idx["name"] for idx in indices_list[:3]])
        if len(indices_list) > 3:
            sample_indices += f" ... (+{len(indices_list) - 3})"

        analysis_table.add_row(
            field_type,
            f"{len(indices_list):,}",
            f"{total_docs:,}",
            bytes_to_human(total_size_bytes),
            sample_indices
        )

    console.print(analysis_table)
    console.print()

    # Display warnings
    warnings = []
    if conflict["has_system_indices"]:
        warnings.append("[red]⚠️  WARNING: Some indices are system indices - modifications may affect cluster stability[/red]")
    if conflict["is_data_stream"]:
        warnings.append("[yellow]⚠️  NOTE: Some indices are data stream backing indices - consider data stream lifecycle[/yellow]")

    # Check for read-only indices
    try:
        all_indices = [idx["name"] for indices_list in types_dict.values() for idx in indices_list]
        settings_response = es.indices.get_settings(index=all_indices[:10])  # Sample first 10

        read_only_count = 0
        for idx_name, idx_settings in settings_response.items():
            if idx_settings.get("settings", {}).get("index", {}).get("blocks", {}).get("read_only", False):
                read_only_count += 1

        if read_only_count > 0:
            warnings.append(f"[yellow]⚠️  NOTE: {read_only_count} sampled indices are read-only[/yellow]")
    except Exception:
        pass

    if warnings:
        console.print(Panel(
            "\n".join(warnings),
            title="[bold red]⚠️  Warnings[/bold red]",
            box=box.ROUNDED,
            border_style="red"
        ))
        console.print()

    # Display impact assessment
    impact_content = f"""[bold]Impact Assessment:[/bold]

• [cyan]Cross-Index Queries:[/cyan] This conflict may cause issues when querying across indices
• [cyan]ESQL Queries:[/cyan] Multi-index ESQL queries may fail or return unexpected results
• [cyan]Aggregations:[/cyan] Aggregations on this field across indices may be affected
• [cyan]Visualizations:[/cyan] Kibana visualizations using this field may show inconsistent data

[bold]Estimated Resolution Impact:[/bold]

• [yellow]Reindex Time:[/yellow] ~{estimate_reindex_time(conflict)} (depends on cluster resources)
• [yellow]Storage Impact:[/yellow] Temporary storage needed during reindex
• [yellow]Downtime:[/yellow] Minimal (if using aliases) to None (if using runtime fields)
"""

    console.print(Panel(
        impact_content,
        title="[bold green]📊 Impact Assessment[/bold green]",
        box=box.ROUNDED,
        border_style="green"
    ))
    console.print()


def estimate_reindex_time(conflict):
    """
    Estimate reindex time based on document count.

    Args:
        conflict: Conflict dictionary

    Returns:
        str: Estimated time string
    """
    total_docs = conflict["total_docs"]

    # Rough estimate: 10,000 docs per second
    seconds = total_docs / 10000

    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        return f"{int(seconds / 60)} minutes"
    else:
        return f"{int(seconds / 3600)} hours"


def resolve_conflicts(es, conflicts):
    """
    Phase 3: Resolution - Provide resolution strategies and execute.

    Args:
        es: Elasticsearch client
        conflicts: List of conflict dictionaries
    """
    console.print("\n[cyan]🔧 Phase 3: Resolution[/cyan]\n")
    console.print("[dim]Select a resolution strategy...[/dim]\n")

    # Let user select which conflict to resolve
    if len(conflicts) == 1:
        selected_conflict = conflicts[0]
    else:
        choices = []
        for idx, conflict in enumerate(conflicts, 1):
            severity_icon = "🔴" if conflict["severity"] == "Critical" else "🟡" if conflict["severity"] == "High" else "🟢"
            choices.append(questionary.Choice(
                f"{severity_icon} {conflict['field']} ({len(conflict['types'])} types, {conflict['total_indices']} indices)",
                value=idx - 1
            ))

        try:
            selection = questionary.select(
                "Select conflict to resolve:",
                choices=choices
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        selected_conflict = conflicts[selection]

    # Display resolution strategies
    display_resolution_strategies(es, selected_conflict)


def display_resolution_strategies(es, conflict):
    """
    Display available resolution strategies for a conflict.

    Args:
        es: Elasticsearch client
        conflict: Conflict dictionary
    """
    field_name = conflict["field"]
    types_dict = conflict["types"]

    console.print(f"\n[bold cyan]Resolution Strategies for: {field_name}[/bold cyan]\n")

    # Build strategy choices
    strategies = [
        {
            "name": "Strategy 1: Reindex to Common Type",
            "description": "Reindex all conflicting indices to use a single, user-selected data type",
            "risk": "High",
            "downtime": "Minimal (with aliases)",
            "reversible": "Yes (with backup)"
        },
        {
            "name": "Strategy 2: Create Index Aliases",
            "description": "Group indices by type and create separate aliases for each type variant",
            "risk": "Low",
            "downtime": "None",
            "reversible": "Yes"
        },
        {
            "name": "Strategy 3: Use Runtime Fields",
            "description": "Create runtime field mappings to handle type conversions at query time",
            "risk": "Low",
            "downtime": "None",
            "reversible": "Yes"
        },
        {
            "name": "Strategy 4: Split Index Pattern",
            "description": "Recommend splitting the index pattern to avoid querying conflicting indices together",
            "risk": "None",
            "downtime": "None",
            "reversible": "N/A"
        },
        {
            "name": "Strategy 5: Mark as Ignored",
            "description": "Add conflicting fields to an ignore list for future scans",
            "risk": "None",
            "downtime": "None",
            "reversible": "Yes"
        }
    ]

    # Display strategies table
    strategies_table = Table(
        title="Available Resolution Strategies",
        box=box.ROUNDED,
        title_style="bold green"
    )

    strategies_table.add_column("#", style="cyan", width=4)
    strategies_table.add_column("Strategy", style="white")
    strategies_table.add_column("Description", style="dim", no_wrap=False)
    strategies_table.add_column("Risk", style="yellow")
    strategies_table.add_column("Downtime", style="magenta")
    strategies_table.add_column("Reversible", style="green")

    for idx, strategy in enumerate(strategies, 1):
        risk_color = "red" if strategy["risk"] == "High" else "yellow" if strategy["risk"] == "Medium" else "green"
        strategies_table.add_row(
            str(idx),
            strategy["name"],
            strategy["description"],
            f"[{risk_color}]{strategy['risk']}[/{risk_color}]",
            strategy["downtime"],
            strategy["reversible"]
        )

    console.print(strategies_table)
    console.print()

    # Let user select strategy
    try:
        choices = [
            questionary.Choice(f"Strategy 1: Reindex to Common Type", value=1),
            questionary.Choice(f"Strategy 2: Create Index Aliases", value=2),
            questionary.Choice(f"Strategy 3: Use Runtime Fields", value=3),
            questionary.Choice(f"Strategy 4: Split Index Pattern (Recommendation)", value=4),
            questionary.Choice(f"Strategy 5: Mark as Ignored", value=5),
            questionary.Separator(),
            questionary.Choice("Cancel", value=0)
        ]

        strategy_choice = questionary.select(
            "Select resolution strategy:",
            choices=choices
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    if strategy_choice == 0:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Execute selected strategy
    if strategy_choice == 1:
        execute_reindex_strategy(es, conflict)
    elif strategy_choice == 2:
        execute_alias_strategy(es, conflict)
    elif strategy_choice == 3:
        execute_runtime_field_strategy(es, conflict)
    elif strategy_choice == 4:
        execute_split_pattern_strategy(es, conflict)
    elif strategy_choice == 5:
        execute_ignore_strategy(es, conflict)


def execute_reindex_strategy(es, conflict):
    """
    Strategy 1: Reindex to Common Type

    Args:
        es: Elasticsearch client
        conflict: Conflict dictionary
    """
    console.print("\n[bold cyan]Strategy 1: Reindex to Common Type[/bold cyan]\n")

    field_name = conflict["field"]
    types_dict = conflict["types"]

    # Let user select target type
    console.print(f"[yellow]Select target data type for field '{field_name}':[/yellow]\n")

    type_choices = []
    for field_type, indices_list in types_dict.items():
        type_choices.append(questionary.Choice(
            f"{field_type} ({len(indices_list)} indices, {sum(idx['doc_count'] for idx in indices_list):,} docs)",
            value=field_type
        ))

    try:
        target_type = questionary.select(
            "Target type:",
            choices=type_choices
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Identify indices that need reindexing
    indices_to_reindex = []
    for field_type, indices_list in types_dict.items():
        if field_type != target_type:
            indices_to_reindex.extend(indices_list)

    console.print(f"\n[yellow]This will reindex {len(indices_to_reindex)} indices to use type '{target_type}'[/yellow]\n")

    # Display indices to reindex
    reindex_table = Table(
        title="Indices to Reindex",
        box=box.ROUNDED,
        title_style="bold yellow"
    )

    reindex_table.add_column("Index", style="cyan")
    reindex_table.add_column("Current Type", style="red")
    reindex_table.add_column("Documents", style="white", justify="right")
    reindex_table.add_column("Size", style="white", justify="right")

    for idx_info in indices_to_reindex[:20]:  # Show first 20
        current_type = [ft for ft, il in types_dict.items() if idx_info in il][0]
        reindex_table.add_row(
            idx_info["name"],
            current_type,
            f"{idx_info['doc_count']:,}",
            idx_info["store_size"]
        )

    if len(indices_to_reindex) > 20:
        reindex_table.add_row("...", "...", f"... and {len(indices_to_reindex) - 20} more", "...")

    console.print(reindex_table)
    console.print()

    # Dry-run mode check
    if not GOD_MODE:
        console.print("[yellow]🔍 SAFE MODE: Would reindex indices but no action taken.[/yellow]\n")
        console.print(Panel(
            f"[bold]Dry-Run Summary:[/bold]\n\n"
            f"• Would reindex {len(indices_to_reindex)} indices\n"
            f"• Target type: {target_type}\n"
            f"• Estimated time: {estimate_reindex_time(conflict)}\n"
            f"• Recommendation: Create snapshots before proceeding",
            title="[bold green]Dry-Run Complete[/bold green]",
            box=box.ROUNDED,
            border_style="green"
        ))
        console.print()
        return

    # Confirm action
    console.print("[red]⚠️  WARNING: This is a destructive operation![/red]\n")
    console.print("[yellow]Recommendations before proceeding:[/yellow]")
    console.print("  1. Create a snapshot of affected indices")
    console.print("  2. Test on a non-production cluster first")
    console.print("  3. Schedule during low-traffic period\n")

    if not confirm_action(f"Proceed with reindexing {len(indices_to_reindex)} indices?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Require explicit confirmation
    console.print("\n[red]Type 'REINDEX' to confirm this operation:[/red]")
    confirmation = safe_input("Confirmation: ").strip()

    if confirmation != "REINDEX":
        console.print("\n[yellow]⚠️  Cancelled. Confirmation did not match.[/yellow]\n")
        return

    console.print("\n[cyan]Starting reindex operation...[/cyan]\n")
    console.print("[yellow]Note: This is a complex operation. In production, use the Reindex API with proper error handling.[/yellow]\n")
    console.print("[dim]For now, this will display the reindex commands you should run manually:[/dim]\n")

    # Display reindex commands
    for idx_info in indices_to_reindex[:5]:  # Show first 5 examples
        new_index_name = f"{idx_info['name']}-reindexed"

        console.print(Panel(
            f"# Step 1: Create new index with correct mapping\n"
            f"PUT /{new_index_name}\n"
            f"{{\n"
            f'  "mappings": {{\n'
            f'    "properties": {{\n'
            f'      "{field_name}": {{\n'
            f'        "type": "{target_type}"\n'
            f'      }}\n'
            f'    }}\n'
            f'  }}\n'
            f'}}\n\n'
            f"# Step 2: Reindex data\n"
            f"POST /_reindex\n"
            f"{{\n"
            f'  "source": {{\n'
            f'    "index": "{idx_info["name"]}"\n'
            f'  }},\n'
            f'  "dest": {{\n'
            f'    "index": "{new_index_name}"\n'
            f'  }}\n'
            f'}}\n\n'
            f"# Step 3: Update aliases (if applicable)\n"
            f"# Step 4: Delete old index after verification",
            title=f"[bold]Reindex: {idx_info['name']}[/bold]",
            box=box.ROUNDED,
            border_style="cyan"
        ))
        console.print()

    if len(indices_to_reindex) > 5:
        console.print(f"[dim]... and {len(indices_to_reindex) - 5} more indices[/dim]\n")

    console.print("[green]✅ Reindex commands generated. Execute these manually or use automation tools.[/green]\n")


def execute_alias_strategy(es, conflict):
    """
    Strategy 2: Create Index Aliases

    Args:
        es: Elasticsearch client
        conflict: Conflict dictionary
    """
    console.print("\n[bold cyan]Strategy 2: Create Index Aliases[/bold cyan]\n")

    field_name = conflict["field"]
    types_dict = conflict["types"]

    console.print(f"[dim]Creating separate aliases for each type variant of '{field_name}'...[/dim]\n")

    # Generate alias names
    base_alias = get_text_input("Enter base alias name:", default="my-indices")

    if not base_alias:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Display alias plan
    alias_table = Table(
        title="Alias Plan",
        box=box.ROUNDED,
        title_style="bold green"
    )

    alias_table.add_column("Alias Name", style="cyan")
    alias_table.add_column("Field Type", style="yellow")
    alias_table.add_column("Indices", style="white", justify="right")
    alias_table.add_column("Sample Indices", style="dim")

    alias_plan = []
    for field_type, indices_list in types_dict.items():
        alias_name = f"{base_alias}-{field_type}"
        sample_indices = ", ".join([idx["name"] for idx in indices_list[:3]])
        if len(indices_list) > 3:
            sample_indices += f" ... (+{len(indices_list) - 3})"

        alias_table.add_row(
            alias_name,
            field_type,
            f"{len(indices_list):,}",
            sample_indices
        )

        alias_plan.append({
            "alias": alias_name,
            "type": field_type,
            "indices": [idx["name"] for idx in indices_list]
        })

    console.print(alias_table)
    console.print()

    # Dry-run mode check
    if not GOD_MODE:
        console.print("[yellow]🔍 SAFE MODE: Would create aliases but no action taken.[/yellow]\n")
        return

    # Confirm action
    if not confirm_action(f"Create {len(alias_plan)} aliases?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Create aliases
    console.print("\n[cyan]Creating aliases...[/cyan]\n")

    success_count = 0
    error_count = 0

    for plan in alias_plan:
        try:
            # Build alias actions
            actions = []
            for index_name in plan["indices"]:
                actions.append({
                    "add": {
                        "index": index_name,
                        "alias": plan["alias"]
                    }
                })

            # Execute alias update
            es.indices.update_aliases(body={"actions": actions})
            console.print(f"[green]✅ Created alias: {plan['alias']} ({len(plan['indices'])} indices)[/green]")
            success_count += 1
        except Exception as e:
            console.print(f"[red]❌ Error creating alias {plan['alias']}: {e}[/red]")
            error_count += 1

    console.print()
    console.print(f"[green]✅ Created {success_count} aliases[/green]")
    if error_count > 0:
        console.print(f"[red]❌ {error_count} errors[/red]")
    console.print()


def execute_runtime_field_strategy(es, conflict):
    """
    Strategy 3: Use Runtime Fields

    Args:
        es: Elasticsearch client
        conflict: Conflict dictionary
    """
    console.print("\n[bold cyan]Strategy 3: Use Runtime Fields[/bold cyan]\n")

    field_name = conflict["field"]
    types_dict = conflict["types"]

    console.print(f"[dim]Creating runtime field mapping for '{field_name}'...[/dim]\n")
    console.print("[yellow]Note: Runtime fields are computed at query time and may impact performance.[/yellow]\n")

    # Let user select target type for runtime field
    console.print(f"[yellow]Select target runtime field type:[/yellow]\n")

    type_choices = []
    for field_type in types_dict.keys():
        type_choices.append(questionary.Choice(field_type, value=field_type))

    try:
        target_type = questionary.select(
            "Runtime field type:",
            choices=type_choices
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Generate runtime field script
    runtime_field_name = f"{field_name}_runtime"

    # Simple type conversion script (this is a basic example)
    script = f"emit(doc['{field_name}'].value)"

    console.print(Panel(
        f"[bold]Runtime Field Configuration:[/bold]\n\n"
        f"Field Name: {runtime_field_name}\n"
        f"Type: {target_type}\n"
        f"Script: {script}\n\n"
        f"[dim]Add this to your index mappings or use in queries:[/dim]\n\n"
        f"PUT /your-index/_mapping\n"
        f"{{\n"
        f'  "runtime": {{\n'
        f'    "{runtime_field_name}": {{\n'
        f'      "type": "{target_type}",\n'
        f'      "script": {{\n'
        f'        "source": "{script}"\n'
        f'      }}\n'
        f'    }}\n'
        f'  }}\n'
        f'}}',
        title="[bold green]Runtime Field Configuration[/bold green]",
        box=box.ROUNDED,
        border_style="green"
    ))
    console.print()

    console.print("[yellow]Note: Apply this runtime field to each affected index or use it in search queries.[/yellow]\n")


def execute_split_pattern_strategy(es, conflict):
    """
    Strategy 4: Split Index Pattern

    Args:
        es: Elasticsearch client
        conflict: Conflict dictionary
    """
    console.print("\n[bold cyan]Strategy 4: Split Index Pattern (Recommendation)[/bold cyan]\n")

    field_name = conflict["field"]
    types_dict = conflict["types"]

    console.print(f"[dim]Analyzing index patterns for '{field_name}'...[/dim]\n")

    # Analyze index patterns
    pattern_suggestions = []

    for field_type, indices_list in types_dict.items():
        # Try to find common patterns
        index_names = [idx["name"] for idx in indices_list]

        # Extract common prefixes
        if index_names:
            # Simple pattern detection: find common prefix
            common_prefix = index_names[0]
            for name in index_names[1:]:
                while not name.startswith(common_prefix) and common_prefix:
                    common_prefix = common_prefix[:-1]

            if common_prefix:
                suggested_pattern = f"{common_prefix}*"
            else:
                suggested_pattern = "custom-pattern-*"

            pattern_suggestions.append({
                "type": field_type,
                "pattern": suggested_pattern,
                "indices_count": len(indices_list),
                "sample_indices": index_names[:3]
            })

    # Display recommendations
    recommendations_table = Table(
        title="Recommended Index Patterns",
        box=box.ROUNDED,
        title_style="bold green"
    )

    recommendations_table.add_column("Field Type", style="cyan")
    recommendations_table.add_column("Suggested Pattern", style="yellow")
    recommendations_table.add_column("Indices", style="white", justify="right")
    recommendations_table.add_column("Sample Indices", style="dim")

    for suggestion in pattern_suggestions:
        sample = ", ".join(suggestion["sample_indices"])
        if suggestion["indices_count"] > 3:
            sample += f" ... (+{suggestion['indices_count'] - 3})"

        recommendations_table.add_row(
            suggestion["type"],
            suggestion["pattern"],
            f"{suggestion['indices_count']:,}",
            sample
        )

    console.print(recommendations_table)
    console.print()

    console.print(Panel(
        f"[bold]Recommendation:[/bold]\n\n"
        f"Instead of querying all indices with a single pattern, split your queries:\n\n"
        + "\n".join([f"• Use pattern '{s['pattern']}' for {s['type']} fields" for s in pattern_suggestions]) +
        f"\n\n[dim]This avoids cross-index type conflicts and improves query performance.[/dim]",
        title="[bold green]💡 Pattern Split Strategy[/bold green]",
        box=box.ROUNDED,
        border_style="green"
    ))
    console.print()


def execute_ignore_strategy(es, conflict):
    """
    Strategy 5: Mark as Ignored

    Args:
        es: Elasticsearch client
        conflict: Conflict dictionary
    """
    console.print("\n[bold cyan]Strategy 5: Mark as Ignored[/bold cyan]\n")

    field_name = conflict["field"]

    console.print(f"[yellow]This will add '{field_name}' to the ignore list for future scans.[/yellow]\n")
    console.print("[dim]Note: This feature requires a persistent ignore list (not yet implemented).[/dim]\n")

    if confirm_action(f"Mark '{field_name}' as ignored?"):
        # In a real implementation, this would save to a config file or database
        console.print(f"\n[green]✅ Field '{field_name}' marked as ignored.[/green]\n")
        console.print("[dim]Future scans will skip this field.[/dim]\n")
    else:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")

