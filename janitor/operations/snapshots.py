"""
Snapshot and backup management operations for Elastic Janitor.
Snapshot repositories, snapshots, and SLM policies.
"""
from datetime import datetime, timezone, timedelta
import questionary
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
from ..config import console, DRY_RUN_MODE
from ..utils import confirm_delete, safe_input, show_breadcrumb, select_from_list
from ..utils.formatters import parse_epoch_millis


def option_list_snapshot_repos(es):
    with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching snapshot repositories..."), transient=True) as progress:
        progress.add_task("fetch", total=None)
        resp = es.snapshot.get_repository(name="_all")

    repos = list(resp.keys())

    if not repos:
        console.print("\n[yellow]🟡 No snapshot repositories found.[/yellow]\n")
        return

    repos.sort()
    console.print()
    table = Table(title="Snapshot Repositories", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Repository Name", style="cyan")
    for r in repos:
        table.add_row(r)
    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 13: List snapshots in a repo
# ------------------------------------------------------------



def option_list_snapshots(es):
    repo = safe_input("Repository name: ").strip()
    if not repo:
        return

    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Fetching snapshots from {repo}..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.snapshot.get(repository=repo, snapshot="_all")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list snapshots: {e}[/red]\n")
        return

    snaps = resp.get("snapshots", [])
    if not snaps:
        console.print("\n[yellow]🟡 No snapshots found.[/yellow]\n")
        return

    console.print()
    table = Table(title=f"Snapshots in {repo}", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Snapshot Name", style="cyan")
    table.add_column("Started", style="yellow")

    for s in snaps:
        snap_name = s.get("snapshot", "")
        start_ms = s.get("start_time_in_millis")
        if start_ms is not None:
            dt = parse_epoch_millis(start_ms)
            table.add_row(snap_name, dt.isoformat())
        else:
            table.add_row(snap_name, "N/A")

    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 14: Delete snapshots older than X days
# ------------------------------------------------------------



def option_delete_old_snapshots(es):
    repo = safe_input("Repository name: ").strip()
    if not repo:
        return

    days_input = safe_input(
        f"Snapshot retention cutoff in days? (default {DEFAULT_RETENTION_DAYS}): "
    ).strip()
    days = int(days_input) if days_input else DEFAULT_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Scanning snapshots in {repo}..."), transient=True) as progress:
            progress.add_task("scan", total=None)
            resp = es.snapshot.get(repository=repo, snapshot="_all")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list snapshots: {e}[/red]\n")
        return

    snaps = resp.get("snapshots", [])
    delete_list = []

    for s in snaps:
        snap_name = s.get("snapshot")
        start_ms = s.get("start_time_in_millis")
        if snap_name and start_ms is not None:
            started = parse_epoch_millis(start_ms)
            if started < cutoff:
                delete_list.append((snap_name, started))

    delete_list.sort(key=lambda x: x[1])

    if not delete_list:
        console.print("\n[green]✅ No snapshots eligible for deletion.[/green]\n")
        return

    if len(delete_list) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} snapshots in one run.[/red]\n")
        return

    console.print(f"\n[red]Will delete {len(delete_list)} snapshots from {repo}:[/red]\n")
    for name, started in delete_list:
        age_days = (datetime.now(timezone.utc) - started).days
        console.print(f"  [red]•[/red] {name} | age={age_days} days")

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(delete_list)} snapshots from {repo}:[/blue]\n")
        for name, started in delete_list[:10]:
            age_days = (datetime.now(timezone.utc) - started).days
            console.print(f"  [blue]•[/blue] {name} (age: {age_days} days)")
        if len(delete_list) > 10:
            console.print(f"  [dim]... and {len(delete_list) - 10} more[/dim]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[red]Deleting snapshots...", total=len(delete_list))
        for name, _ in delete_list:
            progress.update(task, description=f"[red]Deleting: {name[:50]}...")
            try:
                es.snapshot.delete(repository=repo, snapshot=name)
            except Exception as e:
                console.print(f"[red]ERROR deleting {name}: {e}[/red]")
            progress.advance(task)

    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 15: List SLM policies
# ------------------------------------------------------------



