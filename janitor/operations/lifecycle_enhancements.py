"""
ILM Enhancement Features for Elastic Janitor.
Advanced Index Lifecycle Management tools including policy simulation, rollover prediction,
searchable snapshot management, data stream validation, and lifecycle phase distribution.
"""
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, MAX_DELETE_LIMIT, GOD_MODE, PROTECT_SYSTEM
from ..utils import (
    safe_input, is_system, confirm_delete, confirm_action, 
    show_breadcrumb, select_from_list, get_number_input, bytes_to_human
)
from ..core import get_all_indices_info


def option_ilm_policy_simulator(es):
    """
    Interactive simulator that allows users to test ILM policies against existing indices.
    
    Features:
    - Fetch and display all non-system indices
    - Allow user to select an index from the list
    - Fetch and display all ILM policies
    - Allow user to select a policy to simulate
    - Calculate and display current index metrics and predicted phase transitions
    """
    show_breadcrumb(["Main Menu", "Template & Policy Management", "ILM Policy Simulator"])
    
    console.print()
    
    # Fetch all indices
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_info = get_all_indices_info(es)
            cat_indices = es.cat.indices(format="json", h="index,docs.count")
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching indices: {e}[/red]\n")
        return
    
    # Filter out system indices if PROTECT_SYSTEM is enabled
    available_indices = []
    doc_counts = {}
    
    for idx_data in cat_indices:
        idx_name = idx_data.get("index")
        if idx_name and not is_system(idx_name):
            available_indices.append(idx_name)
            doc_counts[idx_name] = idx_data.get("docs.count", "0")
    
    if not available_indices:
        console.print("\n[yellow]🟡 No non-system indices found.[/yellow]\n")
        return
    
    # Limit to first 100 for usability
    available_indices = sorted(available_indices)[:100]
    
    # Let user select an index
    console.print(f"\n[cyan]Found {len(available_indices)} indices (showing first 100)[/cyan]\n")
    
    index_choices = [f"{idx}" for idx in available_indices]
    selected_index = select_from_list("Select an index to simulate:", index_choices)
    
    if not selected_index:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return
    
    # Fetch ILM policies
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ILM policies..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            policies_resp = es.ilm.get_lifecycle()
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching ILM policies: {e}[/red]\n")
        return
    
    policies = list(policies_resp.keys())
    
    if not policies:
        console.print("\n[yellow]🟡 No ILM policies found.[/yellow]\n")
        return
    
    # Let user select a policy
    policy_name = select_from_list("Select an ILM policy to simulate:", sorted(policies))
    
    if not policy_name:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return
    
    # Get index information
    index_info = indices_info.get(selected_index, {})
    created_date = index_info.get("created")
    size_bytes = index_info.get("size_bytes", 0)
    doc_count = doc_counts.get(selected_index, "0")
    
    # Calculate index age
    if created_date:
        age_delta = datetime.now(timezone.utc) - created_date
        age_days = age_delta.days
    else:
        age_days = 0
    
    # Get policy details
    policy_def = policies_resp[policy_name]
    policy_phases = policy_def.get("policy", {}).get("phases", {})
    
    # Determine current phase and actions
    current_phase = determine_current_phase(age_days, size_bytes, int(doc_count) if doc_count.isdigit() else 0, policy_phases)
    
    # Display results
    console.print()
    result_lines = []
    result_lines.append(f"[bold cyan]Index:[/bold cyan] {selected_index}")
    result_lines.append(f"[bold cyan]Policy:[/bold cyan] {policy_name}")
    result_lines.append("")
    result_lines.append(f"[bold yellow]Current Index Metrics:[/bold yellow]")
    result_lines.append(f"  • Age: {age_days} days")
    result_lines.append(f"  • Size: {bytes_to_human(size_bytes)}")
    result_lines.append(f"  • Documents: {doc_count}")
    result_lines.append("")
    result_lines.append(f"[bold green]Current Phase:[/bold green] {current_phase['phase']}")
    
    if current_phase['actions']:
        result_lines.append(f"[bold green]Active Actions:[/bold green]")
        for action in current_phase['actions']:
            result_lines.append(f"  • {action}")
    else:
        result_lines.append("[dim]No actions configured for current phase[/dim]")
    
    result_lines.append("")
    result_lines.append(f"[bold magenta]Phase Transition Timeline:[/bold magenta]")
    
    # Calculate timeline predictions
    timeline = calculate_phase_timeline(age_days, size_bytes, int(doc_count) if doc_count.isdigit() else 0, policy_phases)
    for phase_info in timeline:
        result_lines.append(f"  • {phase_info}")
    
    console.print(Panel("\n".join(result_lines), title="ILM Policy Simulation Results", box=box.ROUNDED))
    console.print()


