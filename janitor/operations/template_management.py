"""
Index Template Management with Version Control for Elastic Janitor.
Provides comprehensive template management including version control, rollback, and editing capabilities.
"""
import json
import tempfile
import subprocess
import os
from datetime import datetime
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax

from ..config import console, GOD_MODE
from ..utils import show_breadcrumb, confirm_action, select_from_list, get_text_input
from ..utils.version_control import (
    save_resource_version_with_dependencies, get_resource_versions, get_resource_version,
    get_last_known_good_version, get_version_count, get_resource_dependencies,
    RESOURCE_TYPE_INDEX_TEMPLATE, RESOURCE_TYPE_COMPONENT_TEMPLATE
)


def option_view_index_template_details(es):
    """View details of an index template with version history."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "View Index Template Details"])

    console.print("\n[cyan]View Index Template Details[/cyan]\n")

    # Fetch all index templates
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching index templates..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.indices.get_index_template()

        templates = [t["name"] for t in resp.get("index_templates", [])]

        if not templates:
            console.print("[yellow]🟡 No index templates found.[/yellow]\n")
            return

        templates.sort()

        # Let user select a template
        selected_template = select_from_list(
            "Select index template to view:",
            choices=templates
        )

        if not selected_template:
            return

        # Get template details
        template_resp = es.indices.get_index_template(name=selected_template)
        template_data = template_resp["index_templates"][0]
        template_config = template_data["index_template"]

        # Display basic info
        console.print(f"\n[bold cyan]Index Template: {selected_template}[/bold cyan]\n")

        # Show index patterns
        index_patterns = template_config.get("index_patterns", [])
        console.print(f"[yellow]Index Patterns:[/yellow] {', '.join(index_patterns)}")

        # Show priority
        priority = template_config.get("priority", 0)
        console.print(f"[yellow]Priority:[/yellow] {priority}")

        # Show composed of (component templates)
        composed_of = template_config.get("composed_of", [])
        if composed_of:
            console.print(f"[yellow]Composed Of:[/yellow] {', '.join(composed_of)}")

        # Show version history count
        version_count = get_version_count(RESOURCE_TYPE_INDEX_TEMPLATE, selected_template)
        console.print(f"[yellow]Version History:[/yellow] {version_count} version(s) stored\n")

        # Show template structure
        table = Table(box=box.ROUNDED, show_header=True, title="Template Structure")
        table.add_column("Component", style="cyan", width=20)
        table.add_column("Status", style="white")

        template_def = template_config.get("template", {})

        if "settings" in template_def:
            settings_count = len(template_def["settings"])
            table.add_row("Settings", f"✓ {settings_count} setting(s)")
        else:
            table.add_row("Settings", "[dim]Not defined[/dim]")

        if "mappings" in template_def:
            properties = template_def["mappings"].get("properties", {})
            table.add_row("Mappings", f"✓ {len(properties)} field(s)")
        else:
            table.add_row("Mappings", "[dim]Not defined[/dim]")

        if "aliases" in template_def:
            aliases_count = len(template_def["aliases"])
            table.add_row("Aliases", f"✓ {aliases_count} alias(es)")
        else:
            table.add_row("Aliases", "[dim]Not defined[/dim]")

        console.print(table)
        console.print()

        # Ask if user wants to see full JSON
        if confirm_action("View full JSON configuration?"):
            console.print()
            syntax = Syntax(
                json.dumps(template_config, indent=2),
                "json",
                theme="monokai",
                line_numbers=True
            )
            console.print(Panel(syntax, title=f"Template: {selected_template}", border_style="cyan"))
            console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_view_component_template_details(es):
    """View details of a component template with version history."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "View Component Template Details"])

    console.print("\n[cyan]View Component Template Details[/cyan]\n")

    # Fetch all component templates
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching component templates..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.cluster.get_component_template()


        templates = [t["name"] for t in resp.get("component_templates", [])]

        if not templates:
            console.print("[yellow]🟡 No component templates found.[/yellow]\n")
            return

        templates.sort()

        # Let user select a template
        selected_template = select_from_list(
            "Select component template to view:",
            choices=templates
        )

        if not selected_template:
            return

        # Get template details
        template_resp = es.cluster.get_component_template(name=selected_template)
        template_data = template_resp["component_templates"][0]
        template_config = template_data["component_template"]

        # Display basic info
        console.print(f"\n[bold cyan]Component Template: {selected_template}[/bold cyan]\n")

        # Show version
        version = template_config.get("version", "Not specified")
        console.print(f"[yellow]Version:[/yellow] {version}")

        # Show version history count
        version_count = get_version_count(RESOURCE_TYPE_COMPONENT_TEMPLATE, selected_template)
        console.print(f"[yellow]Version History:[/yellow] {version_count} version(s) stored\n")

        # Show template structure
        table = Table(box=box.ROUNDED, show_header=True, title="Template Structure")
        table.add_column("Component", style="cyan", width=20)
        table.add_column("Status", style="white")

        template_def = template_config.get("template", {})

        if "settings" in template_def:
            settings_count = len(template_def["settings"])
            table.add_row("Settings", f"✓ {settings_count} setting(s)")
        else:
            table.add_row("Settings", "[dim]Not defined[/dim]")

        if "mappings" in template_def:
            properties = template_def["mappings"].get("properties", {})
            table.add_row("Mappings", f"✓ {len(properties)} field(s)")
        else:
            table.add_row("Mappings", "[dim]Not defined[/dim]")

        if "aliases" in template_def:
            aliases_count = len(template_def["aliases"])
            table.add_row("Aliases", f"✓ {aliases_count} alias(es)")
        else:
            table.add_row("Aliases", "[dim]Not defined[/dim]")

        console.print(table)
        console.print()

        # Ask if user wants to see full JSON
        if confirm_action("View full JSON configuration?"):
            console.print()
            syntax = Syntax(
                json.dumps(template_config, indent=2),
                "json",
                theme="monokai",
                line_numbers=True
            )
            console.print(Panel(syntax, title=f"Component Template: {selected_template}", border_style="cyan"))
            console.print()

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_edit_index_template(es):
    """Edit an existing index template with version control."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Edit Index Template"])

    console.print("\n[cyan]Edit Index Template[/cyan]\n")

    # Fetch all index templates
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching index templates..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.indices.get_index_template()

        templates = [t["name"] for t in resp.get("index_templates", [])]

        if not templates:
            console.print("[yellow]🟡 No index templates found.[/yellow]\n")
            return

        templates.sort()

        # Let user select a template
        selected_template = select_from_list(
            "Select index template to edit:",
            choices=templates
        )

        if not selected_template:
            return

        # Get current template configuration
        template_resp = es.indices.get_index_template(name=selected_template)
        current_config = template_resp["index_templates"][0]["index_template"]

        # Ask if current template is working correctly
        console.print(f"\n[bold]Template: {selected_template}[/bold]\n")
        is_working = confirm_action("Is the current template working correctly?")

        # Always save a backup before editing
        comment = None
        if is_working:
            console.print("\n[green]✓ Saving current state as 'known-good' version...[/green]")
            comment = get_text_input("Optional comment for this version:", default="")
            save_resource_version_with_dependencies(
                es,
                RESOURCE_TYPE_INDEX_TEMPLATE,
                selected_template,
                current_config,
                comment=comment if comment else "Known-good version before edit",
                is_known_good=True
            )
            console.print("[green]✓ Version saved successfully[/green]\n")
        else:
            console.print("\n[yellow]⚠️  Saving backup (not marked as known-good)...[/yellow]")
            save_resource_version_with_dependencies(
                es,
                RESOURCE_TYPE_INDEX_TEMPLATE,
                selected_template,
                current_config,
                comment="Backup before edit (not working correctly)",
                is_known_good=False
            )
            console.print("[yellow]✓ Backup saved[/yellow]\n")

        # Create temporary file with current configuration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(current_config, tmp_file, indent=2)
            tmp_file_path = tmp_file.name

        try:
            # Open in editor
            editor = os.environ.get('EDITOR', 'nano')
            console.print(f"[cyan]Opening editor ({editor})...[/cyan]")
            console.print("[dim]Save and exit the editor when done.[/dim]\n")

            subprocess.call([editor, tmp_file_path])

            # Read modified configuration
            with open(tmp_file_path, 'r') as f:
                new_config = json.load(f)

            # Validate JSON structure
            if not isinstance(new_config, dict):
                console.print("[red]❌ Invalid configuration: must be a JSON object[/red]\n")
                return

            # Show diff summary
            console.print("\n[cyan]Changes detected:[/cyan]")

            old_patterns = current_config.get("index_patterns", [])
            new_patterns = new_config.get("index_patterns", [])
            if old_patterns != new_patterns:
                console.print(f"  • Index patterns: {old_patterns} → {new_patterns}")

            old_priority = current_config.get("priority", 0)
            new_priority = new_config.get("priority", 0)
            if old_priority != new_priority:
                console.print(f"  • Priority: {old_priority} → {new_priority}")

            console.print()

            # Confirm deployment
            if not confirm_action("Deploy this template configuration?"):
                console.print("\n[yellow]⚠️  Cancelled. Template not modified.[/yellow]\n")
                return

            # Deploy template
            if not GOD_MODE:
                console.print("\n[yellow]🔍 DRY-RUN MODE: Would update template[/yellow]")
                console.print(f"[blue]Template: {selected_template}[/blue]\n")
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[cyan]Updating template..."),
                    transient=True,
                ) as progress:
                    progress.add_task("update", total=None)
                    es.indices.put_index_template(name=selected_template, body=new_config)

                console.print(f"\n[green]✅ Template '{selected_template}' updated successfully[/green]\n")

                # Save new version
                save_resource_version_with_dependencies(
                    es,
                    RESOURCE_TYPE_INDEX_TEMPLATE,
                    selected_template,
                    new_config,
                    comment="Updated via editor",
                    is_known_good=False
                )

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except json.JSONDecodeError as e:
        console.print(f"\n[red]❌ Invalid JSON: {str(e)}[/red]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_rollback_index_template(es):
    """Rollback an index template to a previous version."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Rollback Index Template"])

    console.print("\n[cyan]Rollback Index Template to Previous Version[/cyan]\n")

    try:
        # Fetch all index templates
        with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching index templates..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.indices.get_index_template()

        templates = [t["name"] for t in resp.get("index_templates", [])]
        if not templates:
            console.print("[yellow]🟡 No index templates found.[/yellow]\n")
            return

        templates.sort()
        selected_template = select_from_list("Select template to rollback:", choices=templates)
        if not selected_template:
            return

        # Get version history
        versions = get_resource_versions(RESOURCE_TYPE_INDEX_TEMPLATE, selected_template)
        if not versions:
            console.print(f"\n[yellow]🟡 No version history found for '{selected_template}'[/yellow]\n")
            return

        # Display version history
        console.print(f"\n[bold cyan]Available Versions: {selected_template}[/bold cyan]\n")
        table = Table(box=box.ROUNDED, show_header=True)
        table.add_column("Ver", style="cyan", width=5)
        table.add_column("Timestamp", style="white", width=20)
        table.add_column("Status", style="white", width=15)
        table.add_column("Comment", style="dim")

        for version in versions:
            timestamp = datetime.fromisoformat(version["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            status = "[green]✓ Known Good[/green]" if version["is_known_good"] else "[dim]Backup[/dim]"
            comment = version["comment"] or "-"
            table.add_row(str(version["version_number"]), timestamp, status, comment[:40] + "..." if len(comment) > 40 else comment)

        console.print(table)
        console.print()

        # Ask which version to rollback to
        version_num = get_text_input("Enter version number to rollback to:")
        if not version_num or not version_num.isdigit():
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        version = get_resource_version(RESOURCE_TYPE_INDEX_TEMPLATE, selected_template, int(version_num))
        if not version:
            console.print(f"\n[red]❌ Version {version_num} not found[/red]\n")
            return

        # Confirm rollback
        if not confirm_action(f"Rollback template '{selected_template}' to version {version_num}?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Save current state before rollback
        current_resp = es.indices.get_index_template(name=selected_template)
        current_config = current_resp["index_templates"][0]["index_template"]
        save_resource_version_with_dependencies(es, RESOURCE_TYPE_INDEX_TEMPLATE, selected_template, current_config,
                            comment=f"Auto-backup before rollback to v{version_num}", is_known_good=False)

        # Perform rollback
        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would rollback template[/yellow]\n")
        else:
            with Progress(SpinnerColumn(), TextColumn("[cyan]Rolling back template..."), transient=True) as progress:
                progress.add_task("rollback", total=None)
                es.indices.put_index_template(name=selected_template, body=version["configuration"])
            console.print(f"\n[green]✅ Template '{selected_template}' rolled back to version {version_num}[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_export_index_template(es):
    """Export index template configuration to JSON file."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Export Index Template"])

    console.print("\n[cyan]Export Index Template to JSON File[/cyan]\n")

    try:
        with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching index templates..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.indices.get_index_template()

        templates = [t["name"] for t in resp.get("index_templates", [])]
        if not templates:
            console.print("[yellow]🟡 No index templates found.[/yellow]\n")
            return

        templates.sort()
        selected_template = select_from_list("Select template to export:", choices=templates)
        if not selected_template:
            return

        # Get template configuration
        template_resp = es.indices.get_index_template(name=selected_template)
        template_config = template_resp["index_templates"][0]["index_template"]

        # Get filename
        default_filename = f"{selected_template}.json"
        filename = get_text_input("Export filename:", default=default_filename)
        if not filename:
            return

        if not filename.endswith('.json'):
            filename += '.json'

        # Write to file
        with open(filename, 'w') as f:
            json.dump(template_config, f, indent=2)

        console.print(f"\n[green]✅ Template exported to '{filename}'[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_import_index_template(es):
    """Import index template configuration from JSON file."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Import Index Template"])

    console.print("\n[cyan]Import Index Template from JSON File[/cyan]\n")

    try:
        filename = get_text_input("Import filename:")
        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                template_config = json.load(f)
        except FileNotFoundError:
            console.print(f"\n[red]❌ File not found: {filename}[/red]\n")
            return
        except json.JSONDecodeError as e:
            console.print(f"\n[red]❌ Invalid JSON: {str(e)}[/red]\n")
            return

        if not isinstance(template_config, dict):
            console.print("[red]❌ Invalid configuration: must be a JSON object[/red]\n")
            return

        default_name = os.path.splitext(os.path.basename(filename))[0]
        template_name = get_text_input("Template name:", default=default_name)
        if not template_name:
            return

        # Check if template already exists
        resp = es.indices.get_index_template()
        existing_templates = [t["name"] for t in resp.get("index_templates", [])]
        if template_name in existing_templates:
            console.print(f"[yellow]⚠️  Template '{template_name}' already exists[/yellow]")
            if not confirm_action("Overwrite existing template?"):
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
                return
            # Save existing as backup
            existing_resp = es.indices.get_index_template(name=template_name)
            existing_config = existing_resp["index_templates"][0]["index_template"]
            save_resource_version_with_dependencies(es, RESOURCE_TYPE_INDEX_TEMPLATE, template_name, existing_config,
                                comment="Auto-backup before import", is_known_good=False)

        if not confirm_action(f"Import template '{template_name}'?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would import template[/yellow]\n")
        else:
            with Progress(SpinnerColumn(), TextColumn("[cyan]Importing template..."), transient=True) as progress:
                progress.add_task("import", total=None)
                es.indices.put_index_template(name=template_name, body=template_config)
            console.print(f"\n[green]✅ Template '{template_name}' imported successfully[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_edit_component_template(es):
    """Edit an existing component template with version control."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Edit Component Template"])

    console.print("\n[cyan]Edit Component Template[/cyan]\n")

    try:
        with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching component templates..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.cluster.get_component_template()

        templates = [t["name"] for t in resp.get("component_templates", [])]
        if not templates:
            console.print("[yellow]🟡 No component templates found.[/yellow]\n")
            return

        templates.sort()
        selected_template = select_from_list("Select component template to edit:", choices=templates)
        if not selected_template:
            return

        # Get current template configuration
        template_resp = es.cluster.get_component_template(name=selected_template)
        current_config = template_resp["component_templates"][0]["component_template"]

        # Ask if current template is working correctly
        console.print(f"\n[bold]Template: {selected_template}[/bold]\n")
        is_working = confirm_action("Is the current template working correctly?")

        # Always save a backup before editing
        if is_working:
            console.print("\n[green]✓ Saving current state as 'known-good' version...[/green]")
            comment = get_text_input("Optional comment for this version:", default="")
            save_resource_version_with_dependencies(es, RESOURCE_TYPE_COMPONENT_TEMPLATE, selected_template, current_config,
                                comment=comment if comment else "Known-good version before edit", is_known_good=True)
            console.print("[green]✓ Version saved successfully[/green]\n")
        else:
            console.print("\n[yellow]⚠️  Saving backup (not marked as known-good)...[/yellow]")
            save_resource_version_with_dependencies(es, RESOURCE_TYPE_COMPONENT_TEMPLATE, selected_template, current_config,
                                comment="Backup before edit (not working correctly)", is_known_good=False)
            console.print("[yellow]✓ Backup saved[/yellow]\n")

        # Create temporary file with current configuration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(current_config, tmp_file, indent=2)
            tmp_file_path = tmp_file.name

        try:
            # Open in editor
            editor = os.environ.get('EDITOR', 'nano')
            console.print(f"[cyan]Opening editor ({editor})...[/cyan]")
            console.print("[dim]Save and exit the editor when done.[/dim]\n")
            subprocess.call([editor, tmp_file_path])

            # Read modified configuration
            with open(tmp_file_path, 'r') as f:
                new_config = json.load(f)

            if not isinstance(new_config, dict):
                console.print("[red]❌ Invalid configuration: must be a JSON object[/red]\n")
                return

            # Confirm deployment
            if not confirm_action("Deploy this template configuration?"):
                console.print("\n[yellow]⚠️  Cancelled. Template not modified.[/yellow]\n")
                return

            # Deploy template
            if not GOD_MODE:
                console.print("\n[yellow]🔍 DRY-RUN MODE: Would update template[/yellow]\n")
            else:
                with Progress(SpinnerColumn(), TextColumn("[cyan]Updating template..."), transient=True) as progress:
                    progress.add_task("update", total=None)
                    es.cluster.put_component_template(name=selected_template, body=new_config)
                console.print(f"\n[green]✅ Template '{selected_template}' updated successfully[/green]\n")
                save_resource_version_with_dependencies(es, RESOURCE_TYPE_COMPONENT_TEMPLATE, selected_template, new_config,
                                    comment="Updated via editor", is_known_good=False)
        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except json.JSONDecodeError as e:
        console.print(f"\n[red]❌ Invalid JSON: {str(e)}[/red]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_rollback_component_template(es):
    """Rollback a component template to a previous version."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Rollback Component Template"])

    console.print("\n[cyan]Rollback Component Template to Previous Version[/cyan]\n")

    try:
        with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching component templates..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.cluster.get_component_template()

        templates = [t["name"] for t in resp.get("component_templates", [])]
        if not templates:
            console.print("[yellow]🟡 No component templates found.[/yellow]\n")
            return

        templates.sort()
        selected_template = select_from_list("Select template to rollback:", choices=templates)
        if not selected_template:
            return

        # Get version history
        versions = get_resource_versions(RESOURCE_TYPE_COMPONENT_TEMPLATE, selected_template)
        if not versions:
            console.print(f"\n[yellow]🟡 No version history found for '{selected_template}'[/yellow]\n")
            return

        # Display version history
        console.print(f"\n[bold cyan]Available Versions: {selected_template}[/bold cyan]\n")
        table = Table(box=box.ROUNDED, show_header=True)
        table.add_column("Ver", style="cyan", width=5)
        table.add_column("Timestamp", style="white", width=20)
        table.add_column("Status", style="white", width=15)
        table.add_column("Comment", style="dim")

        for version in versions:
            timestamp = datetime.fromisoformat(version["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            status = "[green]✓ Known Good[/green]" if version["is_known_good"] else "[dim]Backup[/dim]"
            comment = version["comment"] or "-"
            table.add_row(str(version["version_number"]), timestamp, status, comment[:40] + "..." if len(comment) > 40 else comment)

        console.print(table)
        console.print()

        # Ask which version to rollback to
        version_num = get_text_input("Enter version number to rollback to:")
        if not version_num or not version_num.isdigit():
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        version = get_resource_version(RESOURCE_TYPE_COMPONENT_TEMPLATE, selected_template, int(version_num))
        if not version:
            console.print(f"\n[red]❌ Version {version_num} not found[/red]\n")
            return

        if not confirm_action(f"Rollback template '{selected_template}' to version {version_num}?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Save current state before rollback
        current_resp = es.cluster.get_component_template(name=selected_template)
        current_config = current_resp["component_templates"][0]["component_template"]
        save_resource_version_with_dependencies(es, RESOURCE_TYPE_COMPONENT_TEMPLATE, selected_template, current_config,
                            comment=f"Auto-backup before rollback to v{version_num}", is_known_good=False)

        # Perform rollback
        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would rollback template[/yellow]\n")
        else:
            with Progress(SpinnerColumn(), TextColumn("[cyan]Rolling back template..."), transient=True) as progress:
                progress.add_task("rollback", total=None)
                es.cluster.put_component_template(name=selected_template, body=version["configuration"])
            console.print(f"\n[green]✅ Template '{selected_template}' rolled back to version {version_num}[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_export_component_template(es):
    """Export component template configuration to JSON file."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Export Component Template"])

    console.print("\n[cyan]Export Component Template to JSON File[/cyan]\n")

    try:
        with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching component templates..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.cluster.get_component_template()

        templates = [t["name"] for t in resp.get("component_templates", [])]
        if not templates:
            console.print("[yellow]🟡 No component templates found.[/yellow]\n")
            return

        templates.sort()
        selected_template = select_from_list("Select template to export:", choices=templates)
        if not selected_template:
            return

        # Get template configuration
        template_resp = es.cluster.get_component_template(name=selected_template)
        template_config = template_resp["component_templates"][0]["component_template"]

        # Get filename
        default_filename = f"{selected_template}.json"
        filename = get_text_input("Export filename:", default=default_filename)
        if not filename:
            return

        if not filename.endswith('.json'):
            filename += '.json'

        # Write to file
        with open(filename, 'w') as f:
            json.dump(template_config, f, indent=2)

        console.print(f"\n[green]✅ Template exported to '{filename}'[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_import_component_template(es):
    """Import component template configuration from JSON file."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Import Component Template"])

    console.print("\n[cyan]Import Component Template from JSON File[/cyan]\n")

    try:
        filename = get_text_input("Import filename:")
        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                template_config = json.load(f)
        except FileNotFoundError:
            console.print(f"\n[red]❌ File not found: {filename}[/red]\n")
            return
        except json.JSONDecodeError as e:
            console.print(f"\n[red]❌ Invalid JSON: {str(e)}[/red]\n")
            return

        if not isinstance(template_config, dict):
            console.print("[red]❌ Invalid configuration: must be a JSON object[/red]\n")
            return

        default_name = os.path.splitext(os.path.basename(filename))[0]
        template_name = get_text_input("Template name:", default=default_name)
        if not template_name:
            return

        # Check if template already exists
        resp = es.cluster.get_component_template()
        existing_templates = [t["name"] for t in resp.get("component_templates", [])]
        if template_name in existing_templates:
            console.print(f"[yellow]⚠️  Template '{template_name}' already exists[/yellow]")
            if not confirm_action("Overwrite existing template?"):
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
                return
            # Save existing as backup
            existing_resp = es.cluster.get_component_template(name=template_name)
            existing_config = existing_resp["component_templates"][0]["component_template"]
            save_resource_version_with_dependencies(es, RESOURCE_TYPE_COMPONENT_TEMPLATE, template_name, existing_config,
                                comment="Auto-backup before import", is_known_good=False)

        if not confirm_action(f"Import template '{template_name}'?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would import template[/yellow]\n")
        else:
            with Progress(SpinnerColumn(), TextColumn("[cyan]Importing template..."), transient=True) as progress:
                progress.add_task("import", total=None)
                es.cluster.put_component_template(name=template_name, body=template_config)
            console.print(f"\n[green]✅ Template '{template_name}' imported successfully[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")

