"""
Template & Policy Management operations for Elastic Janitor - Advanced Features.
Advanced template and policy analysis, simulation, and management.
"""
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, MAX_DELETE_LIMIT, DRY_RUN_MODE, PROTECT_SYSTEM
from ..utils import (
    safe_input, is_system, confirm_delete, confirm_action, 
    show_breadcrumb, select_from_list, get_number_input, bytes_to_human
)
from ..core import get_all_indices_info


def option_template_conflict_detector(es):
    """Analyze all index templates to identify overlapping or conflicting index patterns."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Template Conflict Detector"])
    
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index templates..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        resp = es.indices.get_index_template()
    
    templates = resp.get("index_templates", [])
    
    if not templates:
        console.print("\n[yellow]🟡 No index templates found.[/yellow]\n")
        return
    
    # Build a list of templates with their patterns and priorities
    template_data = []
    for t in templates:
        name = t["name"]
        template_def = t["index_template"]
        patterns = template_def.get("index_patterns", [])
        priority = template_def.get("priority", 0)
        
        template_data.append({
            "name": name,
            "patterns": patterns,
            "priority": priority
        })
    
    # Sort by priority (highest first)
    template_data.sort(key=lambda x: x["priority"], reverse=True)
    
    # Find conflicts - templates with overlapping patterns
    conflicts = []
    
    for i, t1 in enumerate(template_data):
        for j, t2 in enumerate(template_data):
            if i >= j:
                continue
            
            # Check if patterns overlap
            overlapping = []
            for p1 in t1["patterns"]:
                for p2 in t2["patterns"]:
                    if patterns_overlap(p1, p2):
                        overlapping.append((p1, p2))
            
            if overlapping:
                conflicts.append({
                    "template1": t1["name"],
                    "priority1": t1["priority"],
                    "template2": t2["name"],
                    "priority2": t2["priority"],
                    "overlapping_patterns": overlapping
                })
    
    if not conflicts:
        console.print("\n[green]✅ No template conflicts detected![/green]\n")
        return
    
    # Display conflicts
    console.print()
    console.print(Panel(f"[bold yellow]⚠️  Found {len(conflicts)} Template Conflicts[/bold yellow]", box=box.DOUBLE))
    console.print()
    
    for idx, conflict in enumerate(conflicts, 1):
        console.print(f"[bold cyan]Conflict {idx}:[/bold cyan]")
        console.print(f"  Template 1: [yellow]{conflict['template1']}[/yellow] (priority: {conflict['priority1']})")
        console.print(f"  Template 2: [yellow]{conflict['template2']}[/yellow] (priority: {conflict['priority2']})")
        
        if conflict['priority1'] > conflict['priority2']:
            console.print(f"  [green]→ {conflict['template1']} will take precedence[/green]")
        elif conflict['priority2'] > conflict['priority1']:
            console.print(f"  [green]→ {conflict['template2']} will take precedence[/green]")
        else:
            console.print(f"  [red]⚠️  Same priority - behavior is undefined![/red]")
        
        console.print(f"  Overlapping patterns:")
        for p1, p2 in conflict['overlapping_patterns']:
            console.print(f"    • [dim]{p1}[/dim] ↔ [dim]{p2}[/dim]")
        console.print()
    
    console.print()


def patterns_overlap(pattern1, pattern2):
    """Check if two index patterns could match the same indices."""
    # Simple wildcard pattern matching
    # This is a simplified check - real Elasticsearch pattern matching is more complex
    
    # If patterns are identical, they overlap
    if pattern1 == pattern2:
        return True
    
    # Convert patterns to regex-like comparison
    # For simplicity, we'll check if one pattern could match the other
    p1_parts = pattern1.split('*')
    p2_parts = pattern2.split('*')
    
    # If both have wildcards, they likely overlap
    if '*' in pattern1 and '*' in pattern2:
        # Check if they share common prefix or suffix
        if p1_parts[0] and p2_parts[0]:
            if p1_parts[0].startswith(p2_parts[0]) or p2_parts[0].startswith(p1_parts[0]):
                return True
        return False
    
    # If one has wildcard and other doesn't
    if '*' in pattern1:
        # Check if pattern2 could match pattern1
        if pattern2.startswith(p1_parts[0]):
            return True
    elif '*' in pattern2:
        # Check if pattern1 could match pattern2
        if pattern1.startswith(p2_parts[0]):
            return True
    
    return False


def option_ilm_policy_simulator(es):
    """Allow user to select an index and ILM policy to simulate policy actions."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "ILM Policy Simulator"])

    console.print()

    # Get all indices
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching indices..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        indices_info = get_all_indices_info(es)

    if not indices_info:
        console.print("\n[yellow]🟡 No indices found.[/yellow]\n")
        return

    # Filter out system indices if protected
    index_names = [name for name in indices_info.keys() if not (PROTECT_SYSTEM and is_system(name))]
    index_names.sort()

    if not index_names:
        console.print("\n[yellow]🟡 No non-system indices found.[/yellow]\n")
        return

    # Let user select an index
    console.print(f"\n[cyan]Found {len(index_names)} indices[/cyan]")
    selected_index = select_from_list(
        "Select an index to simulate:",
        choices=index_names[:100]  # Limit to first 100 for usability
    )

    if not selected_index:
        return

    # Get all ILM policies
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching ILM policies..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        policies_resp = es.ilm.get_lifecycle()

    policies = list(policies_resp.keys())

    if not policies:
        console.print("\n[yellow]🟡 No ILM policies found.[/yellow]\n")
        return

    policies.sort()

    # Let user select a policy
    selected_policy = select_from_list(
        "Select an ILM policy to simulate:",
        choices=policies
    )

    if not selected_policy:
        return

    # Get index info
    idx_info = indices_info[selected_index]
    age_days = (datetime.now(timezone.utc) - idx_info["created"]).days
    size_bytes = idx_info["size_bytes"]

    # Get policy details
    policy_def = policies_resp[selected_policy]["policy"]
    phases = policy_def.get("phases", {})

    # Display simulation
    console.print()
    console.print(Panel(f"[bold cyan]ILM Policy Simulation[/bold cyan]", box=box.DOUBLE))
    console.print()

    console.print(f"[bold]Index:[/bold] {selected_index}")
    console.print(f"[bold]Policy:[/bold] {selected_policy}")
    console.print(f"[bold]Current Age:[/bold] {age_days} days")
    console.print(f"[bold]Current Size:[/bold] {bytes_to_human(size_bytes)}")
    console.print()

    # Determine current phase based on age
    current_phase = determine_phase(age_days, size_bytes, phases)

    console.print(f"[bold cyan]Current Phase:[/bold cyan] [yellow]{current_phase}[/yellow]")
    console.print()

    # Display phase details
    for phase_name in ["hot", "warm", "cold", "frozen", "delete"]:
        if phase_name not in phases:
            continue

        phase = phases[phase_name]
        min_age = phase.get("min_age", "0d")
        actions = phase.get("actions", {})

        is_current = (phase_name == current_phase)
        phase_marker = "→ " if is_current else "  "
        phase_style = "bold yellow" if is_current else "dim"

        console.print(f"{phase_marker}[{phase_style}]{phase_name.upper()} Phase[/{phase_style}] (min_age: {min_age})")

        if actions:
            for action_name, action_config in actions.items():
                console.print(f"    • {action_name}: {format_action(action_name, action_config)}")
        else:
            console.print(f"    [dim]No actions defined[/dim]")

        console.print()

    # Show upcoming actions
    upcoming = get_upcoming_actions(age_days, size_bytes, phases, current_phase)

    if upcoming:
        console.print(f"[bold green]Upcoming Actions:[/bold green]")
        for action_info in upcoming:
            console.print(f"  • In ~{action_info['days_until']} days: {action_info['phase']} → {action_info['action']}")
        console.print()
    else:
        console.print(f"[dim]No upcoming actions scheduled[/dim]\n")


