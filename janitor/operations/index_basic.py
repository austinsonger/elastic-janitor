"""
Index management operations for Elastic Janitor - Basic Operations.
Listing, viewing, and basic analysis of indices.
"""
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console
from ..utils import safe_input, show_breadcrumb, select_from_list, is_system
from ..utils.formatters import size_to_bytes


def option_list_largest_indices(es):
    n_input = safe_input("Show top how many? (default 25): ").strip()
    n = int(n_input) if n_input else 25

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching indices..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,store.size,pri.store.size,docs.count")

    def size_to_bytes(s):
        if not s:
            return 0
        s = s.strip().lower()
        mult = 1
        if s.endswith("kb"):
            mult = 1024
            num = s[:-2]
        elif s.endswith("mb"):
            mult = 1024**2
            num = s[:-2]
        elif s.endswith("gb"):
            mult = 1024**3
            num = s[:-2]
        elif s.endswith("tb"):
            mult = 1024**4
            num = s[:-2]
        else:
            num = s
        try:
            return float(num) * mult
        except Exception:
            return 0

    for r in rows:
        r["_bytes"] = size_to_bytes(r.get("store.size"))

    rows.sort(key=lambda x: x["_bytes"], reverse=True)

    console.print()
    table = Table(title=f"Top {n} Largest Indices", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Index Name", style="cyan", no_wrap=False)
    table.add_column("Total Size", justify="right", style="yellow")
    table.add_column("Primary Size", justify="right", style="yellow")
    table.add_column("Doc Count", justify="right", style="blue")

    for r in rows[:n]:
        name = r.get("index", "")
        size = r.get("store.size", "")
        pri = r.get("pri.store.size", "")
        docs = r.get("docs.count", "0")
        table.add_row(name, size, pri, docs)

    console.print(table)
    console.print()


# ------------------------------------------------------------
# Option 4: List index templates
# ------------------------------------------------------------



def option_index_settings_viewer(es):
    """View and compare index settings."""
    show_breadcrumb(["Main Menu", "Index Management", "Index Settings Viewer"])

    # Get all indices
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching indices..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        indices_list = es.cat.indices(format="json", h="index")

    index_names = [idx["index"] for idx in indices_list if not is_system(idx["index"])]

    if not index_names:
        console.print("[yellow]No indices found.[/yellow]\n")
        return

    # Select indices to view
    selected = select_from_list(
        "Select indices to view settings (use space to select, enter to confirm):",
        choices=index_names[:100] + (["... (showing first 100)"] if len(index_names) > 100 else []),
        multi=True
    )

    if not selected or not any(s != "... (showing first 100)" for s in selected):
        return

    selected = [s for s in selected if s != "... (showing first 100)"]

    # Fetch settings
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching settings..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        settings_data = {}
        for idx_name in selected:
            try:
                settings = es.indices.get_settings(index=idx_name)
                settings_data[idx_name] = settings[idx_name]["settings"]["index"]
            except Exception as e:
                console.print(f"[red]Error fetching settings for {idx_name}: {e}[/red]")

    # Display settings
    console.print()
    for idx_name, settings in settings_data.items():
        console.print(f"\n[bold cyan]Index:[/bold cyan] {idx_name}")

        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Setting", style="yellow")
        table.add_column("Value", style="white")

        # Key settings to display
        key_settings = [
            ("number_of_shards", settings.get("number_of_shards", "N/A")),
            ("number_of_replicas", settings.get("number_of_replicas", "N/A")),
            ("refresh_interval", settings.get("refresh_interval", "N/A")),
            ("codec", settings.get("codec", "default")),
        ]

        for key, value in key_settings:
            table.add_row(key, str(value))

        console.print(table)

    console.print()




def option_duplicate_index_detector(es):
    """Identify potentially duplicate indices."""
    show_breadcrumb(["Main Menu", "Index Management", "Duplicate Index Detector"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing indices for duplicates..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        indices = es.cat.indices(format="json", h="index,docs.count,store.size,creation.date")

    # Group by similar patterns
    pattern_groups = defaultdict(list)

    for idx in indices:
        idx_name = idx.get("index", "")
        if is_system(idx_name):
            continue

        # Extract base pattern (remove dates, numbers at end)
        import re
        base_pattern = re.sub(r'[-_]\d{4}[-_.]\d{2}[-_.]\d{2}.*$', '', idx_name)
        base_pattern = re.sub(r'[-_]\d{8,}.*$', '', base_pattern)
        base_pattern = re.sub(r'[-_]\d+$', '', base_pattern)

        pattern_groups[base_pattern].append(idx)

    # Find potential duplicates
    duplicates = {k: v for k, v in pattern_groups.items() if len(v) > 1}

    if not duplicates:
        console.print("\n[green]✅ No potential duplicate patterns found.[/green]\n")
        return

    console.print()
    console.print(f"[cyan]Found {len(duplicates)} patterns with multiple indices:[/cyan]\n")

    for pattern, indices_list in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        console.print(f"\n[bold yellow]Pattern:[/bold yellow] {pattern}")
        console.print(f"[dim]Indices: {len(indices_list)}[/dim]")

        table = Table(box=box.SIMPLE)
        table.add_column("Index Name", style="cyan")
        table.add_column("Docs", justify="right")
        table.add_column("Size", justify="right")

        for idx in indices_list[:5]:
            table.add_row(
                idx.get("index", ""),
                idx.get("docs.count", "0"),
                idx.get("store.size", "0b")
            )

        console.print(table)

        if len(indices_list) > 5:
            console.print(f"[dim]... and {len(indices_list) - 5} more[/dim]")

    console.print()




