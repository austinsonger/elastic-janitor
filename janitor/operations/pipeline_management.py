"""
Ingest Pipeline Management operations for Elastic Janitor.
Provides comprehensive pipeline management including viewing, editing, version control, and rollback.
"""
import json
import tempfile
import subprocess
import os
from datetime import datetime
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
from ..config import console, GOD_MODE
from ..utils import (
    show_breadcrumb, confirm_action, select_from_list,
    get_text_input, safe_input, paginate_table
)
from ..utils.version_control import (
    save_resource_version_with_dependencies, get_pipeline_versions, get_pipeline_version,
    get_last_known_good_version_for_pipeline as get_last_known_good_version,
    get_version_count, get_resource_dependencies, RESOURCE_TYPE_PIPELINE
)


def option_view_pipeline_details(es):
    """View detailed information about an ingest pipeline."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "View Pipeline Details"])

    console.print("\n[cyan]View Ingest Pipeline Details[/cyan]\n")

    # Fetch all pipelines
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ingest pipelines..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.ingest.get_pipeline()

        pipelines = list(resp.keys())

        if not pipelines:
            console.print("[yellow]🟡 No ingest pipelines found.[/yellow]\n")
            return

        pipelines.sort()

        # Let user select a pipeline
        selected_pipeline = select_from_list(
            "Select pipeline to view:",
            choices=pipelines
        )

        if not selected_pipeline:
            return

        # Get pipeline details
        pipeline_config = resp[selected_pipeline]

        # Display pipeline information
        console.print(f"\n[bold cyan]Pipeline: {selected_pipeline}[/bold cyan]\n")

        # Show description if available
        description = pipeline_config.get("description", "No description")
        console.print(f"[yellow]Description:[/yellow] {description}\n")

        # Show version if available
        version = pipeline_config.get("version")
        if version:
            console.print(f"[yellow]Version:[/yellow] {version}\n")

        # Show processors
        processors = pipeline_config.get("processors", [])
        if processors:
            console.print(f"[yellow]Processors ({len(processors)}):[/yellow]")

            table = Table(box=box.ROUNDED, show_header=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Type", style="cyan")
            table.add_column("Details", style="white")

            for idx, processor in enumerate(processors, 1):
                # Each processor is a dict with one key (the processor type)
                proc_type = list(processor.keys())[0]
                proc_config = processor[proc_type]

                # Extract key details
                details = []
                if isinstance(proc_config, dict):
                    if "field" in proc_config:
                        details.append(f"field: {proc_config['field']}")
                    if "target_field" in proc_config:
                        details.append(f"target: {proc_config['target_field']}")
                    if "pattern" in proc_config:
                        details.append(f"pattern: {proc_config['pattern']}")

                table.add_row(
                    str(idx),
                    proc_type,
                    ", ".join(details) if details else "-"
                )

            console.print(table)
            console.print()

        # Show on_failure processors if available
        on_failure = pipeline_config.get("on_failure", [])
        if on_failure:
            console.print(f"[yellow]On-Failure Processors ({len(on_failure)}):[/yellow]")
            for idx, processor in enumerate(on_failure, 1):
                proc_type = list(processor.keys())[0]
                console.print(f"  {idx}. {proc_type}")
            console.print()

        # Ask if user wants to see full JSON
        if confirm_action("View full JSON configuration?"):
            console.print()
            syntax = Syntax(
                json.dumps(pipeline_config, indent=2),
                "json",
                theme="monokai",
                line_numbers=True
            )
            console.print(Panel(syntax, title=f"Pipeline: {selected_pipeline}", border_style="cyan"))
            console.print()

        # Show version history if available
        version_count = get_version_count(RESOURCE_TYPE_PIPELINE, selected_pipeline)
        if version_count > 0:
            console.print(f"[dim]💾 {version_count} version(s) stored in version history[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")




def option_edit_pipeline(es):
    """Edit an existing ingest pipeline with version control."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Edit Pipeline"])

    console.print("\n[cyan]Edit Ingest Pipeline[/cyan]\n")

    # Fetch all pipelines
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ingest pipelines..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.ingest.get_pipeline()

        pipelines = list(resp.keys())

        if not pipelines:
            console.print("[yellow]🟡 No ingest pipelines found.[/yellow]\n")
            return

        pipelines.sort()

        # Let user select a pipeline
        selected_pipeline = select_from_list(
            "Select pipeline to edit:",
            choices=pipelines
        )

        if not selected_pipeline:
            return

        # Get current pipeline configuration
        current_config = resp[selected_pipeline]

        # Ask if current pipeline is working correctly
        console.print(f"\n[bold]Pipeline: {selected_pipeline}[/bold]\n")
        is_working = confirm_action("Is the current pipeline working correctly?")

        # Always save a backup before editing
        comment = None
        if is_working:
            console.print("\n[green]✓ Saving current state as 'known-good' version...[/green]")
            comment = get_text_input("Optional comment for this version:", default="")
            save_resource_version_with_dependencies(
                es,
                RESOURCE_TYPE_PIPELINE,
                selected_pipeline,
                current_config,
                comment=comment if comment else "Known-good version before edit",
                is_known_good=True
            )
            console.print("[green]✓ Version saved successfully[/green]\n")
        else:
            console.print("\n[yellow]⚠️  Saving backup (not marked as known-good)...[/yellow]")
            save_resource_version_with_dependencies(
                es,
                RESOURCE_TYPE_PIPELINE,
                selected_pipeline,
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

            old_processors = len(current_config.get("processors", []))
            new_processors = len(new_config.get("processors", []))

            if old_processors != new_processors:
                console.print(f"  • Processors: {old_processors} → {new_processors}")

            old_desc = current_config.get("description", "")
            new_desc = new_config.get("description", "")
            if old_desc != new_desc:
                console.print(f"  • Description changed")

            console.print()

            # Ask if user wants to test with simulate API
            if confirm_action("Test pipeline with sample document?"):
                _test_pipeline_simulate(es, selected_pipeline, new_config)

            # Confirm deployment
            if not confirm_action("Deploy this pipeline configuration?"):
                console.print("\n[yellow]⚠️  Cancelled. Pipeline not modified.[/yellow]\n")
                return

            # Deploy pipeline
            if not GOD_MODE:
                console.print("\n[yellow]🔍 DRY-RUN MODE: Would update pipeline[/yellow]")
                console.print(f"[blue]Pipeline: {selected_pipeline}[/blue]")
                console.print(f"[blue]Processors: {new_processors}[/blue]\n")
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[cyan]Updating pipeline..."),
                    transient=True,
                ) as progress:
                    progress.add_task("update", total=None)
                    es.ingest.put_pipeline(id=selected_pipeline, body=new_config)

                console.print(f"\n[green]✅ Pipeline '{selected_pipeline}' updated successfully[/green]\n")

                # Save new version
                save_resource_version_with_dependencies(
                    es,
                    RESOURCE_TYPE_PIPELINE,
                    selected_pipeline,
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



def _test_pipeline_simulate(es, pipeline_name, pipeline_config):
    """Test pipeline using the simulate API."""
    console.print("\n[cyan]Testing pipeline with simulate API...[/cyan]\n")

    # Get sample document from user
    console.print("[yellow]Enter a sample document (JSON):[/yellow]")
    console.print("[dim]Example: {\"message\": \"test log\", \"@timestamp\": \"2024-01-01T00:00:00Z\"}[/dim]\n")

    doc_input = get_text_input("Document JSON:", default='{"message": "test"}')

    if not doc_input:
        return

    try:
        sample_doc = json.loads(doc_input)

        # Use simulate API
        simulate_body = {
            "pipeline": pipeline_config,
            "docs": [{"_source": sample_doc}]
        }

        result = es.ingest.simulate(body=simulate_body)

        # Display results
        if "docs" in result and len(result["docs"]) > 0:
            doc_result = result["docs"][0]

            if "error" in doc_result:
                console.print(f"\n[red]❌ Pipeline Error:[/red]")
                console.print(Panel(
                    json.dumps(doc_result["error"], indent=2),
                    title="Error Details",
                    border_style="red"
                ))
            else:
                console.print(f"\n[green]✅ Pipeline executed successfully[/green]\n")

                output_doc = doc_result.get("doc", {}).get("_source", {})
                syntax = Syntax(
                    json.dumps(output_doc, indent=2),
                    "json",
                    theme="monokai",
                    line_numbers=True
                )
                console.print(Panel(syntax, title="Output Document", border_style="green"))

        console.print()

    except json.JSONDecodeError:
        console.print("\n[red]❌ Invalid JSON document[/red]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Simulation error: {str(e)}[/red]\n")


def option_view_version_history(es):
    """View version history for a pipeline."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "View Version History"])

    console.print("\n[cyan]Pipeline Version History[/cyan]\n")

    # Fetch all pipelines
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ingest pipelines..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.ingest.get_pipeline()

        pipelines = list(resp.keys())

        if not pipelines:
            console.print("[yellow]🟡 No ingest pipelines found.[/yellow]\n")
            return

        pipelines.sort()

        # Let user select a pipeline
        selected_pipeline = select_from_list(
            "Select pipeline to view history:",
            choices=pipelines
        )

        if not selected_pipeline:
            return

        # Get version history
        versions = get_pipeline_versions(selected_pipeline)

        if not versions:
            console.print(f"\n[yellow]🟡 No version history found for '{selected_pipeline}'[/yellow]\n")
            return

        # Display version history
        console.print(f"\n[bold cyan]Version History: {selected_pipeline}[/bold cyan]\n")

        # Define columns for pagination
        columns = [
            {"name": "Ver", "style": "cyan", "width": 5},
            {"name": "Timestamp", "style": "white", "width": 20},
            {"name": "Status", "style": "white", "width": 12},
            {"name": "Processors", "style": "white", "width": 10},
            {"name": "Comment", "style": "dim"}
        ]

        # Build rows from versions
        rows = []
        for version in versions:
            timestamp = datetime.fromisoformat(version["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            status = "[green]✓ Known Good[/green]" if version["is_known_good"] else "[dim]Backup[/dim]"
            processors = len(version["configuration"].get("processors", []))
            comment = version["comment"] or "-"

            rows.append((
                str(version["version_number"]),
                timestamp,
                status,
                str(processors),
                comment[:50] + "..." if len(comment) > 50 else comment
            ))

        paginate_table(rows, columns, page_size=20, title=f"Version History: {selected_pipeline}")

        # Ask if user wants to view a specific version
        if confirm_action("View details of a specific version?"):
            version_num = get_text_input("Enter version number:")
            if version_num and version_num.isdigit():
                version = get_pipeline_version(selected_pipeline, int(version_num))
                if version:
                    console.print()
                    syntax = Syntax(
                        json.dumps(version["configuration"], indent=2),
                        "json",
                        theme="monokai",
                        line_numbers=True
                    )
                    console.print(Panel(
                        syntax,
                        title=f"Version {version_num} - {version['comment'] or 'No comment'}",
                        border_style="cyan"
                    ))
                    console.print()
                else:
                    console.print(f"\n[yellow]🟡 Version {version_num} not found[/yellow]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_rollback_pipeline(es):
    """Rollback a pipeline to a previous version."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Rollback Pipeline"])

    console.print("\n[cyan]Rollback Pipeline to Previous Version[/cyan]\n")

    # Fetch all pipelines
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ingest pipelines..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.ingest.get_pipeline()

        pipelines = list(resp.keys())

        if not pipelines:
            console.print("[yellow]🟡 No ingest pipelines found.[/yellow]\n")
            return

        pipelines.sort()

        # Let user select a pipeline
        selected_pipeline = select_from_list(
            "Select pipeline to rollback:",
            choices=pipelines
        )

        if not selected_pipeline:
            return

        # Get version history
        versions = get_pipeline_versions(selected_pipeline)

        if not versions:
            console.print(f"\n[yellow]🟡 No version history found for '{selected_pipeline}'[/yellow]\n")
            console.print("[dim]Tip: Edit the pipeline first to create version history[/dim]\n")
            return

        # Display version history
        console.print(f"\n[bold cyan]Available Versions: {selected_pipeline}[/bold cyan]\n")

        # Define columns for pagination
        columns = [
            {"name": "Ver", "style": "cyan", "width": 5},
            {"name": "Timestamp", "style": "white", "width": 20},
            {"name": "Status", "style": "white", "width": 15},
            {"name": "Processors", "style": "white", "width": 10},
            {"name": "Comment", "style": "dim"}
        ]

        # Build rows from versions
        rows = []
        for version in versions:
            timestamp = datetime.fromisoformat(version["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            status = "[green]✓ Known Good[/green]" if version["is_known_good"] else "[dim]Backup[/dim]"
            processors = len(version["configuration"].get("processors", []))
            comment = version["comment"] or "-"

            rows.append((
                str(version["version_number"]),
                timestamp,
                status,
                str(processors),
                comment[:40] + "..." if len(comment) > 40 else comment
            ))

        paginate_table(rows, columns, page_size=20, title=f"Available Versions: {selected_pipeline}")

        # Get current pipeline configuration
        current_config = resp[selected_pipeline]
        current_processors = len(current_config.get("processors", []))

        console.print(f"[yellow]Current pipeline has {current_processors} processor(s)[/yellow]\n")

        # Ask which version to rollback to
        version_num = get_text_input("Enter version number to rollback to:")

        if not version_num or not version_num.isdigit():
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        version = get_pipeline_version(selected_pipeline, int(version_num))

        if not version:
            console.print(f"\n[red]❌ Version {version_num} not found[/red]\n")
            return

        # Show what will be restored
        console.print(f"\n[cyan]Rollback Details:[/cyan]")
        console.print(f"  • Version: {version['version_number']}")
        console.print(f"  • Timestamp: {datetime.fromisoformat(version['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"  • Status: {'Known Good' if version['is_known_good'] else 'Backup'}")
        console.print(f"  • Processors: {len(version['configuration'].get('processors', []))}")
        if version['comment']:
            console.print(f"  • Comment: {version['comment']}")
        console.print()

        # Show preview of configuration
        if confirm_action("View configuration preview?"):
            console.print()
            syntax = Syntax(
                json.dumps(version["configuration"], indent=2),
                "json",
                theme="monokai",
                line_numbers=True
            )
            console.print(Panel(syntax, title=f"Version {version_num} Configuration", border_style="cyan"))
            console.print()

        # Confirm rollback
        if not confirm_action(f"Rollback pipeline '{selected_pipeline}' to version {version_num}?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Save current state before rollback
        console.print("\n[cyan]Saving current state before rollback...[/cyan]")
        save_resource_version_with_dependencies(
            es,
            RESOURCE_TYPE_PIPELINE,
            selected_pipeline,
            current_config,
            comment=f"Auto-backup before rollback to v{version_num}",
            is_known_good=False
        )

        # Perform rollback
        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would rollback pipeline[/yellow]")
            console.print(f"[blue]Pipeline: {selected_pipeline}[/blue]")
            console.print(f"[blue]Target Version: {version_num}[/blue]\n")
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Rolling back pipeline..."),
                transient=True,
            ) as progress:
                progress.add_task("rollback", total=None)
                es.ingest.put_pipeline(id=selected_pipeline, body=version["configuration"])

            console.print(f"\n[green]✅ Pipeline '{selected_pipeline}' rolled back to version {version_num}[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_emergency_rollback(es):
    """Quick rollback to last known-good version."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Emergency Rollback"])

    console.print("\n[red bold]⚠️  EMERGENCY ROLLBACK[/red bold]\n")
    console.print("[yellow]This will rollback to the last known-good version[/yellow]\n")

    # Fetch all pipelines
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ingest pipelines..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.ingest.get_pipeline()

        pipelines = list(resp.keys())

        if not pipelines:
            console.print("[yellow]🟡 No ingest pipelines found.[/yellow]\n")
            return

        pipelines.sort()

        # Let user select a pipeline
        selected_pipeline = select_from_list(
            "Select pipeline for emergency rollback:",
            choices=pipelines
        )

        if not selected_pipeline:
            return

        # Get last known-good version
        last_good = get_last_known_good_version(selected_pipeline)

        if not last_good:
            console.print(f"\n[red]❌ No known-good version found for '{selected_pipeline}'[/red]\n")
            console.print("[dim]Tip: Mark a version as 'known-good' when editing the pipeline[/dim]\n")
            return

        # Show what will be restored
        console.print(f"\n[cyan]Last Known-Good Version:[/cyan]")
        console.print(f"  • Version: {last_good['version_number']}")
        console.print(f"  • Timestamp: {datetime.fromisoformat(last_good['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"  • Processors: {len(last_good['configuration'].get('processors', []))}")
        if last_good['comment']:
            console.print(f"  • Comment: {last_good['comment']}")
        console.print()

        # Confirm emergency rollback
        if not confirm_action(f"[red]EMERGENCY ROLLBACK[/red] pipeline '{selected_pipeline}'?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Save current state before rollback
        current_config = resp[selected_pipeline]
        console.print("\n[cyan]Saving current state before emergency rollback...[/cyan]")
        save_resource_version_with_dependencies(
            es,
            RESOURCE_TYPE_PIPELINE,
            selected_pipeline,
            current_config,
            comment=f"Auto-backup before emergency rollback to v{last_good['version_number']}",
            is_known_good=False
        )

        # Perform rollback
        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would perform emergency rollback[/yellow]")
            console.print(f"[blue]Pipeline: {selected_pipeline}[/blue]")
            console.print(f"[blue]Target Version: {last_good['version_number']}[/blue]\n")
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[red]Performing emergency rollback..."),
                transient=True,
            ) as progress:
                progress.add_task("rollback", total=None)
                es.ingest.put_pipeline(id=selected_pipeline, body=last_good["configuration"])

            console.print(f"\n[green]✅ Emergency rollback complete![/green]")
            console.print(f"[green]Pipeline '{selected_pipeline}' restored to version {last_good['version_number']}[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_export_pipeline(es):
    """Export pipeline configuration to JSON file."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Export Pipeline"])

    console.print("\n[cyan]Export Pipeline to JSON File[/cyan]\n")

    # Fetch all pipelines
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ingest pipelines..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.ingest.get_pipeline()

        pipelines = list(resp.keys())

        if not pipelines:
            console.print("[yellow]🟡 No ingest pipelines found.[/yellow]\n")
            return

        pipelines.sort()

        # Let user select a pipeline
        selected_pipeline = select_from_list(
            "Select pipeline to export:",
            choices=pipelines
        )

        if not selected_pipeline:
            return

        # Get pipeline configuration
        pipeline_config = resp[selected_pipeline]

        # Get filename
        default_filename = f"{selected_pipeline}.json"
        filename = get_text_input("Export filename:", default=default_filename)

        if not filename:
            return

        # Ensure .json extension
        if not filename.endswith('.json'):
            filename += '.json'

        # Write to file
        with open(filename, 'w') as f:
            json.dump(pipeline_config, f, indent=2)

        console.print(f"\n[green]✅ Pipeline exported to '{filename}'[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")



def option_import_pipeline(es):
    """Import pipeline configuration from JSON file."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Import Pipeline"])

    console.print("\n[cyan]Import Pipeline from JSON File[/cyan]\n")

    try:
        # Get filename
        filename = get_text_input("Import filename:")

        if not filename:
            return

        # Read file
        try:
            with open(filename, 'r') as f:
                pipeline_config = json.load(f)
        except FileNotFoundError:
            console.print(f"\n[red]❌ File not found: {filename}[/red]\n")
            return
        except json.JSONDecodeError as e:
            console.print(f"\n[red]❌ Invalid JSON: {str(e)}[/red]\n")
            return

        # Validate configuration
        if not isinstance(pipeline_config, dict):
            console.print("[red]❌ Invalid configuration: must be a JSON object[/red]\n")
            return

        # Get pipeline name
        default_name = os.path.splitext(os.path.basename(filename))[0]
        pipeline_name = get_text_input("Pipeline name:", default=default_name)

        if not pipeline_name:
            return

        # Show preview
        console.print(f"\n[cyan]Pipeline Configuration:[/cyan]")
        processors = pipeline_config.get("processors", [])
        console.print(f"  • Processors: {len(processors)}")
        description = pipeline_config.get("description", "No description")
        console.print(f"  • Description: {description}")
        console.print()

        # Check if pipeline already exists
        resp = es.ingest.get_pipeline()
        if pipeline_name in resp:
            console.print(f"[yellow]⚠️  Pipeline '{pipeline_name}' already exists[/yellow]")
            if not confirm_action("Overwrite existing pipeline?"):
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
                return

            # Save existing pipeline as backup
            console.print("\n[cyan]Saving existing pipeline as backup...[/cyan]")
            save_resource_version_with_dependencies(
                es,
                RESOURCE_TYPE_PIPELINE,
                pipeline_name,
                resp[pipeline_name],
                comment="Auto-backup before import",
                is_known_good=False
            )

        # Confirm import
        if not confirm_action(f"Import pipeline '{pipeline_name}'?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Import pipeline
        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would import pipeline[/yellow]")
            console.print(f"[blue]Pipeline: {pipeline_name}[/blue]")
            console.print(f"[blue]Processors: {len(processors)}[/blue]\n")
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Importing pipeline..."),
                transient=True,
            ) as progress:
                progress.add_task("import", total=None)
                es.ingest.put_pipeline(id=pipeline_name, body=pipeline_config)

            console.print(f"\n[green]✅ Pipeline '{pipeline_name}' imported successfully[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def option_clone_pipeline(es):
    """Clone an existing pipeline with a new name."""
    show_breadcrumb(["Main Menu", "Template & Policy Management", "Clone Pipeline"])

    console.print("\n[cyan]Clone Ingest Pipeline[/cyan]\n")

    # Fetch all pipelines
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching ingest pipelines..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            resp = es.ingest.get_pipeline()

        pipelines = list(resp.keys())

        if not pipelines:
            console.print("[yellow]🟡 No ingest pipelines found.[/yellow]\n")
            return

        pipelines.sort()

        # Let user select source pipeline
        source_pipeline = select_from_list(
            "Select pipeline to clone:",
            choices=pipelines
        )

        if not source_pipeline:
            return

        # Get source configuration
        source_config = resp[source_pipeline]

        # Get new pipeline name
        default_name = f"{source_pipeline}-copy"
        new_pipeline_name = get_text_input("New pipeline name:", default=default_name)

        if not new_pipeline_name:
            return

        # Check if new name already exists
        if new_pipeline_name in resp:
            console.print(f"\n[red]❌ Pipeline '{new_pipeline_name}' already exists[/red]\n")
            return

        # Show what will be cloned
        console.print(f"\n[cyan]Clone Details:[/cyan]")
        console.print(f"  • Source: {source_pipeline}")
        console.print(f"  • Target: {new_pipeline_name}")
        console.print(f"  • Processors: {len(source_config.get('processors', []))}")
        console.print()

        # Confirm clone
        if not confirm_action(f"Clone pipeline '{source_pipeline}' to '{new_pipeline_name}'?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Clone pipeline
        if not GOD_MODE:
            console.print("\n[yellow]🔍 DRY-RUN MODE: Would clone pipeline[/yellow]")
            console.print(f"[blue]Source: {source_pipeline}[/blue]")
            console.print(f"[blue]Target: {new_pipeline_name}[/blue]\n")
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Cloning pipeline..."),
                transient=True,
            ) as progress:
                progress.add_task("clone", total=None)
                es.ingest.put_pipeline(id=new_pipeline_name, body=source_config)

            console.print(f"\n[green]✅ Pipeline cloned successfully[/green]")
            console.print(f"[green]New pipeline: '{new_pipeline_name}'[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")