def determine_phase(age_days, size_bytes, phases):
    """Determine which phase an index would be in based on age and size."""
    # Check phases in order: hot, warm, cold, frozen, delete
    phase_order = ["hot", "warm", "cold", "frozen", "delete"]

    current_phase = "hot"  # Default to hot

    for phase_name in phase_order:
        if phase_name not in phases:
            continue

        phase = phases[phase_name]
        min_age = phase.get("min_age", "0d")
        min_age_days = parse_time_value(min_age)

        if age_days >= min_age_days:
            current_phase = phase_name
        else:
            break

    return current_phase


def parse_time_value(time_str):
    """Parse time value like '30d', '7h', '90m' to days."""
    if not time_str:
        return 0

    time_str = time_str.strip().lower()

    if time_str.endswith('d'):
        return int(time_str[:-1])
    elif time_str.endswith('h'):
        return int(time_str[:-1]) / 24
    elif time_str.endswith('m'):
        return int(time_str[:-1]) / (24 * 60)
    elif time_str.endswith('s'):
        return int(time_str[:-1]) / (24 * 60 * 60)
    else:
        return int(time_str)


def format_action(action_name, action_config):
    """Format action configuration for display."""
    if action_name == "rollover":
        parts = []
        if "max_age" in action_config:
            parts.append(f"max_age={action_config['max_age']}")
        if "max_size" in action_config:
            parts.append(f"max_size={action_config['max_size']}")
        if "max_docs" in action_config:
            parts.append(f"max_docs={action_config['max_docs']}")
        return ", ".join(parts) if parts else "default settings"
    elif action_name == "shrink":
        return f"number_of_shards={action_config.get('number_of_shards', 'auto')}"
    elif action_name == "forcemerge":
        return f"max_num_segments={action_config.get('max_num_segments', 1)}"
    elif action_name == "delete":
        return "delete index"
    else:
        return str(action_config) if action_config else "enabled"


