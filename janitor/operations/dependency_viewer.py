"""
Dependency Viewer Operations for Elastic Janitor.
View and manage resource dependencies captured during version control.
"""
import json
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree
from ..config import console, DRY_RUN_MODE
from ..utils import show_breadcrumb, confirm_action, select_from_list
from ..utils.version_control import (
    get_resource_versions, get_resource_dependencies, compare_dependency_with_current,
    rollback_resource_with_dependencies,
    RESOURCE_TYPE_PIPELINE, RESOURCE_TYPE_INDEX_TEMPLATE, RESOURCE_TYPE_COMPONENT_TEMPLATE
)


def option_view_resource_dependencies(es):
    """View dependencies captured for a specific resource version."""
    show_breadcrumb("Template & Policy Management", "View Resource Dependencies")

    # Select resource type
    resource_types = [
        ("Ingest Pipeline", RESOURCE_TYPE_PIPELINE),
        ("Index Template", RESOURCE_TYPE_INDEX_TEMPLATE),
        ("Component Template", RESOURCE_TYPE_COMPONENT_TEMPLATE)
    ]

    type_choice = select_from_list(
        [rt[0] for rt in resource_types],
        "Select resource type:"
    )

    if not type_choice:
        return

    resource_type = resource_types[[rt[0] for rt in resource_types].index(type_choice)][1]

    # Get list of resources with versions
    try:
        # Fetch all resources of this type from Elasticsearch
        if resource_type == RESOURCE_TYPE_PIPELINE:
            resp = es.ingest.get_pipeline()
            resource_names = list(resp.keys())
        elif resource_type == RESOURCE_TYPE_INDEX_TEMPLATE:
            resp = es.indices.get_index_template()
            resource_names = [t["name"] for t in resp.get("index_templates", [])]
        elif resource_type == RESOURCE_TYPE_COMPONENT_TEMPLATE:
            resp = es.cluster.get_component_template()
            resource_names = [t["name"] for t in resp.get("component_templates", [])]
        else:
            console.print("[red]Invalid resource type[/red]")
            return

        if not resource_names:
            console.print(f"[yellow]No {type_choice.lower()}s found[/yellow]")
            return

        # Select resource
        selected_resource = select_from_list(sorted(resource_names), f"Select {type_choice.lower()}:")
        if not selected_resource:
            return

        # Get versions for this resource
        versions = get_resource_versions(resource_type, selected_resource)

        if not versions:
            console.print(f"[yellow]No versions found for '{selected_resource}'[/yellow]")
            return

        # Display versions
        version_choices = [
            f"v{v['version_number']} - {v['timestamp'][:19]} {' [KNOWN-GOOD]' if v['is_known_good'] else ''} - {v.get('comment', 'No comment')}"
            for v in versions
        ]

        selected_version_str = select_from_list(version_choices, "Select version to view dependencies:")
        if not selected_version_str:
            return

        version_num = int(selected_version_str.split()[0][1:])  # Extract version number

        # Get dependencies
        dependencies = get_resource_dependencies(resource_type, selected_resource, version_num)

        if not dependencies:
            console.print(f"\n[yellow]No dependencies captured for version {version_num}[/yellow]")
            console.print("[dim]This version was saved before dependency tracking was enabled,[/dim]")
            console.print("[dim]or no dependencies were found at the time of saving.[/dim]")
            return

        # Display dependencies
        _display_dependencies(es, selected_resource, version_num, dependencies)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")


def _display_dependencies(es, resource_name, version_num, dependencies):
    """Display dependencies in a formatted table with change detection."""
    console.print(f"\n[bold cyan]Dependencies for '{resource_name}' v{version_num}[/bold cyan]")
    console.print(f"[dim]Captured {len(dependencies)} dependency snapshot(s)[/dim]\n")

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan", width=20)
    table.add_column("Name", style="green", width=30)
    table.add_column("Relationship", style="yellow", width=25)
    table.add_column("Status", style="white", width=30)

    changed_count = 0
    missing_count = 0

    for dep in dependencies:
        dep_type = dep["dependency_resource_type"].replace("_", " ").title()
        dep_name = dep["dependency_resource_name"]
        relationship = dep["relationship_type"].replace("_", " ").title()

        # Compare with current state
        comparison = compare_dependency_with_current(es, dep)

        if not comparison["exists"]:
            status = "[red]⚠️  MISSING[/red]"
            missing_count += 1
        elif comparison["changed"]:
            status = "[yellow]⚠️  CHANGED[/yellow]"
            changed_count += 1
        else:
            status = "[green]✓ Unchanged[/green]"

        table.add_row(dep_type, dep_name, relationship, status)

    console.print(table)

    # Display summary
    if changed_count > 0 or missing_count > 0:
        console.print(f"\n[bold yellow]⚠️  Warning:[/bold yellow]")
        if changed_count > 0:
            console.print(f"  • {changed_count} dependencies have changed since this snapshot")
        if missing_count > 0:
            console.print(f"  • {missing_count} dependencies no longer exist")
        console.print("\n[dim]Rolling back to this version may not restore the exact same behavior.[/dim]")
    else:
        console.print(f"\n[green]✓ All dependencies are unchanged since this snapshot[/green]")





