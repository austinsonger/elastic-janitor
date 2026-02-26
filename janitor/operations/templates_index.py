"""
Template management operations for Elastic Janitor - Index Templates.
Index templates and component templates.
"""
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
from ..config import console, MAX_DELETE_LIMIT, GOD_MODE
from ..utils import is_system, confirm_delete, safe_input, show_breadcrumb, select_from_list


def option_list_templates(es):
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

    console.print()
    table = Table(title="Index Templates", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Template Name", style="cyan", no_wrap=False)
    table.add_column("Index Patterns", style="yellow")

    for t in templates:
        name = t["name"]
        patterns = t["index_template"].get("index_patterns", [])
        table.add_row(name, ", ".join(patterns))

    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 5: Delete index templates by match
# ------------------------------------------------------------



def option_delete_templates(es):
    resp = es.indices.get_index_template()
    templates = resp.get("index_templates", [])

    if not templates:
        console.print("\n[yellow]🟡 No templates found.[/yellow]\n")
        return

    match = safe_input("Delete templates containing what text? ").strip()
    if not match:
        return

    matches = [t["name"] for t in templates if match in t["name"]]

    if not matches:
        console.print("\n[yellow]🟡 No matching templates.[/yellow]\n")
        return

    if len(matches) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} templates in one run.[/red]\n")
        return

    console.print("\n[red]Templates that match:[/red]\n")
    for name in matches:
        console.print(f"  [red]•[/red] {name}")

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global GOD_MODE
    if not GOD_MODE:
        console.print("\n[yellow]🔍 SAFE MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(matches)} index templates:[/blue]\n")
        for name in matches[:10]:
            console.print(f"  [blue]•[/blue] {name}")
        if len(matches) > 10:
            console.print(f"  [dim]... and {len(matches) - 10} more[/dim]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[red]Deleting templates...", total=len(matches))

        for name in matches:
            progress.update(task, description=f"[red]Deleting: {name[:50]}...")
            es.indices.delete_index_template(name=name)
            progress.advance(task)

    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 6: List component templates
# ------------------------------------------------------------



def option_list_component_templates(es):
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching component templates..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        resp = es.cluster.get_component_template()

    component_templates = resp.get("component_templates", [])

    if not component_templates:
        console.print("\n[yellow]🟡 No component templates found.[/yellow]\n")
        return

    console.print()
    table = Table(title="Component Templates", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Template Name", style="cyan", no_wrap=False)

    for t in component_templates:
        name = t["name"]
        table.add_row(name)

    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 7: Delete component templates by match
# ------------------------------------------------------------



def option_delete_component_templates(es):
    resp = es.cluster.get_component_template()
    component_templates = resp.get("component_templates", [])

    if not component_templates:
        console.print("\n[yellow]🟡 No component templates found.[/yellow]\n")
        return

    match = safe_input("Delete component templates containing what text? ").strip()
    if not match:
        return

    matches = [t["name"] for t in component_templates if match in t["name"]]

    if not matches:
        console.print("\n[yellow]🟡 No matching component templates.[/yellow]\n")
        return

    if len(matches) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} component templates in one run.[/red]\n")
        return

    console.print("\n[red]Component templates that match:[/red]\n")
    for name in matches:
        console.print(f"  [red]•[/red] {name}")

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global GOD_MODE
    if not GOD_MODE:
        console.print("\n[yellow]🔍 SAFE MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(matches)} component templates:[/blue]\n")
        for name in matches[:10]:
            console.print(f"  [blue]•[/blue] {name}")
        if len(matches) > 10:
            console.print(f"  [dim]... and {len(matches) - 10} more[/dim]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[red]Deleting component templates...", total=len(matches))

        for name in matches:
            progress.update(task, description=f"[red]Deleting: {name[:50]}...")
            es.cluster.delete_component_template(name=name)
            progress.advance(task)

    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 8: List ILM policies
# ------------------------------------------------------------



