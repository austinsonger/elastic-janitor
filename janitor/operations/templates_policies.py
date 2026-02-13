"""
Template management operations for Elastic Janitor - Policies & Pipelines.
ILM policies and ingest pipelines.
"""
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
from ..config import console, MAX_DELETE_LIMIT, DRY_RUN_MODE
from ..utils import confirm_delete, safe_input, show_breadcrumb, select_from_list


def option_list_ilm(es):
    with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching ILM policies..."), transient=True) as progress:
        progress.add_task("fetch", total=None)
        resp = es.ilm.get_lifecycle()

    policies = list(resp.keys())

    if not policies:
        console.print("\n[yellow]🟡 No ILM policies found.[/yellow]\n")
        return

    policies.sort()
    console.print()
    table = Table(title="ILM Policies", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Policy Name", style="cyan")
    for p in policies:
        table.add_row(p)
    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 9: Delete ILM policies by match
# ------------------------------------------------------------



def option_delete_ilm(es):
    resp = es.ilm.get_lifecycle()
    policies = list(resp.keys())

    if not policies:
        console.print("\n[yellow]🟡 No ILM policies found.[/yellow]\n")
        return

    match = safe_input("Delete ILM policies containing what text? ").strip()
    if not match:
        return

    matches = [p for p in policies if match in p]

    if not matches:
        console.print("\n[yellow]🟡 No matching ILM policies.[/yellow]\n")
        return

    if len(matches) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} ILM policies in one run.[/red]\n")
        return

    console.print("\n[red]Policies that match:[/red]\n")
    for p in matches:
        console.print(f"  [red]•[/red] {p}")

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(matches)} ILM policies:[/blue]\n")
        for p in matches[:10]:
            console.print(f"  [blue]•[/blue] {p}")
        if len(matches) > 10:
            console.print(f"  [dim]... and {len(matches) - 10} more[/dim]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[red]Deleting ILM policies...", total=len(matches))
        for p in matches:
            progress.update(task, description=f"[red]Deleting: {p[:50]}...")
            es.ilm.delete_lifecycle(name=p)
            progress.advance(task)
    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 10: List ingest pipelines
# ------------------------------------------------------------



def option_list_pipelines(es):
    with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching ingest pipelines..."), transient=True) as progress:
        progress.add_task("fetch", total=None)
        resp = es.ingest.get_pipeline()

    pipelines = list(resp.keys())

    if not pipelines:
        console.print("\n[yellow]🟡 No ingest pipelines found.[/yellow]\n")
        return

    pipelines.sort()
    console.print()
    table = Table(title="Ingest Pipelines", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Pipeline Name", style="cyan")
    for p in pipelines:
        table.add_row(p)
    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 11: Delete ingest pipelines by match
# ------------------------------------------------------------



def option_delete_pipelines(es):
    resp = es.ingest.get_pipeline()
    pipelines = list(resp.keys())

    if not pipelines:
        console.print("\n[yellow]🟡 No ingest pipelines found.[/yellow]\n")
        return

    match = safe_input("Delete ingest pipelines containing what text? ").strip()
    if not match:
        return

    matches = [p for p in pipelines if match in p]

    if not matches:
        console.print("\n[yellow]🟡 No matching pipelines.[/yellow]\n")
        return

    if len(matches) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} ingest pipelines in one run.[/red]\n")
        return

    console.print("\n[red]Pipelines that match:[/red]\n")
    for p in matches:
        console.print(f"  [red]•[/red] {p}")

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(matches)} ingest pipelines:[/blue]\n")
        for p in matches[:10]:
            console.print(f"  [blue]•[/blue] {p}")
        if len(matches) > 10:
            console.print(f"  [dim]... and {len(matches) - 10} more[/dim]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[red]Deleting pipelines...", total=len(matches))
        for p in matches:
            progress.update(task, description=f"[red]Deleting: {p[:50]}...")
            es.ingest.delete_pipeline(id=p)
            progress.advance(task)
    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 12: List snapshot repositories
# ------------------------------------------------------------