def option_rollback_with_dependencies(es):
    """Rollback a resource and all its dependencies to a specific snapshot."""
    show_breadcrumb("Template & Policy Management", "Rollback with Dependencies")

    # Select resource type
    resource_types = [
        ("Ingest Pipeline", RESOURCE_TYPE_PIPELINE),
        ("Index Template", RESOURCE_TYPE_INDEX_TEMPLATE),
        ("Component Template", RESOURCE_TYPE_COMPONENT_TEMPLATE)
    ]

    type_choice = select_from_list(
        [rt[0] for rt in resource_types],
        "Select resource type:"
    )

    if not type_choice:
        return

    resource_type = resource_types[[rt[0] for rt in resource_types].index(type_choice)][1]

    # Get list of resources with versions
    try:
        # Fetch all resources of this type from Elasticsearch
        if resource_type == RESOURCE_TYPE_PIPELINE:
            resp = es.ingest.get_pipeline()
            resource_names = list(resp.keys())
        elif resource_type == RESOURCE_TYPE_INDEX_TEMPLATE:
            resp = es.indices.get_index_template()
            resource_names = [t["name"] for t in resp.get("index_templates", [])]
        elif resource_type == RESOURCE_TYPE_COMPONENT_TEMPLATE:
            resp = es.cluster.get_component_template()
            resource_names = [t["name"] for t in resp.get("component_templates", [])]
        else:
            console.print("[red]Invalid resource type[/red]")
            return

        if not resource_names:
            console.print(f"[yellow]No {type_choice.lower()}s found[/yellow]")
            return

        # Select resource
        selected_resource = select_from_list(sorted(resource_names), f"Select {type_choice.lower()}:")
        if not selected_resource:
            return

        # Get versions for this resource
        versions = get_resource_versions(resource_type, selected_resource)

        if not versions:
            console.print(f"[yellow]No versions found for '{selected_resource}'[/yellow]")
            return

        # Display versions
        version_choices = [
            f"v{v['version_number']} - {v['timestamp'][:19]} {' [KNOWN-GOOD]' if v['is_known_good'] else ''} - {v.get('comment', 'No comment')}"
            for v in versions
        ]

        selected_version_str = select_from_list(version_choices, "Select version to rollback to:")
        if not selected_version_str:
            return

        version_num = int(selected_version_str.split()[0][1:])  # Extract version number

        # Get dependencies
        dependencies = get_resource_dependencies(resource_type, selected_resource, version_num)

        # Display what will be rolled back
        console.print(f"\n[bold cyan]Rollback Plan for '{selected_resource}' v{version_num}[/bold cyan]\n")

        console.print(f"[bold]Main Resource:[/bold]")
        console.print(f"  • {resource_type.replace('_', ' ').title()}: {selected_resource}")

        if dependencies:
            console.print(f"\n[bold]Dependencies ({len(dependencies)}):[/bold]")

            # Check for changes
            changed_deps = []
            missing_deps = []

            for dep in dependencies:
                dep_type = dep["dependency_resource_type"].replace("_", " ").title()
                dep_name = dep["dependency_resource_name"]

                comparison = compare_dependency_with_current(es, dep)

                if not comparison["exists"]:
                    console.print(f"  • [red]{dep_type}: {dep_name} (MISSING - will be recreated)[/red]")
                    missing_deps.append(dep_name)
                elif comparison["changed"]:
                    console.print(f"  • [yellow]{dep_type}: {dep_name} (CHANGED - will be overwritten)[/yellow]")
                    changed_deps.append(dep_name)
                else:
                    console.print(f"  • [green]{dep_type}: {dep_name} (unchanged)[/green]")

            # Display warnings
            if changed_deps or missing_deps:
                console.print(f"\n[bold yellow]⚠️  Warnings:[/bold yellow]")
                if changed_deps:
                    console.print(f"  • {len(changed_deps)} dependencies have changed and will be overwritten")
                if missing_deps:
                    console.print(f"  • {len(missing_deps)} dependencies are missing and will be recreated")
                console.print("\n[dim]This will restore the exact state from when version {version_num} was saved.[/dim]")
        else:
            console.print(f"\n[yellow]No dependencies captured for this version[/yellow]")
            console.print("[dim]Only the main resource will be rolled back.[/dim]")

        # Confirm rollback
        if DRY_RUN_MODE:
            console.print(f"\n[bold yellow]DRY RUN MODE - No changes will be made[/bold yellow]")

        if not confirm_action(f"Proceed with rollback of '{selected_resource}' and {len(dependencies)} dependencies?"):
            console.print("[yellow]Rollback cancelled[/yellow]")
            return

        # Perform rollback
        console.print(f"\n[cyan]Rolling back '{selected_resource}' to version {version_num}...[/cyan]")

        result = rollback_resource_with_dependencies(
            es, resource_type, selected_resource, version_num, dry_run=False
        )

        # Display results
        console.print()
        if result["success"]:
            console.print("[bold green]✅ Rollback completed successfully![/bold green]\n")

            if result["main_resource_restored"]:
                console.print(f"[green]✓ Main resource '{selected_resource}' restored[/green]")

            if result["dependencies_restored"]:
                console.print(f"[green]✓ {len(result['dependencies_restored'])} dependencies restored:[/green]")
                for dep_name in result["dependencies_restored"]:
                    console.print(f"  • {dep_name}")
        else:
            console.print("[bold red]❌ Rollback completed with errors[/bold red]\n")

        # Display warnings
        if result["warnings"]:
            console.print(f"\n[bold yellow]Warnings:[/bold yellow]")
            for warning in result["warnings"]:
                console.print(f"  {warning}")

        # Display errors
        if result["errors"]:
            console.print(f"\n[bold red]Errors:[/bold red]")
            for error in result["errors"]:
                console.print(f"  • {error}")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