def determine_current_phase(age_days, size_bytes, doc_count, policy_phases):
    """Determine which ILM phase an index would currently be in based on policy."""
    # Phase order: hot -> warm -> cold -> frozen -> delete
    phase_order = ["hot", "warm", "cold", "frozen", "delete"]

    current_phase_name = "hot"  # Default to hot phase
    current_actions = []

    for phase_name in phase_order:
        if phase_name not in policy_phases:
            continue

        phase_config = policy_phases[phase_name]
        min_age = phase_config.get("min_age", "0d")

        # Parse min_age (e.g., "30d", "7d", "1h")
        min_age_days = parse_age_to_days(min_age)

        if age_days >= min_age_days:
            current_phase_name = phase_name
            # Get actions for this phase
            actions = phase_config.get("actions", {})
            current_actions = list(actions.keys())
        else:
            break

    return {
        "phase": current_phase_name,
        "actions": current_actions
    }


def calculate_phase_timeline(age_days, size_bytes, doc_count, policy_phases):
    """Calculate when the index would transition to each subsequent phase."""
    timeline = []
    phase_order = ["hot", "warm", "cold", "frozen", "delete"]

    for phase_name in phase_order:
        if phase_name not in policy_phases:
            continue

        phase_config = policy_phases[phase_name]
        min_age = phase_config.get("min_age", "0d")
        min_age_days = parse_age_to_days(min_age)

        if age_days >= min_age_days:
            timeline.append(f"[green]✓[/green] {phase_name.upper()}: Already in this phase (min_age: {min_age})")
        else:
            days_until = min_age_days - age_days
            timeline.append(f"[yellow]→[/yellow] {phase_name.upper()}: In {days_until} days (min_age: {min_age})")

    return timeline


def parse_age_to_days(age_str):
    """Parse ILM age string (e.g., '30d', '7d', '1h') to days."""
    if not age_str:
        return 0

    age_str = age_str.strip().lower()

    if age_str.endswith('d'):
        return int(age_str[:-1])
    elif age_str.endswith('h'):
        return int(age_str[:-1]) / 24
    elif age_str.endswith('m'):
        return int(age_str[:-1]) / (24 * 60)
    elif age_str.endswith('s'):
        return int(age_str[:-1]) / (24 * 60 * 60)
    else:
        # Assume days if no unit
        try:
            return int(age_str)
        except:
            return 0