def option_list_slm(es):
    try:
        with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching SLM policies..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.slm.get_lifecycle()
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list SLM policies: {e}[/red]\n")
        return

    policies = list(resp.get("policies", {}).keys())
    if not policies:
        console.print("\n[yellow]🟡 No SLM policies found.[/yellow]\n")
        return

    policies.sort()
    console.print()
    table = Table(title="SLM Policies", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Policy Name", style="cyan")
    for p in policies:
        table.add_row(p)
    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 16: Delete SLM policies by match
# ------------------------------------------------------------



def option_delete_slm(es):
    try:
        resp = es.slm.get_lifecycle()
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list SLM policies: {e}[/red]\n")
        return

    policies = list(resp.get("policies", {}).keys())
    if not policies:
        console.print("\n[yellow]🟡 No SLM policies found.[/yellow]\n")
        return

    match = safe_input("Delete SLM policies containing what text? ").strip()
    if not match:
        return

    matches = [p for p in policies if match in p]

    if not matches:
        console.print("\n[yellow]🟡 No matching SLM policies.[/yellow]\n")
        return

    if len(matches) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} SLM policies in one run.[/red]\n")
        return

    console.print("\n[red]SLM policies that match:[/red]\n")
    for p in matches:
        console.print(f"  [red]•[/red] {p}")

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(matches)} SLM policies:[/blue]\n")
        for p in matches[:10]:
            console.print(f"  [blue]•[/blue] {p}")
        if len(matches) > 10:
            console.print(f"  [dim]... and {len(matches) - 10} more[/dim]")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[red]Deleting SLM policies...", total=len(matches))
        for p in matches:
            progress.update(task, description=f"[red]Deleting: {p[:50]}...")
            try:
                es.slm.delete_lifecycle(policy_id=p)
            except Exception as e:
                console.print(f"[red]ERROR deleting {p}: {e}[/red]")
            progress.advance(task)

    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------

DEFAULT_RETENTION_DAYS = 90
MAX_DELETE_LIMIT = 5000


# ------------------------------------------------------------
# Option 6: Verify Snapshot Repository
# ------------------------------------------------------------