def get_upcoming_actions(age_days, size_bytes, phases, current_phase):
    """Get list of upcoming actions based on current phase."""
    phase_order = ["hot", "warm", "cold", "frozen", "delete"]
    upcoming = []

    # Find current phase index
    try:
        current_idx = phase_order.index(current_phase)
    except ValueError:
        current_idx = 0

    # Look at future phases
    for phase_name in phase_order[current_idx + 1:]:
        if phase_name not in phases:
            continue

        phase = phases[phase_name]
        min_age = phase.get("min_age", "0d")
        min_age_days = parse_time_value(min_age)
        days_until = max(0, min_age_days - age_days)

        actions = phase.get("actions", {})
        for action_name in actions.keys():
            upcoming.append({
                "phase": phase_name,
                "action": action_name,
                "days_until": int(days_until)
            })

    return upcoming


def option_bulk_policy_assignment(es):
    """List indices and allow multi-select to assign ILM policy to multiple indices."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Bulk Policy Assignment"])

    console.print()

    # Get all indices with their current ILM policy
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching indices and ILM information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        indices_info = get_all_indices_info(es)

        # Get ILM explain for all indices
        try:
            ilm_explain = es.ilm.explain_lifecycle(index="*")
        except Exception:
            ilm_explain = {"indices": {}}

    if not indices_info:
        console.print("\n[yellow]🟡 No indices found.[/yellow]\n")
        return

    # Filter out system indices if protected
    index_data = []
    for idx_name, info in indices_info.items():
        if PROTECT_SYSTEM and is_system(idx_name):
            continue

        ilm_info = ilm_explain.get("indices", {}).get(idx_name, {})
        current_policy = ilm_info.get("policy", "None")
        managed = ilm_info.get("managed", False)

        index_data.append({
            "name": idx_name,
            "policy": current_policy,
            "managed": managed,
            "size": bytes_to_human(info["size_bytes"])
        })

    if not index_data:
        console.print("\n[yellow]🟡 No non-system indices found.[/yellow]\n")
        return

    # Sort by name
    index_data.sort(key=lambda x: x["name"])

    # Display current state
    console.print(f"\n[cyan]Found {len(index_data)} indices[/cyan]\n")

    # Ask user to filter by current policy
    filter_choice = select_from_list(
        "Filter indices by current policy:",
        choices=[
            "All indices",
            "Indices without ILM policy",
            "Indices with specific policy"
        ]
    )

    if not filter_choice:
        return

    if filter_choice == "Indices with specific policy":
        policy_name = safe_input("Enter policy name to filter by: ").strip()
        if not policy_name:
            return
        filtered_data = [idx for idx in index_data if idx["policy"] == policy_name]
    elif filter_choice == "Indices without ILM policy":
        filtered_data = [idx for idx in index_data if idx["policy"] == "None" or not idx["managed"]]
    else:
        filtered_data = index_data

    if not filtered_data:
        console.print("\n[yellow]🟡 No indices match the filter.[/yellow]\n")
        return

    console.print(f"\n[cyan]Filtered to {len(filtered_data)} indices[/cyan]\n")

    # Let user multi-select indices (limit to first 50 for usability)
    display_limit = min(50, len(filtered_data))
    choices = [f"{idx['name']} (current: {idx['policy']}, size: {idx['size']})" for idx in filtered_data[:display_limit]]

    if len(filtered_data) > display_limit:
        console.print(f"[yellow]⚠️  Showing first {display_limit} of {len(filtered_data)} indices[/yellow]\n")

    selected = select_from_list(
        "Select indices to assign policy to (use space to select, enter to confirm):",
        choices=choices,
        multi=True
    )

    if not selected or len(selected) == 0:
        console.print("\n[yellow]⚠️  No indices selected.[/yellow]\n")
        return

    # Extract index names from selections
    selected_indices = []
    for sel in selected:
        idx_name = sel.split(" (current:")[0]
        selected_indices.append(idx_name)

    # Get available ILM policies
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching ILM policies..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        policies_resp = es.ilm.get_lifecycle()

    policies = list(policies_resp.keys())

    if not policies:
        console.print("\n[yellow]🟡 No ILM policies found.[/yellow]\n")
        return

    policies.sort()

    # Let user select target policy
    target_policy = select_from_list(
        "Select ILM policy to assign:",
        choices=policies
    )

    if not target_policy:
        return

    # Show preview
    console.print()
    console.print(Panel(f"[bold yellow]Preview: Assign '{target_policy}' to {len(selected_indices)} indices[/bold yellow]", box=box.DOUBLE))
    console.print()

    for idx_name in selected_indices[:10]:
        console.print(f"  • {idx_name}")

    if len(selected_indices) > 10:
        console.print(f"  [dim]... and {len(selected_indices) - 10} more[/dim]")

    console.print()

    # Confirm
    if not confirm_action(f"Assign policy '{target_policy}' to {len(selected_indices)} indices?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating policy assignment...[/yellow]\n")
        console.print(f"[blue]Would assign policy '{target_policy}' to {len(selected_indices)} indices[/blue]\n")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    # Apply policy to selected indices
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn()
    ) as progress:
        task = progress.add_task(f"[cyan]Assigning policy...", total=len(selected_indices))

        for idx_name in selected_indices:
            progress.update(task, description=f"[cyan]Assigning to: {idx_name[:50]}...")
            try:
                es.indices.put_settings(
                    index=idx_name,
                    body={"index.lifecycle.name": target_policy}
                )
            except Exception as e:
                console.print(f"\n[red]Error assigning policy to {idx_name}: {e}[/red]")
            progress.advance(task)

    console.print("\n[green]✅ Policy assignment complete.[/green]\n")


def option_policy_effectiveness_report(es):
    """List all ILM policies and show statistics about their usage."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Policy Effectiveness Report"])

    console.print()

    # Get all ILM policies
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching ILM policies..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        policies_resp = es.ilm.get_lifecycle()

    policies = list(policies_resp.keys())

    if not policies:
        console.print("\n[yellow]🟡 No ILM policies found.[/yellow]\n")
        return

    # Get ILM explain for all indices
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing policy usage across all indices..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            ilm_explain = es.ilm.explain_lifecycle(index="*")
        except Exception:
            ilm_explain = {"indices": {}}

    indices_ilm = ilm_explain.get("indices", {})

    # Build statistics for each policy
    policy_stats = {}

    for policy_name in policies:
        policy_stats[policy_name] = {
            "total_indices": 0,
            "phases": defaultdict(int),
            "indices": []
        }

    # Count indices per policy and phase
    for idx_name, ilm_info in indices_ilm.items():
        if PROTECT_SYSTEM and is_system(idx_name):
            continue

        policy = ilm_info.get("policy")
        if not policy or policy not in policy_stats:
            continue

        managed = ilm_info.get("managed", False)
        if not managed:
            continue

        phase = ilm_info.get("phase", "unknown")

        policy_stats[policy]["total_indices"] += 1
        policy_stats[policy]["phases"][phase] += 1
        policy_stats[policy]["indices"].append(idx_name)

    # Display report
    console.print()
    console.print(Panel(f"[bold cyan]ILM Policy Effectiveness Report[/bold cyan]", box=box.DOUBLE))
    console.print()

    # Sort policies by usage (most used first)
    sorted_policies = sorted(
        policy_stats.items(),
        key=lambda x: x[1]["total_indices"],
        reverse=True
    )

    # Create summary table
    table = Table(title="Policy Usage Summary", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Policy Name", style="cyan", no_wrap=False)
    table.add_column("Total Indices", style="yellow", justify="right")
    table.add_column("Hot", style="red", justify="right")
    table.add_column("Warm", style="yellow", justify="right")
    table.add_column("Cold", style="blue", justify="right")
    table.add_column("Frozen", style="cyan", justify="right")
    table.add_column("Delete", style="magenta", justify="right")
    table.add_column("Status", style="green")

    unused_policies = []

    for policy_name, stats in sorted_policies:
        total = stats["total_indices"]
        phases = stats["phases"]

        status = "✅ Active" if total > 0 else "⚠️  Unused"

        if total == 0:
            unused_policies.append(policy_name)

        table.add_row(
            policy_name,
            str(total),
            str(phases.get("hot", 0)),
            str(phases.get("warm", 0)),
            str(phases.get("cold", 0)),
            str(phases.get("frozen", 0)),
            str(phases.get("delete", 0)),
            status
        )

    console.print(table)
    console.print()

    # Show unused policies
    if unused_policies:
        console.print(f"[yellow]⚠️  Found {len(unused_policies)} unused policies:[/yellow]")
        for policy in unused_policies:
            console.print(f"  • {policy}")
        console.print()
    else:
        console.print(f"[green]✅ All policies are actively managing indices![/green]\n")

    # Show detailed breakdown for top policies
    console.print(f"[bold cyan]Top 5 Most Used Policies:[/bold cyan]\n")

    for policy_name, stats in sorted_policies[:5]:
        if stats["total_indices"] == 0:
            continue

        console.print(f"[bold]{policy_name}[/bold] ({stats['total_indices']} indices)")

        # Show phase distribution
        phases = stats["phases"]
        for phase_name in ["hot", "warm", "cold", "frozen", "delete"]:
            count = phases.get(phase_name, 0)
            if count > 0:
                percentage = (count / stats["total_indices"]) * 100
                console.print(f"  {phase_name}: {count} ({percentage:.1f}%)")

        console.print()

    console.print()


def option_template_inheritance_viewer(es):
    """Allow user to select an index template and view its complete composition."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Template Inheritance Viewer"])

    console.print()

    # Get all index templates
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index templates..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        resp = es.indices.get_index_template()

    templates = resp.get("index_templates", [])

    if not templates:
        console.print("\n[yellow]🟡 No index templates found.[/yellow]\n")
        return

    # Let user select a template
    template_names = [t["name"] for t in templates]
    template_names.sort()

    selected_template = select_from_list(
        "Select an index template to view:",
        choices=template_names
    )

    if not selected_template:
        return

    # Find the selected template
    template_obj = None
    for t in templates:
        if t["name"] == selected_template:
            template_obj = t
            break

    if not template_obj:
        console.print("\n[red]❌ Template not found.[/red]\n")
        return

    template_def = template_obj["index_template"]

    # Display template information
    console.print()
    console.print(Panel(f"[bold cyan]Template: {selected_template}[/bold cyan]", box=box.DOUBLE))
    console.print()

    # Show index patterns
    patterns = template_def.get("index_patterns", [])
    console.print(f"[bold]Index Patterns:[/bold]")
    for pattern in patterns:
        console.print(f"  • {pattern}")
    console.print()

    # Show priority
    priority = template_def.get("priority", 0)
    console.print(f"[bold]Priority:[/bold] {priority}\n")

    # Show composed_of (component templates)
    composed_of = template_def.get("composed_of", [])

    if composed_of:
        console.print(f"[bold cyan]Component Templates ({len(composed_of)}):[/bold cyan]")
        for comp_name in composed_of:
            console.print(f"  • {comp_name}")
        console.print()

        # Fetch component templates
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching component templates..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            comp_resp = es.cluster.get_component_template()

        component_templates = comp_resp.get("component_templates", [])
        comp_map = {ct["name"]: ct for ct in component_templates}

        # Show inheritance chain
        console.print(f"[bold cyan]Inheritance Chain:[/bold cyan]\n")

        for idx, comp_name in enumerate(composed_of, 1):
            console.print(f"[bold]{idx}. {comp_name}[/bold]")

            if comp_name in comp_map:
                comp_template = comp_map[comp_name]["component_template"]["template"]

                # Show settings
                settings = comp_template.get("settings", {})
                if settings:
                    console.print(f"  [yellow]Settings:[/yellow]")
                    display_nested_dict(settings, indent=4)

                # Show mappings
                mappings = comp_template.get("mappings", {})
                if mappings:
                    console.print(f"  [yellow]Mappings:[/yellow]")
                    properties = mappings.get("properties", {})
                    if properties:
                        console.print(f"    Properties: {len(properties)} fields")
                        for field_name in list(properties.keys())[:5]:
                            field_type = properties[field_name].get("type", "object")
                            console.print(f"      • {field_name}: {field_type}")
                        if len(properties) > 5:
                            console.print(f"      [dim]... and {len(properties) - 5} more fields[/dim]")

                # Show aliases
                aliases = comp_template.get("aliases", {})
                if aliases:
                    console.print(f"  [yellow]Aliases:[/yellow]")
                    for alias_name in aliases.keys():
                        console.print(f"    • {alias_name}")
            else:
                console.print(f"  [red]⚠️  Component template not found[/red]")

            console.print()
    else:
        console.print(f"[dim]No component templates used[/dim]\n")

    # Show template's own settings/mappings/aliases
    template_settings = template_def.get("template", {})

    if template_settings:
        console.print(f"[bold cyan]Template's Own Configuration:[/bold cyan]\n")

        settings = template_settings.get("settings", {})
        if settings:
            console.print(f"[yellow]Settings:[/yellow]")
            display_nested_dict(settings, indent=2)

        mappings = template_settings.get("mappings", {})
        if mappings:
            console.print(f"[yellow]Mappings:[/yellow]")
            properties = mappings.get("properties", {})
            if properties:
                console.print(f"  Properties: {len(properties)} fields")

        aliases = template_settings.get("aliases", {})
        if aliases:
            console.print(f"[yellow]Aliases:[/yellow]")
            for alias_name in aliases.keys():
                console.print(f"  • {alias_name}")

        console.print()


def display_nested_dict(d, indent=0):
    """Display nested dictionary with indentation."""
    prefix = " " * indent
    for key, value in d.items():
        if isinstance(value, dict):
            console.print(f"{prefix}{key}:")
            display_nested_dict(value, indent + 2)
        else:
            console.print(f"{prefix}{key}: {value}")


def option_unused_template_detector(es):
    """Scan all templates and find those not used by any indices."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Unused Template Detector"])

    console.print()

    # Get all index templates
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index templates..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        idx_templates_resp = es.indices.get_index_template()

    index_templates = idx_templates_resp.get("index_templates", [])

    # Get all component templates
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching component templates..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        comp_templates_resp = es.cluster.get_component_template()

    component_templates = comp_templates_resp.get("component_templates", [])

    # Get all indices
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching all indices..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        indices_resp = es.cat.indices(format="json", h="index")

    all_indices = [idx["index"] for idx in indices_resp]

    # Check which index templates are used
    unused_index_templates = []

    for template in index_templates:
        template_name = template["name"]
        patterns = template["index_template"].get("index_patterns", [])

        # Check if any index matches this template's patterns
        matched = False
        for idx_name in all_indices:
            if matches_any_pattern(idx_name, patterns):
                matched = True
                break

        if not matched:
            unused_index_templates.append({
                "name": template_name,
                "patterns": patterns,
                "type": "index_template"
            })

    # Check which component templates are used
    # A component template is used if it's referenced by any index template
    used_component_templates = set()

    for template in index_templates:
        composed_of = template["index_template"].get("composed_of", [])
        used_component_templates.update(composed_of)

    unused_component_templates = []

    for comp_template in component_templates:
        comp_name = comp_template["name"]

        if comp_name not in used_component_templates:
            unused_component_templates.append({
                "name": comp_name,
                "type": "component_template"
            })

    # Display results
    console.print()
    console.print(Panel(f"[bold cyan]Unused Template Detection Report[/bold cyan]", box=box.DOUBLE))
    console.print()

    total_unused = len(unused_index_templates) + len(unused_component_templates)

    if total_unused == 0:
        console.print("[green]✅ All templates are in use![/green]\n")
        return

    # Show unused index templates
    if unused_index_templates:
        console.print(f"[bold yellow]Unused Index Templates ({len(unused_index_templates)}):[/bold yellow]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Template Name", style="yellow")
        table.add_column("Index Patterns", style="dim")

        for template in unused_index_templates:
            table.add_row(
                template["name"],
                ", ".join(template["patterns"])
            )

        console.print(table)
        console.print()

    # Show unused component templates
    if unused_component_templates:
        console.print(f"[bold yellow]Unused Component Templates ({len(unused_component_templates)}):[/bold yellow]\n")

        for template in unused_component_templates:
            console.print(f"  • {template['name']}")

        console.print()

    # Offer to delete unused templates
    if not confirm_action(f"Delete {total_unused} unused templates?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    if len(unused_index_templates) + len(unused_component_templates) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} templates in one run.[/red]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(unused_index_templates)} index templates and {len(unused_component_templates)} component templates[/blue]\n")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    # Delete unused index templates
    if unused_index_templates:
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn()
        ) as progress:
            task = progress.add_task("[red]Deleting index templates...", total=len(unused_index_templates))

            for template in unused_index_templates:
                progress.update(task, description=f"[red]Deleting: {template['name'][:50]}...")
                try:
                    es.indices.delete_index_template(name=template["name"])
                except Exception as e:
                    console.print(f"\n[red]Error deleting {template['name']}: {e}[/red]")
                progress.advance(task)

    # Delete unused component templates
    if unused_component_templates:
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn()
        ) as progress:
            task = progress.add_task("[red]Deleting component templates...", total=len(unused_component_templates))

            for template in unused_component_templates:
                progress.update(task, description=f"[red]Deleting: {template['name'][:50]}...")
                try:
                    es.cluster.delete_component_template(name=template["name"])
                except Exception as e:
                    console.print(f"\n[red]Error deleting {template['name']}: {e}[/red]")
                progress.advance(task)

    console.print("\n[green]✅ Unused templates deleted.[/green]\n")


def matches_any_pattern(index_name, patterns):
    """Check if an index name matches any of the given patterns."""
    for pattern in patterns:
        if matches_pattern(index_name, pattern):
            return True
    return False


def matches_pattern(index_name, pattern):
    """Check if an index name matches a pattern (supports wildcards)."""
    # Simple wildcard matching
    if '*' not in pattern:
        return index_name == pattern

    # Convert pattern to regex-like matching
    parts = pattern.split('*')

    # Check if index starts with first part
    if parts[0] and not index_name.startswith(parts[0]):
        return False

    # Check if index ends with last part
    if parts[-1] and not index_name.endswith(parts[-1]):
        return False

    # For more complex patterns, do a simple contains check for middle parts
    current_pos = len(parts[0]) if parts[0] else 0

    for part in parts[1:-1]:
        if not part:
            continue
        pos = index_name.find(part, current_pos)
        if pos == -1:
            return False
        current_pos = pos + len(part)

    return True