def option_rollover_prediction(es):
    """
    Build a predictive analytics feature for index rollover.

    Features:
    - Fetch all indices with their creation dates, sizes, and document counts
    - Calculate growth rate for indices with rollover aliases or part of data streams
    - Predict when each rollover condition will be met
    - Display results in a table with highlighting for indices near rollover
    """
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Rollover Prediction"])

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices and analyzing rollover conditions..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_info = get_all_indices_info(es)
            cat_indices = es.cat.indices(format="json", h="index,docs.count")
            aliases_resp = es.cat.aliases(format="json")
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return

    # Build doc count map
    doc_counts = {}
    for idx_data in cat_indices:
        idx_name = idx_data.get("index")
        if idx_name:
            doc_counts[idx_name] = int(idx_data.get("docs.count", "0")) if idx_data.get("docs.count", "0").isdigit() else 0

    # Build alias map
    index_aliases = defaultdict(list)
    for alias_data in aliases_resp:
        idx_name = alias_data.get("index")
        alias_name = alias_data.get("alias")
        if idx_name and alias_name:
            index_aliases[idx_name].append(alias_name)

    # Analyze indices for rollover prediction
    predictions = []

    for idx_name, info in indices_info.items():
        if is_system(idx_name):
            continue

        # Check if index has rollover alias or is part of data stream
        has_rollover = False
        if idx_name in index_aliases:
            # Check for write alias (common pattern for rollover)
            for alias in index_aliases[idx_name]:
                if "write" in alias.lower() or idx_name.startswith(".ds-"):
                    has_rollover = True
                    break

        # Also check if it's a data stream backing index
        if idx_name.startswith(".ds-"):
            has_rollover = True

        if not has_rollover:
            continue

        created_date = info.get("created")
        size_bytes = info.get("size_bytes", 0)
        doc_count = doc_counts.get(idx_name, 0)

        if not created_date:
            continue

        # Calculate age and growth rates
        age_delta = datetime.now(timezone.utc) - created_date
        age_days = max(age_delta.days, 1)  # Avoid division by zero

        bytes_per_day = size_bytes / age_days
        docs_per_day = doc_count / age_days

        # Predict rollover (using common defaults: 50GB, 30 days, or 200M docs)
        # These are typical values - actual values would come from ILM policy
        max_size_bytes = 50 * 1024**3  # 50GB
        max_age_days = 30
        max_docs = 200_000_000

        # Calculate days until each condition
        days_until_size = (max_size_bytes - size_bytes) / bytes_per_day if bytes_per_day > 0 else float('inf')
        days_until_age = max_age_days - age_days
        days_until_docs = (max_docs - doc_count) / docs_per_day if docs_per_day > 0 else float('inf')

        # Determine which condition will trigger first
        min_days = min(days_until_size, days_until_age, days_until_docs)

        if min_days == days_until_size:
            trigger_condition = "max_size (50GB)"
        elif min_days == days_until_age:
            trigger_condition = "max_age (30d)"
        else:
            trigger_condition = "max_docs (200M)"

        predictions.append({
            "index": idx_name,
            "age_days": age_days,
            "size": bytes_to_human(size_bytes),
            "docs": doc_count,
            "bytes_per_day": bytes_per_day,
            "docs_per_day": docs_per_day,
            "days_until_rollover": max(0, int(min_days)),
            "trigger_condition": trigger_condition
        })

    if not predictions:
        console.print("\n[yellow]🟡 No indices with rollover configuration found.[/yellow]\n")
        return

    # Sort by days until rollover
    predictions.sort(key=lambda x: x["days_until_rollover"])

    # Display results
    console.print()
    table = Table(title="Rollover Prediction Analysis", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Index", style="cyan", no_wrap=False)
    table.add_column("Age", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Docs", justify="right")
    table.add_column("Growth Rate", justify="right")
    table.add_column("Days Until Rollover", justify="right")
    table.add_column("Trigger Condition")

    for pred in predictions[:50]:  # Limit to 50 for readability
        # Highlight indices within 7 days of rollover
        style = "yellow" if pred["days_until_rollover"] <= 7 else ""

        growth_rate = f"{bytes_to_human(pred['bytes_per_day'])}/day"

        table.add_row(
            pred["index"],
            f"{pred['age_days']}d",
            pred["size"],
            f"{pred['docs']:,}",
            growth_rate,
            f"{pred['days_until_rollover']}d",
            pred["trigger_condition"],
            style=style
        )

    console.print(table)
    console.print()

    if len(predictions) > 50:
        console.print(f"[dim]Showing 50 of {len(predictions)} indices with rollover configuration[/dim]\n")


def option_searchable_snapshot_manager(es):
    """
    Implement comprehensive searchable snapshot management.

    Features:
    - List all searchable snapshots with mount status
    - Display storage tier and size savings
    - Provide interactive menu for mount/unmount operations
    """
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Searchable Snapshot Manager"])

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching searchable snapshots..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            # Get all indices and check for searchable snapshot type
            indices_resp = es.indices.get(index="*", expand_wildcards="all")
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching indices: {e}[/red]\n")
        return

    # Find searchable snapshots
    searchable_snapshots = []

    for idx_name, idx_data in indices_resp.items():
        settings = idx_data.get("settings", {}).get("index", {})
        store_type = settings.get("store", {}).get("type")

        # Check if it's a searchable snapshot
        if store_type == "snapshot":
            snapshot_info = settings.get("store", {}).get("snapshot", {})

            searchable_snapshots.append({
                "index": idx_name,
                "repository": snapshot_info.get("repository_name", "unknown"),
                "snapshot": snapshot_info.get("snapshot_name", "unknown"),
                "tier": settings.get("routing", {}).get("allocation", {}).get("include", {}).get("_tier", "unknown"),
                "mount_status": "mounted"
            })

    if not searchable_snapshots:
        console.print("\n[yellow]🟡 No searchable snapshots found.[/yellow]\n")
        console.print("[dim]Searchable snapshots are indices mounted from snapshots in frozen or cold tier.[/dim]\n")
    else:
        # Display searchable snapshots
        console.print()
        table = Table(title="Searchable Snapshots", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Index Name", style="cyan")
        table.add_column("Mount Status", style="green")
        table.add_column("Repository")
        table.add_column("Snapshot")
        table.add_column("Storage Tier")

        for ss in searchable_snapshots:
            table.add_row(
                ss["index"],
                ss["mount_status"],
                ss["repository"],
                ss["snapshot"],
                ss["tier"]
            )

        console.print(table)
        console.print()

    # Interactive menu
    while True:
        console.print()
        try:
            choice = select_from_list(
                "Select an operation:",
                [
                    "Mount a searchable snapshot",
                    "Unmount a searchable snapshot",
                    "View storage savings report",
                    "← Back"
                ]
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if not choice or choice == "← Back":
            return

        if choice == "Mount a searchable snapshot":
            mount_searchable_snapshot(es)
        elif choice == "Unmount a searchable snapshot":
            unmount_searchable_snapshot(es, searchable_snapshots)
        elif choice == "View storage savings report":
            view_storage_savings(es, searchable_snapshots)


def mount_searchable_snapshot(es):
    """Mount a searchable snapshot."""
    console.print()

    # Get repository name
    repository = safe_input("Enter snapshot repository name: ").strip()
    if not repository:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Get snapshot name
    snapshot = safe_input("Enter snapshot name: ").strip()
    if not snapshot:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Get index name for mount
    index_name = safe_input("Enter index name to mount as: ").strip()
    if not index_name:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    if not GOD_MODE:
        console.print("\n[yellow]🔍 SAFE MODE: Would mount searchable snapshot[/yellow]")
        console.print(f"  Repository: {repository}")
        console.print(f"  Snapshot: {snapshot}")
        console.print(f"  Index: {index_name}")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    if not confirm_action(f"Mount searchable snapshot '{snapshot}' from '{repository}' as '{index_name}'?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    try:
        # Mount the searchable snapshot
        es.searchable_snapshots.mount(
            repository=repository,
            snapshot=snapshot,
            body={
                "index": index_name
            }
        )
        console.print(f"\n[green]✅ Successfully mounted searchable snapshot as '{index_name}'[/green]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Error mounting searchable snapshot: {e}[/red]\n")


def unmount_searchable_snapshot(es, searchable_snapshots):
    """Unmount a searchable snapshot."""
    if not searchable_snapshots:
        console.print("\n[yellow]🟡 No searchable snapshots to unmount.[/yellow]\n")
        return

    console.print()

    # Let user select which snapshot to unmount
    choices = [ss["index"] for ss in searchable_snapshots]
    selected = select_from_list("Select searchable snapshot to unmount:", choices)

    if not selected:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    if not GOD_MODE:
        console.print(f"\n[yellow]🔍 SAFE MODE: Would unmount searchable snapshot '{selected}'[/yellow]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    try:
        # Unmount by deleting the index
        es.indices.delete(index=selected)
        console.print(f"\n[green]✅ Successfully unmounted searchable snapshot '{selected}'[/green]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Error unmounting searchable snapshot: {e}[/red]\n")


def view_storage_savings(es, searchable_snapshots):
    """View storage savings report for searchable snapshots."""
    console.print()

    if not searchable_snapshots:
        console.print("\n[yellow]🟡 No searchable snapshots to analyze.[/yellow]\n")
        return

    console.print(Panel(
        "[bold cyan]Searchable Snapshot Storage Savings[/bold cyan]\n\n"
        "Searchable snapshots provide significant storage savings by:\n"
        "• Storing data in object storage (S3, GCS, Azure Blob)\n"
        "• Using local cache for frequently accessed data\n"
        "• Reducing primary storage costs by 50-90%\n\n"
        f"[green]Total searchable snapshots: {len(searchable_snapshots)}[/green]",
        box=box.ROUNDED
    ))
    console.print()


def option_data_stream_template_validator(es):
    """
    Create a comprehensive validation tool for data stream configurations.

    Features:
    - Fetch all index templates
    - Validate data stream templates for common issues
    - Check ILM policy references, @timestamp mapping, component templates, etc.
    - Display validation results with recommendations
    """
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Data Stream Template Validator"])

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching index templates and validating..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            templates_resp = es.indices.get_index_template()
            # Also fetch ILM policies and component templates for validation
            ilm_policies = es.ilm.get_lifecycle()
            component_templates_resp = es.cluster.get_component_template()
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching templates: {e}[/red]\n")
        return

    templates = templates_resp.get("index_templates", [])
    component_templates = {ct["name"]: ct for ct in component_templates_resp.get("component_templates", [])}

    # Filter for data stream templates
    data_stream_templates = []
    for t in templates:
        template_def = t["index_template"]
        if template_def.get("data_stream"):
            data_stream_templates.append(t)

    if not data_stream_templates:
        console.print("\n[yellow]🟡 No data stream templates found.[/yellow]\n")
        return

    # Validate each data stream template
    validation_results = []

    for t in data_stream_templates:
        name = t["name"]
        template_def = t["index_template"]

        issues = []
        warnings = []
        recommendations = []

        # Check 1: Validate ILM policy reference
        settings = template_def.get("template", {}).get("settings", {})
        ilm_policy_name = settings.get("index", {}).get("lifecycle", {}).get("name")

        if ilm_policy_name:
            if ilm_policy_name not in ilm_policies:
                issues.append(f"Referenced ILM policy '{ilm_policy_name}' does not exist")
        else:
            warnings.append("No ILM policy configured")

        # Check 2: Validate @timestamp field mapping
        mappings = template_def.get("template", {}).get("mappings", {})
        properties = mappings.get("properties", {})

        timestamp_field = properties.get("@timestamp", {})
        if not timestamp_field:
            issues.append("@timestamp field not found in mappings")
        elif timestamp_field.get("type") != "date":
            issues.append(f"@timestamp field type is '{timestamp_field.get('type')}', should be 'date'")

        # Check 3: Validate component templates exist
        composed_of = template_def.get("composed_of", [])
        for ct_name in composed_of:
            if ct_name not in component_templates:
                issues.append(f"Referenced component template '{ct_name}' does not exist")

        # Check 4: Validate index.hidden is not set to true
        if settings.get("index", {}).get("hidden") == "true":
            issues.append("index.hidden is set to true - data streams should not be hidden")

        # Check 5: Check for conflicting mappings across component templates
        if len(composed_of) > 1:
            field_sources = defaultdict(list)
            for ct_name in composed_of:
                if ct_name in component_templates:
                    ct_mappings = component_templates[ct_name].get("component_template", {}).get("template", {}).get("mappings", {})
                    ct_properties = ct_mappings.get("properties", {})
                    for field_name in ct_properties.keys():
                        field_sources[field_name].append(ct_name)

            # Check for fields defined in multiple component templates
            for field_name, sources in field_sources.items():
                if len(sources) > 1:
                    warnings.append(f"Field '{field_name}' defined in multiple component templates: {', '.join(sources)}")

        # Determine status
        if issues:
            status = "❌ Errors"
            status_style = "red"
        elif warnings:
            status = "⚠️  Warnings"
            status_style = "yellow"
        else:
            status = "✅ Valid"
            status_style = "green"

        # Add recommendations
        if not ilm_policy_name:
            recommendations.append("Consider adding an ILM policy for lifecycle management")
        if not composed_of:
            recommendations.append("Consider using component templates for reusable configurations")

        validation_results.append({
            "name": name,
            "status": status,
            "status_style": status_style,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations
        })

    # Display validation results
    console.print()
    table = Table(title="Data Stream Template Validation Results", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Template Name", style="cyan")
    table.add_column("Status")
    table.add_column("Issues Found", no_wrap=False)

    for result in validation_results:
        issues_text = ""
        if result["issues"]:
            issues_text += "[red]Errors:[/red]\n" + "\n".join([f"  • {i}" for i in result["issues"]])
        if result["warnings"]:
            if issues_text:
                issues_text += "\n"
            issues_text += "[yellow]Warnings:[/yellow]\n" + "\n".join([f"  • {w}" for w in result["warnings"]])
        if result["recommendations"]:
            if issues_text:
                issues_text += "\n"
            issues_text += "[cyan]Recommendations:[/cyan]\n" + "\n".join([f"  • {r}" for r in result["recommendations"]])

        if not issues_text:
            issues_text = "[dim]No issues found[/dim]"

        table.add_row(
            result["name"],
            f"[{result['status_style']}]{result['status']}[/{result['status_style']}]",
            issues_text
        )

    console.print(table)
    console.print()


def option_lifecycle_phase_distribution(es):
    """
    Build a visualization and analysis feature for ILM phase distribution.

    Features:
    - Fetch all indices and their ILM explain status
    - Group indices by ILM policy and current phase
    - Calculate metrics for each group
    - Display distribution across all phases
    - Optionally calculate storage costs per phase
    """
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Lifecycle Phase Distribution"])

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ILM lifecycle status for all indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            # Get ILM explain for all indices
            ilm_explain = es.ilm.explain_lifecycle(index="*")
            indices_info = get_all_indices_info(es)
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching ILM status: {e}[/red]\n")
        return

    indices_data = ilm_explain.get("indices", {})

    if not indices_data:
        console.print("\n[yellow]🟡 No indices with ILM policies found.[/yellow]\n")
        return

    # Group indices by policy and phase
    policy_phase_groups = defaultdict(lambda: defaultdict(list))
    indices_with_errors = []

    for idx_name, idx_ilm_data in indices_data.items():
        if is_system(idx_name):
            continue

        policy_name = idx_ilm_data.get("policy", "no-policy")
        phase = idx_ilm_data.get("phase", "unknown")

        # Check for errors
        if idx_ilm_data.get("failed_step"):
            indices_with_errors.append({
                "index": idx_name,
                "policy": policy_name,
                "phase": phase,
                "error": idx_ilm_data.get("failed_step_retry_count", 0)
            })

        policy_phase_groups[policy_name][phase].append(idx_name)

    # Calculate metrics for each group
    policy_metrics = {}

    for policy_name, phases in policy_phase_groups.items():
        phase_metrics = {}

        for phase, indices in phases.items():
            total_size = 0
            total_age_days = 0
            count = len(indices)

            for idx_name in indices:
                info = indices_info.get(idx_name, {})
                total_size += info.get("size_bytes", 0)

                created_date = info.get("created")
                if created_date:
                    age_delta = datetime.now(timezone.utc) - created_date
                    total_age_days += age_delta.days

            avg_age = total_age_days / count if count > 0 else 0

            phase_metrics[phase] = {
                "count": count,
                "total_size": total_size,
                "avg_age": avg_age
            }

        policy_metrics[policy_name] = phase_metrics

    # Display summary table
    console.print()
    summary_table = Table(title="ILM Phase Distribution Summary", box=box.ROUNDED, title_style="bold cyan")
    summary_table.add_column("Policy", style="cyan")
    summary_table.add_column("Phase", style="yellow")
    summary_table.add_column("Indices", justify="right")
    summary_table.add_column("Total Size", justify="right")
    summary_table.add_column("Avg Age (days)", justify="right")

    for policy_name in sorted(policy_metrics.keys()):
        phases = policy_metrics[policy_name]

        for phase in ["hot", "warm", "cold", "frozen", "delete", "unknown"]:
            if phase not in phases:
                continue

            metrics = phases[phase]

            summary_table.add_row(
                policy_name,
                phase.upper(),
                str(metrics["count"]),
                bytes_to_human(metrics["total_size"]),
                f"{metrics['avg_age']:.1f}"
            )

    console.print(summary_table)
    console.print()

    # Display indices with errors if any
    if indices_with_errors:
        console.print()
        error_table = Table(title="Indices with ILM Errors", box=box.ROUNDED, title_style="bold red")
        error_table.add_column("Index", style="red")
        error_table.add_column("Policy")
        error_table.add_column("Phase")
        error_table.add_column("Retry Count", justify="right")

        for err in indices_with_errors[:20]:  # Limit to 20
            error_table.add_row(
                err["index"],
                err["policy"],
                err["phase"],
                str(err["error"])
            )

        console.print(error_table)
        console.print()

        if len(indices_with_errors) > 20:
            console.print(f"[dim]Showing 20 of {len(indices_with_errors)} indices with errors[/dim]\n")

    # Optional: Calculate storage costs
    console.print()
    if confirm_action("Would you like to calculate storage costs per phase?", items_count=None):
        calculate_storage_costs(policy_metrics)


def calculate_storage_costs(policy_metrics):
    """Calculate storage costs per phase based on user-provided pricing."""
    console.print()
    console.print("[cyan]Enter storage costs ($/GB/month) for each tier:[/cyan]\n")

    # Get pricing for each tier
    hot_price = get_number_input("Hot tier ($/GB/month):", default=0.15, min_val=0.0)
    warm_price = get_number_input("Warm tier ($/GB/month):", default=0.10, min_val=0.0)
    cold_price = get_number_input("Cold tier ($/GB/month):", default=0.05, min_val=0.0)
    frozen_price = get_number_input("Frozen tier ($/GB/month):", default=0.02, min_val=0.0)

    if hot_price is None or warm_price is None or cold_price is None or frozen_price is None:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    tier_pricing = {
        "hot": hot_price,
        "warm": warm_price,
        "cold": cold_price,
        "frozen": frozen_price,
        "delete": 0.0,
        "unknown": 0.0
    }

    # Calculate costs
    console.print()
    cost_table = Table(title="Estimated Monthly Storage Costs", box=box.ROUNDED, title_style="bold cyan")
    cost_table.add_column("Policy", style="cyan")
    cost_table.add_column("Phase", style="yellow")
    cost_table.add_column("Total Size", justify="right")
    cost_table.add_column("Price ($/GB)", justify="right")
    cost_table.add_column("Monthly Cost", justify="right", style="green")

    total_cost = 0.0

    for policy_name in sorted(policy_metrics.keys()):
        phases = policy_metrics[policy_name]

        for phase in ["hot", "warm", "cold", "frozen", "delete", "unknown"]:
            if phase not in phases:
                continue

            metrics = phases[phase]
            size_gb = metrics["total_size"] / (1024**3)
            price = tier_pricing.get(phase, 0.0)
            cost = size_gb * price
            total_cost += cost

            cost_table.add_row(
                policy_name,
                phase.upper(),
                bytes_to_human(metrics["total_size"]),
                f"${price:.3f}",
                f"${cost:.2f}"
            )

    console.print(cost_table)
    console.print()
    console.print(f"[bold green]Total Estimated Monthly Cost: ${total_cost:.2f}[/bold green]\n")