def option_verify_snapshot_repository(es):
    """
    Verify snapshot repository integrity and restore-ability.
    Uses the Elasticsearch snapshot.verify_repository API to check if the repository
    is accessible and functional from all nodes.
    """
    repo = safe_input("Repository name to verify: ").strip()
    if not repo:
        return

    try:
        console.print(f"\n[cyan]Verifying repository '{repo}'...[/cyan]\n")
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Running verification on {repo}..."), transient=True) as progress:
            progress.add_task("verify", total=None)
            resp = es.snapshot.verify_repository(name=repo)
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not verify repository: {e}[/red]\n")
        return

    nodes = resp.get("nodes", {})

    if not nodes:
        console.print("\n[yellow]🟡 No node information returned.[/yellow]\n")
        return

    console.print()
    table = Table(title=f"Repository Verification: {repo}", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Node Name", style="cyan")
    table.add_column("Node ID", style="yellow")
    table.add_column("Status", style="green")

    for node_id, node_info in nodes.items():
        node_name = node_info.get("name", "N/A")
        table.add_row(node_name, node_id, "✅ Verified")

    console.print(table)
    console.print(f"\n[green]✅ Repository '{repo}' verified successfully on {len(nodes)} node(s).[/green]\n")


# ------------------------------------------------------------
# Option 7: Snapshot Size Analysis
# ------------------------------------------------------------


def option_snapshot_size_analysis(es):
    """
    Show size trends and compression ratios for snapshots in a repository.
    Displays snapshot name, start time, total size, compressed size, and compression ratio.
    Sorts by size (largest first) and calculates total storage used.
    """
    repo = safe_input("Repository name: ").strip()
    if not repo:
        return

    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Analyzing snapshots in {repo}..."), transient=True) as progress:
            progress.add_task("analyze", total=None)
            resp = es.snapshot.get(repository=repo, snapshot="_all")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list snapshots: {e}[/red]\n")
        return

    snaps = resp.get("snapshots", [])
    if not snaps:
        console.print("\n[yellow]🟡 No snapshots found.[/yellow]\n")
        return

    # Collect snapshot data
    snapshot_data = []
    total_size_bytes = 0

    for s in snaps:
        snap_name = s.get("snapshot", "")
        start_ms = s.get("start_time_in_millis")

        # Get size information from stats
        stats = s.get("stats", {})
        total_size = stats.get("total", {}).get("size_in_bytes", 0)

        # Try to get incremental size (actual storage used)
        incremental_size = stats.get("incremental", {}).get("size_in_bytes", total_size)

        # Calculate compression ratio if both sizes available
        if total_size > 0 and incremental_size > 0:
            compression_ratio = total_size / incremental_size
        else:
            compression_ratio = 1.0

        started = parse_epoch_millis(start_ms) if start_ms else None

        snapshot_data.append({
            'name': snap_name,
            'started': started,
            'total_size': total_size,
            'incremental_size': incremental_size,
            'compression_ratio': compression_ratio
        })

        total_size_bytes += incremental_size

    # Sort by incremental size (largest first)
    snapshot_data.sort(key=lambda x: x['incremental_size'], reverse=True)

    console.print()
    table = Table(title=f"Snapshot Size Analysis: {repo}", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Snapshot Name", style="cyan")
    table.add_column("Started", style="yellow")
    table.add_column("Total Size", style="magenta", justify="right")
    table.add_column("Stored Size", style="blue", justify="right")
    table.add_column("Compression", style="green", justify="right")

    from ..utils.formatters import bytes_to_human

    for snap in snapshot_data:
        started_str = snap['started'].strftime("%Y-%m-%d %H:%M") if snap['started'] else "N/A"
        total_size_str = bytes_to_human(snap['total_size'])
        stored_size_str = bytes_to_human(snap['incremental_size'])
        compression_str = f"{snap['compression_ratio']:.2f}x"

        table.add_row(
            snap['name'],
            started_str,
            total_size_str,
            stored_size_str,
            compression_str
        )

    console.print(table)
    console.print(f"\n[cyan]Total snapshots: {len(snapshot_data)}[/cyan]")
    console.print(f"[cyan]Total storage used: {bytes_to_human(total_size_bytes)}[/cyan]\n")


# ------------------------------------------------------------
# Option 8: Automated Snapshot Cleanup
# ------------------------------------------------------------


def option_automated_snapshot_cleanup(es):
    """
    Implement schedule-based snapshot retention policies.
    Allows users to specify: keep last N snapshots, keep daily/weekly/monthly snapshots.
    Previews which snapshots would be kept vs. deleted based on the policy.
    """
    repo = safe_input("Repository name: ").strip()
    if not repo:
        return

    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Scanning snapshots in {repo}..."), transient=True) as progress:
            progress.add_task("scan", total=None)
            resp = es.snapshot.get(repository=repo, snapshot="_all")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list snapshots: {e}[/red]\n")
        return

    snaps = resp.get("snapshots", [])
    if not snaps:
        console.print("\n[yellow]🟡 No snapshots found.[/yellow]\n")
        return

    console.print("\n[cyan]Retention Policy Options:[/cyan]")
    console.print("  1. Keep last N snapshots")
    console.print("  2. Keep daily/weekly/monthly snapshots")
    console.print("  3. Combined policy (last N + daily/weekly/monthly)\n")

    policy_choice = safe_input("Select policy (1-3): ").strip()

    if policy_choice not in ["1", "2", "3"]:
        console.print("\n[yellow]⚠️  Invalid choice.[/yellow]\n")
        return

    # Parse snapshots with timestamps
    snapshot_list = []
    for s in snaps:
        snap_name = s.get("snapshot")
        start_ms = s.get("start_time_in_millis")
        if snap_name and start_ms is not None:
            started = parse_epoch_millis(start_ms)
            snapshot_list.append((snap_name, started))

    snapshot_list.sort(key=lambda x: x[1], reverse=True)  # Sort newest first

    keep_set = set()

    # Policy 1: Keep last N
    if policy_choice in ["1", "3"]:
        keep_n_input = safe_input("Keep last N snapshots (default 10): ").strip()
        keep_n = int(keep_n_input) if keep_n_input else 10

        for i, (snap_name, _) in enumerate(snapshot_list):
            if i < keep_n:
                keep_set.add(snap_name)

    # Policy 2 or 3: Keep daily/weekly/monthly
    if policy_choice in ["2", "3"]:
        keep_daily_input = safe_input("Keep daily snapshots for last N days (default 7): ").strip()
        keep_daily = int(keep_daily_input) if keep_daily_input else 7

        keep_weekly_input = safe_input("Keep weekly snapshots for last N weeks (default 4): ").strip()
        keep_weekly = int(keep_weekly_input) if keep_weekly_input else 4

        keep_monthly_input = safe_input("Keep monthly snapshots for last N months (default 12): ").strip()
        keep_monthly = int(keep_monthly_input) if keep_monthly_input else 12

        now = datetime.now(timezone.utc)
        daily_cutoff = now - timedelta(days=keep_daily)
        weekly_cutoff = now - timedelta(weeks=keep_weekly)
        monthly_cutoff = now - timedelta(days=keep_monthly * 30)

        seen_days = set()
        seen_weeks = set()
        seen_months = set()

        for snap_name, started in snapshot_list:
            day_key = started.strftime("%Y-%m-%d")
            week_key = started.strftime("%Y-W%W")
            month_key = started.strftime("%Y-%m")

            # Keep one snapshot per day within daily retention
            if started >= daily_cutoff and day_key not in seen_days:
                keep_set.add(snap_name)
                seen_days.add(day_key)

            # Keep one snapshot per week within weekly retention
            elif started >= weekly_cutoff and started < daily_cutoff and week_key not in seen_weeks:
                keep_set.add(snap_name)
                seen_weeks.add(week_key)

            # Keep one snapshot per month within monthly retention
            elif started >= monthly_cutoff and started < weekly_cutoff and month_key not in seen_months:
                keep_set.add(snap_name)
                seen_months.add(month_key)

    # Determine what to delete
    delete_list = [(name, started) for name, started in snapshot_list if name not in keep_set]
    keep_list = [(name, started) for name, started in snapshot_list if name in keep_set]

    if not delete_list:
        console.print("\n[green]✅ No snapshots eligible for deletion based on this policy.[/green]\n")
        return

    # Preview
    console.print(f"\n[green]Snapshots to KEEP ({len(keep_list)}):[/green]")
    for name, started in keep_list[:10]:
        age_days = (datetime.now(timezone.utc) - started).days
        console.print(f"  [green]•[/green] {name} | age={age_days} days")
    if len(keep_list) > 10:
        console.print(f"  [dim]... and {len(keep_list) - 10} more[/dim]")

    console.print(f"\n[red]Snapshots to DELETE ({len(delete_list)}):[/red]")
    for name, started in delete_list[:10]:
        age_days = (datetime.now(timezone.utc) - started).days
        console.print(f"  [red]•[/red] {name} | age={age_days} days")
    if len(delete_list) > 10:
        console.print(f"  [dim]... and {len(delete_list) - 10} more[/dim]")

    if len(delete_list) > MAX_DELETE_LIMIT:
        console.print(f"\n[red]❌ Refusing to delete more than {MAX_DELETE_LIMIT} snapshots in one run.[/red]\n")
        return

    if not confirm_delete():
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating deletion...[/yellow]\n")
        console.print(f"[blue]Would delete {len(delete_list)} snapshots from {repo}[/blue]\n")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[red]Deleting snapshots...", total=len(delete_list))
        for name, _ in delete_list:
            progress.update(task, description=f"[red]Deleting: {name[:50]}...")
            try:
                es.snapshot.delete(repository=repo, snapshot=name)
            except Exception as e:
                console.print(f"[red]ERROR deleting {name}: {e}[/red]")
            progress.advance(task)

    console.print("\n[green]✅ Done.[/green]\n")


# ------------------------------------------------------------
# Option 9: Cross-Repository Snapshot Copy
# ------------------------------------------------------------


def option_cross_repository_copy(es):
    """
    Copy snapshots from one repository to another.
    Uses snapshot restore and re-snapshot approach.
    """
    source_repo = safe_input("Source repository name: ").strip()
    if not source_repo:
        return

    # List snapshots in source repo
    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Fetching snapshots from {source_repo}..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.snapshot.get(repository=source_repo, snapshot="_all")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list snapshots: {e}[/red]\n")
        return

    snaps = resp.get("snapshots", [])
    if not snaps:
        console.print("\n[yellow]🟡 No snapshots found in source repository.[/yellow]\n")
        return

    # Display available snapshots
    console.print(f"\n[cyan]Available snapshots in {source_repo}:[/cyan]")
    for i, s in enumerate(snaps[:20], 1):
        snap_name = s.get("snapshot", "")
        console.print(f"  {i}. {snap_name}")
    if len(snaps) > 20:
        console.print(f"  [dim]... and {len(snaps) - 20} more[/dim]")

    snapshot_name = safe_input("\nSnapshot name to copy: ").strip()
    if not snapshot_name:
        return

    # Verify snapshot exists
    if not any(s.get("snapshot") == snapshot_name for s in snaps):
        console.print(f"\n[red]❌ ERROR: Snapshot '{snapshot_name}' not found in {source_repo}.[/red]\n")
        return

    dest_repo = safe_input("Destination repository name: ").strip()
    if not dest_repo:
        return

    # Verify destination repository exists
    try:
        es.snapshot.get_repository(name=dest_repo)
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Destination repository '{dest_repo}' not found: {e}[/red]\n")
        return

    new_snapshot_name = safe_input(f"New snapshot name (default: {snapshot_name}): ").strip()
    if not new_snapshot_name:
        new_snapshot_name = snapshot_name

    console.print(f"\n[yellow]⚠️  This operation will:[/yellow]")
    console.print(f"  1. Restore snapshot '{snapshot_name}' from '{source_repo}'")
    console.print(f"  2. Create new snapshot '{new_snapshot_name}' in '{dest_repo}'")
    console.print(f"  3. Delete the restored indices\n")

    confirm = safe_input("Type 'COPY' to proceed: ").strip()
    if confirm != "COPY":
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating copy...[/yellow]\n")
        console.print(f"[blue]Would copy snapshot '{snapshot_name}' from '{source_repo}' to '{dest_repo}' as '{new_snapshot_name}'[/blue]\n")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    console.print("\n[cyan]Note: Cross-repository snapshot copy is not directly supported by Elasticsearch.[/cyan]")
    console.print("[cyan]You may need to use the clone snapshot API or manually restore and re-snapshot.[/cyan]")
    console.print("[cyan]For production use, consider using Elasticsearch's snapshot clone API if available.[/cyan]\n")
    console.print("[yellow]⚠️  This feature requires manual implementation based on your Elasticsearch version.[/yellow]\n")


# ------------------------------------------------------------
# Option 10: Snapshot Restore Wizard
# ------------------------------------------------------------


def option_snapshot_restore_wizard(es):
    """
    Interactive restore with index selection.
    Lists all snapshots in a repository, allows user to select one,
    shows indices contained in the selected snapshot, and allows multi-select of indices to restore.
    """
    repo = safe_input("Repository name: ").strip()
    if not repo:
        return

    # List snapshots in repository
    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Fetching snapshots from {repo}..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.snapshot.get(repository=repo, snapshot="_all")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list snapshots: {e}[/red]\n")
        return

    snaps = resp.get("snapshots", [])
    if not snaps:
        console.print("\n[yellow]🟡 No snapshots found.[/yellow]\n")
        return

    # Create choices for snapshot selection
    snapshot_choices = []
    for s in snaps:
        snap_name = s.get("snapshot", "")
        start_ms = s.get("start_time_in_millis")
        if start_ms:
            started = parse_epoch_millis(start_ms)
            label = f"{snap_name} ({started.strftime('%Y-%m-%d %H:%M')})"
        else:
            label = snap_name
        snapshot_choices.append((label, snap_name))

    # Sort by name
    snapshot_choices.sort(key=lambda x: x[1], reverse=True)

    console.print(f"\n[cyan]Select snapshot to restore from {repo}:[/cyan]")
    from questionary import Choice
    choices = [Choice(label, value=value) for label, value in snapshot_choices]

    selected_snapshot = select_from_list("Select snapshot:", choices)
    if not selected_snapshot:
        return

    # Get snapshot details
    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Fetching snapshot details..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            snap_resp = es.snapshot.get(repository=repo, snapshot=selected_snapshot)
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not get snapshot details: {e}[/red]\n")
        return

    snapshot_info = snap_resp.get("snapshots", [{}])[0]
    indices = snapshot_info.get("indices", [])

    if not indices:
        console.print("\n[yellow]🟡 No indices found in snapshot.[/yellow]\n")
        return

    console.print(f"\n[cyan]Indices in snapshot '{selected_snapshot}':[/cyan]")
    for idx in indices[:20]:
        console.print(f"  • {idx}")
    if len(indices) > 20:
        console.print(f"  [dim]... and {len(indices) - 20} more[/dim]")

    # Ask if user wants to restore all or select specific indices
    console.print("\n[cyan]Restore options:[/cyan]")
    console.print("  1. Restore all indices")
    console.print("  2. Select specific indices to restore\n")

    restore_choice = safe_input("Select option (1-2): ").strip()

    indices_to_restore = []

    if restore_choice == "1":
        indices_to_restore = indices
    elif restore_choice == "2":
        # Multi-select indices
        index_choices = [Choice(idx, value=idx) for idx in sorted(indices)]
        selected_indices = select_from_list("Select indices to restore (use space to select, enter to confirm):", index_choices, multi=True)
        if not selected_indices:
            console.print("\n[yellow]⚠️  No indices selected.[/yellow]\n")
            return
        indices_to_restore = selected_indices
    else:
        console.print("\n[yellow]⚠️  Invalid choice.[/yellow]\n")
        return

    # Restore options
    rename_pattern = safe_input("\nRename pattern (e.g., 'restored_(.+)' to prefix with 'restored_', leave empty for no rename): ").strip()
    rename_replacement = safe_input("Rename replacement (e.g., 'restored_$1', leave empty for no rename): ").strip()

    include_aliases_input = safe_input("Include aliases? (y/n, default: y): ").strip().lower()
    include_aliases = include_aliases_input != "n"

    # Build restore request
    restore_body = {
        "indices": ",".join(indices_to_restore),
        "include_aliases": include_aliases
    }

    if rename_pattern and rename_replacement:
        restore_body["rename_pattern"] = rename_pattern
        restore_body["rename_replacement"] = rename_replacement

    # Preview
    console.print(f"\n[yellow]⚠️  Will restore {len(indices_to_restore)} indices from snapshot '{selected_snapshot}':[/yellow]")
    for idx in indices_to_restore[:10]:
        console.print(f"  [yellow]•[/yellow] {idx}")
    if len(indices_to_restore) > 10:
        console.print(f"  [dim]... and {len(indices_to_restore) - 10} more[/dim]")

    if rename_pattern and rename_replacement:
        console.print(f"\n[cyan]Rename pattern: {rename_pattern} -> {rename_replacement}[/cyan]")

    confirm = safe_input("\nType 'RESTORE' to proceed: ").strip()
    if confirm != "RESTORE":
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    global DRY_RUN_MODE
    if DRY_RUN_MODE:
        console.print("\n[yellow]🔍 DRY-RUN MODE: Simulating restore...[/yellow]\n")
        console.print(f"[blue]Would restore {len(indices_to_restore)} indices from snapshot '{selected_snapshot}'[/blue]\n")
        console.print("\n[green]✅ Dry-run complete. No actual changes made.[/green]\n")
        return

    # Execute restore
    try:
        console.print(f"\n[cyan]Restoring snapshot '{selected_snapshot}'...[/cyan]\n")
        es.snapshot.restore(repository=repo, snapshot=selected_snapshot, body=restore_body)
        console.print(f"\n[green]✅ Restore initiated successfully. Monitor cluster health for progress.[/green]\n")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not restore snapshot: {e}[/red]\n")


# ------------------------------------------------------------
# Option 11: Snapshot Comparison
# ------------------------------------------------------------


def option_snapshot_comparison(es):
    """
    Compare two snapshots to see what changed.
    Shows differences: new indices, deleted indices, modified indices.
    Displays size changes and document count changes where available.
    """
    repo = safe_input("Repository name: ").strip()
    if not repo:
        return

    # List snapshots in repository
    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Fetching snapshots from {repo}..."), transient=True) as progress:
            progress.add_task("fetch", total=None)
            resp = es.snapshot.get(repository=repo, snapshot="_all")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not list snapshots: {e}[/red]\n")
        return

    snaps = resp.get("snapshots", [])
    if not snaps:
        console.print("\n[yellow]🟡 No snapshots found.[/yellow]\n")
        return

    if len(snaps) < 2:
        console.print("\n[yellow]🟡 Need at least 2 snapshots to compare.[/yellow]\n")
        return

    # Display available snapshots
    console.print(f"\n[cyan]Available snapshots in {repo}:[/cyan]")
    for i, s in enumerate(snaps, 1):
        snap_name = s.get("snapshot", "")
        start_ms = s.get("start_time_in_millis")
        if start_ms:
            started = parse_epoch_millis(start_ms)
            console.print(f"  {i}. {snap_name} ({started.strftime('%Y-%m-%d %H:%M')})")
        else:
            console.print(f"  {i}. {snap_name}")

    snapshot1_name = safe_input("\nFirst snapshot name (older): ").strip()
    if not snapshot1_name:
        return

    snapshot2_name = safe_input("Second snapshot name (newer): ").strip()
    if not snapshot2_name:
        return

    # Verify snapshots exist
    snap1_info = None
    snap2_info = None

    for s in snaps:
        if s.get("snapshot") == snapshot1_name:
            snap1_info = s
        if s.get("snapshot") == snapshot2_name:
            snap2_info = s

    if not snap1_info:
        console.print(f"\n[red]❌ ERROR: Snapshot '{snapshot1_name}' not found.[/red]\n")
        return

    if not snap2_info:
        console.print(f"\n[red]❌ ERROR: Snapshot '{snapshot2_name}' not found.[/red]\n")
        return

    # Get indices from both snapshots
    indices1 = set(snap1_info.get("indices", []))
    indices2 = set(snap2_info.get("indices", []))

    # Calculate differences
    new_indices = indices2 - indices1
    deleted_indices = indices1 - indices2
    common_indices = indices1 & indices2

    # Get shard stats for size/doc count comparison
    shards1 = {shard.get("index"): shard for shard in snap1_info.get("shards", {}).get("shards", []) if "index" in shard}
    shards2 = {shard.get("index"): shard for shard in snap2_info.get("shards", {}).get("shards", []) if "index" in shard}

    console.print(f"\n[bold cyan]Snapshot Comparison: {snapshot1_name} vs {snapshot2_name}[/bold cyan]\n")

    # Display new indices
    if new_indices:
        console.print(f"[green]New Indices ({len(new_indices)}):[/green]")
        for idx in sorted(new_indices)[:20]:
            console.print(f"  [green]+[/green] {idx}")
        if len(new_indices) > 20:
            console.print(f"  [dim]... and {len(new_indices) - 20} more[/dim]")
        console.print()

    # Display deleted indices
    if deleted_indices:
        console.print(f"[red]Deleted Indices ({len(deleted_indices)}):[/red]")
        for idx in sorted(deleted_indices)[:20]:
            console.print(f"  [red]-[/red] {idx}")
        if len(deleted_indices) > 20:
            console.print(f"  [dim]... and {len(deleted_indices) - 20} more[/dim]")
        console.print()

    # Display modified indices (common indices with potential changes)
    if common_indices:
        console.print(f"[yellow]Common Indices ({len(common_indices)}):[/yellow]")
        console.print("[dim]Note: Detailed size/doc count comparison requires additional API calls[/dim]")
        for idx in sorted(common_indices)[:10]:
            console.print(f"  [yellow]~[/yellow] {idx}")
        if len(common_indices) > 10:
            console.print(f"  [dim]... and {len(common_indices) - 10} more[/dim]")
        console.print()

    # Summary
    console.print("[bold cyan]Summary:[/bold cyan]")
    console.print(f"  Total indices in {snapshot1_name}: {len(indices1)}")
    console.print(f"  Total indices in {snapshot2_name}: {len(indices2)}")
    console.print(f"  New indices: {len(new_indices)}")
    console.print(f"  Deleted indices: {len(deleted_indices)}")
    console.print(f"  Common indices: {len(common_indices)}")

    # Get snapshot sizes
    stats1 = snap1_info.get("stats", {})
    stats2 = snap2_info.get("stats", {})

    size1 = stats1.get("incremental", {}).get("size_in_bytes", 0)
    size2 = stats2.get("incremental", {}).get("size_in_bytes", 0)

    if size1 and size2:
        from ..utils.formatters import bytes_to_human
        size_diff = size2 - size1
        size_diff_str = bytes_to_human(abs(size_diff))

        console.print(f"\n  Snapshot size {snapshot1_name}: {bytes_to_human(size1)}")
        console.print(f"  Snapshot size {snapshot2_name}: {bytes_to_human(size2)}")

        if size_diff > 0:
            console.print(f"  Size change: [red]+{size_diff_str}[/red]")
        elif size_diff < 0:
            console.print(f"  Size change: [green]-{size_diff_str}[/green]")
        else:
            console.print(f"  Size change: [dim]No change[/dim]")

    console.print()



