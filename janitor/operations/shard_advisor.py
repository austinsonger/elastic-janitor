"""
Shard Rebalancing Advisor for Elastic Janitor.
Analyzes current shard distribution and recommends optimal shard counts,
allocation strategies, and rebalancing actions.
"""
from datetime import datetime, timezone
from collections import defaultdict
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, GOD_MODE, PROTECT_SYSTEM
from ..utils import (
    safe_input, is_system, confirm_action, show_breadcrumb,
    select_from_list, get_number_input, get_text_input, bytes_to_human,
    log_operation,
)
from ..core import get_all_indices_info


# ── Target ranges ───────────────────────────────────────────────────
TARGET_SHARD_SIZE_MIN_GB = 10
TARGET_SHARD_SIZE_MAX_GB = 50
TARGET_SHARD_SIZE_IDEAL_GB = 30
MAX_SHARDS_PER_NODE = 600


def _get_shard_allocation(es):
    """Get detailed shard allocation data."""
    shards = es.cat.shards(format="json", bytes="b")
    allocation = es.cat.allocation(format="json", bytes="b")
    return shards, allocation


def _get_node_info(es):
    """Get node details including roles and resources."""
    nodes = es.cat.nodes(format="json", bytes="b", h="id,name,heap.percent,ram.percent,cpu,disk.total,disk.used,disk.avail,disk.used_percent,node.role,master")
    return nodes


def _calculate_optimal_shards(total_size_bytes, target_gb=TARGET_SHARD_SIZE_IDEAL_GB):
    """Calculate optimal primary shard count for given index size."""
    target_bytes = target_gb * 1024 * 1024 * 1024
    if total_size_bytes <= 0:
        return 1
    optimal = max(1, round(total_size_bytes / target_bytes))
    return optimal


def _analyze_distribution_balance(shards_by_node):
    """Analyze how evenly shards are distributed across nodes."""
    if not shards_by_node:
        return {"balanced": True, "variance": 0, "recommendation": ""}

    counts = list(shards_by_node.values())
    if len(counts) < 2:
        return {"balanced": True, "variance": 0, "recommendation": ""}

    avg = sum(counts) / len(counts)
    variance = sum((c - avg) ** 2 for c in counts) / len(counts)
    std_dev = variance ** 0.5
    cv = (std_dev / avg * 100) if avg > 0 else 0  # Coefficient of variation

    balanced = cv < 20  # Less than 20% variance is acceptable
    recommendation = ""
    if not balanced:
        most = max(shards_by_node, key=shards_by_node.get)
        least = min(shards_by_node, key=shards_by_node.get)
        recommendation = (
            f"Rebalance from '{most}' ({shards_by_node[most]} shards) "
            f"to '{least}' ({shards_by_node[least]} shards)"
        )

    return {
        "balanced": balanced,
        "variance": round(cv, 1),
        "std_dev": round(std_dev, 1),
        "avg": round(avg, 1),
        "recommendation": recommendation,
    }


# ── Interactive menu operations ─────────────────────────────────────

def option_shard_distribution_analysis(es):
    """Analyze current shard distribution across nodes."""
    show_breadcrumb(["Main Menu", "Shard Rebalancing Advisor", "Distribution Analysis"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing shard distribution..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)
            shards, allocation = _get_shard_allocation(es)
            nodes = _get_node_info(es)
    except Exception as e:
        console.print(f"\n[red]Error fetching data: {e}[/red]\n")
        return

    # Node-level allocation summary
    console.print("[bold cyan]Node Allocation Summary[/bold cyan]\n")

    alloc_table = Table(title="Shard Allocation per Node", box=box.ROUNDED)
    alloc_table.add_column("Node", style="cyan")
    alloc_table.add_column("Shards", style="yellow", justify="right")
    alloc_table.add_column("Disk Used", style="red", justify="right")
    alloc_table.add_column("Disk Avail", style="green", justify="right")
    alloc_table.add_column("Disk %", style="magenta", justify="right")

    for a in allocation:
        node_name = a.get("node", "UNASSIGNED")
        if node_name == "UNASSIGNED":
            continue
        alloc_table.add_row(
            node_name,
            str(a.get("shards", 0)),
            bytes_to_human(int(a.get("disk.used", 0) or 0)),
            bytes_to_human(int(a.get("disk.avail", 0) or 0)),
            f"{a.get('disk.percent', 0)}%",
        )

    console.print(alloc_table)

    # Shard distribution balance
    shards_by_node = defaultdict(int)
    for s in shards:
        node = s.get("node")
        if node and node != "null":
            shards_by_node[node] += 1

    balance = _analyze_distribution_balance(dict(shards_by_node))

    console.print()
    if balance["balanced"]:
        console.print(
            f"[green]Shard distribution is balanced "
            f"(CV: {balance['variance']}%, avg: {balance['avg']} shards/node)[/green]"
        )
    else:
        console.print(
            f"[yellow]Shard distribution is UNBALANCED "
            f"(CV: {balance['variance']}%, avg: {balance['avg']} shards/node)[/yellow]"
        )
        console.print(f"[yellow]Recommendation: {balance['recommendation']}[/yellow]")

    # Unassigned shards
    unassigned = [s for s in shards if s.get("state") == "UNASSIGNED"]
    if unassigned:
        console.print(f"\n[red]{len(unassigned)} unassigned shard(s) detected![/red]")
        by_reason = defaultdict(int)
        for s in unassigned:
            by_reason[s.get("unassigned.reason", "UNKNOWN")] += 1
        for reason, count in by_reason.items():
            console.print(f"  {reason}: {count}")

    console.print()


def option_shard_count_recommendations(es):
    """Recommend optimal shard counts for all indices."""
    show_breadcrumb(["Main Menu", "Shard Rebalancing Advisor", "Shard Count Recommendations"])
    console.print()

    target_gb = get_number_input(
        f"Target shard size in GB (default: {TARGET_SHARD_SIZE_IDEAL_GB}): ",
        default=TARGET_SHARD_SIZE_IDEAL_GB,
    )
    if target_gb is None:
        return

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing indices..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)
            indices_info = get_all_indices_info(es)
            shards = es.cat.shards(format="json", bytes="b")
            cluster_health = es.cluster.health()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    # Build shard count per index
    primary_shards_by_index = defaultdict(int)
    replica_shards_by_index = defaultdict(int)
    for s in shards:
        idx = s.get("index", "")
        if s.get("prirep") == "p":
            primary_shards_by_index[idx] += 1
        else:
            replica_shards_by_index[idx] += 1

    recommendations = []
    for idx_name, idx_data in indices_info.items():
        if is_system(idx_name):
            continue

        total_size = idx_data.get("size_bytes", 0)
        current_primary = primary_shards_by_index.get(idx_name, 0)
        current_replica = replica_shards_by_index.get(idx_name, 0)
        current_total = current_primary + current_replica
        optimal_primary = _calculate_optimal_shards(total_size, target_gb)

        if current_primary == 0:
            continue

        avg_shard_size = total_size / current_primary if current_primary > 0 else 0
        avg_shard_gb = avg_shard_size / (1024 * 1024 * 1024)

        if avg_shard_gb < TARGET_SHARD_SIZE_MIN_GB and current_primary > 1:
            status = "Over-sharded"
            action = f"Reduce to {optimal_primary} primary shard(s)"
        elif avg_shard_gb > TARGET_SHARD_SIZE_MAX_GB:
            status = "Under-sharded"
            action = f"Increase to {optimal_primary} primary shard(s)"
        else:
            status = "Optimal"
            action = "No change needed"

        recommendations.append({
            "index": idx_name,
            "size": idx_data.get("size", "0b"),
            "size_bytes": total_size,
            "current_primary": current_primary,
            "current_replica": current_replica,
            "optimal_primary": optimal_primary,
            "avg_shard_gb": round(avg_shard_gb, 2),
            "status": status,
            "action": action,
        })

    # Sort: issues first, then by size
    recommendations.sort(
        key=lambda x: (x["status"] == "Optimal", -x["size_bytes"])
    )

    console.print("[bold cyan]Shard Count Recommendations[/bold cyan]\n")

    table = Table(
        title=f"{len(recommendations)} Indices Analyzed (target: {target_gb}GB/shard)",
        box=box.ROUNDED,
    )
    table.add_column("Index", style="cyan")
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("Primary", style="magenta", justify="right")
    table.add_column("Replica", style="blue", justify="right")
    table.add_column("Avg Shard", style="white", justify="right")
    table.add_column("Optimal", style="green", justify="right")
    table.add_column("Status", style="white")

    for r in recommendations[:50]:
        status_str = {
            "Over-sharded": "[yellow]Over-sharded[/yellow]",
            "Under-sharded": "[red]Under-sharded[/red]",
            "Optimal": "[green]Optimal[/green]",
        }.get(r["status"], r["status"])

        table.add_row(
            r["index"],
            r["size"],
            str(r["current_primary"]),
            str(r["current_replica"]),
            f"{r['avg_shard_gb']:.1f}GB",
            str(r["optimal_primary"]),
            status_str,
        )

    console.print(table)

    # Summary
    issues = [r for r in recommendations if r["status"] != "Optimal"]
    over = [r for r in issues if r["status"] == "Over-sharded"]
    under = [r for r in issues if r["status"] == "Under-sharded"]

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total indices: {len(recommendations)}")
    console.print(f"  Optimal: {len(recommendations) - len(issues)}")
    console.print(f"  Over-sharded: {len(over)}")
    console.print(f"  Under-sharded: {len(under)}")

    if issues:
        console.print(f"\n[yellow]{len(issues)} indices need shard count adjustment.[/yellow]")

    console.print()


def option_shard_rebalance_plan(es):
    """Generate a rebalancing plan with specific actions."""
    show_breadcrumb(["Main Menu", "Shard Rebalancing Advisor", "Rebalance Plan"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Generating rebalance plan..."),
            transient=True,
        ) as progress:
            progress.add_task("plan", total=None)
            shards, allocation = _get_shard_allocation(es)
            nodes = _get_node_info(es)
            cluster_health = es.cluster.health()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    actions = []

    # 1. Check for unassigned shards
    unassigned = [s for s in shards if s.get("state") == "UNASSIGNED"]
    if unassigned:
        actions.append({
            "priority": 1,
            "action": "Retry Failed Allocations",
            "detail": f"{len(unassigned)} unassigned shards need allocation",
            "command": "POST /_cluster/reroute?retry_failed=true",
            "impact": "Restores replica availability",
        })

    # 2. Check disk balance
    disk_usage = {}
    for a in allocation:
        node_name = a.get("node", "")
        if node_name and node_name != "UNASSIGNED":
            pct = float(a.get("disk.percent", 0) or 0)
            disk_usage[node_name] = pct

    if disk_usage:
        max_disk = max(disk_usage.values())
        min_disk = min(disk_usage.values())
        if max_disk - min_disk > 20:
            heavy_node = max(disk_usage, key=disk_usage.get)
            light_node = min(disk_usage, key=disk_usage.get)
            actions.append({
                "priority": 2,
                "action": "Balance Disk Usage",
                "detail": (
                    f"Disk imbalance: {heavy_node} at {max_disk:.0f}% vs "
                    f"{light_node} at {min_disk:.0f}%"
                ),
                "command": (
                    f"PUT /_cluster/settings "
                    f'{{\"transient\": {{\"cluster.routing.allocation.disk.watermark.low\": \"80%\"}}}}'
                ),
                "impact": "Prevents disk exhaustion on hot nodes",
            })

    # 3. Check shard balance
    shards_by_node = defaultdict(int)
    for s in shards:
        node = s.get("node")
        if node and node != "null":
            shards_by_node[node] += 1

    balance = _analyze_distribution_balance(dict(shards_by_node))
    if not balance["balanced"]:
        actions.append({
            "priority": 3,
            "action": "Rebalance Shards",
            "detail": (
                f"Shard distribution variance is {balance['variance']}%. "
                f"{balance['recommendation']}"
            ),
            "command": (
                "PUT /_cluster/settings "
                '{\"transient\": {\"cluster.routing.rebalance.enable\": \"all\"}}'
            ),
            "impact": "Even shard distribution improves query performance",
        })

    # 4. Check shards per node
    for node_name, count in shards_by_node.items():
        if count > MAX_SHARDS_PER_NODE:
            actions.append({
                "priority": 2,
                "action": f"Reduce Shards on {node_name}",
                "detail": (
                    f"Node '{node_name}' has {count} shards "
                    f"(max recommended: {MAX_SHARDS_PER_NODE})"
                ),
                "command": "Consolidate indices or add nodes to the cluster",
                "impact": "Prevents OOM and slow cluster state updates",
            })

    # 5. Check relocating shards
    relocating = [s for s in shards if s.get("state") == "RELOCATING"]
    if relocating:
        actions.append({
            "priority": 4,
            "action": "Monitor Ongoing Relocations",
            "detail": f"{len(relocating)} shard(s) currently relocating",
            "command": "GET /_cat/shards?v&s=state",
            "impact": "Wait for completion before further rebalancing",
        })

    # Display plan
    console.print("[bold cyan]Shard Rebalance Plan[/bold cyan]\n")

    status = cluster_health.get("status", "unknown")
    status_color = {"green": "green", "yellow": "yellow", "red": "red"}.get(status, "white")
    console.print(
        f"Cluster Status: [{status_color}]{status.upper()}[/{status_color}]  |  "
        f"Active Shards: {cluster_health.get('active_shards', 0)}  |  "
        f"Relocating: {cluster_health.get('relocating_shards', 0)}  |  "
        f"Unassigned: {cluster_health.get('unassigned_shards', 0)}\n"
    )

    if not actions:
        console.print("[green]No rebalancing actions needed. Cluster is well-balanced.[/green]\n")
        return

    actions.sort(key=lambda x: x["priority"])

    table = Table(title=f"Rebalance Plan ({len(actions)} actions)", box=box.ROUNDED)
    table.add_column("Priority", style="dim", justify="right")
    table.add_column("Action", style="cyan")
    table.add_column("Detail", style="yellow", max_width=50)
    table.add_column("Impact", style="green", max_width=40)

    for a in actions:
        table.add_row(
            str(a["priority"]),
            a["action"],
            a["detail"],
            a["impact"],
        )

    console.print(table)

    # Offer to execute safe actions
    safe_actions = [a for a in actions if "reroute" in a.get("command", "").lower() or "rebalance" in a.get("command", "").lower()]
    if safe_actions and confirm_action(f"Execute {len(safe_actions)} safe rebalancing action(s)?"):
        for a in safe_actions:
            try:
                if "reroute" in a["command"].lower():
                    if GOD_MODE:
                        es.cluster.reroute(retry_failed=True)
                        console.print(f"  [green]Executed: {a['action']}[/green]")
                    else:
                        console.print(f"  [yellow][dry-run] Would execute: {a['action']}[/yellow]")
                elif "rebalance" in a["command"].lower():
                    if GOD_MODE:
                        es.cluster.put_settings(body={
                            "transient": {"cluster.routing.rebalance.enable": "all"}
                        })
                        console.print(f"  [green]Executed: {a['action']}[/green]")
                    else:
                        console.print(f"  [yellow][dry-run] Would execute: {a['action']}[/yellow]")
            except Exception as e:
                console.print(f"  [red]Failed: {a['action']} - {e}[/red]")

        if not GOD_MODE:
            console.print("\n[yellow]SAFE MODE: Actions above were simulated[/yellow]")

        log_operation("shard_rebalance", f"Executed {len(safe_actions)} rebalance actions")

    console.print()


def option_shard_allocation_strategy(es):
    """Recommend allocation strategies based on node resources."""
    show_breadcrumb(["Main Menu", "Shard Rebalancing Advisor", "Allocation Strategy"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing node resources..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)
            nodes = _get_node_info(es)
            node_stats = es.nodes.stats(metric=["fs", "jvm", "os"])
            shards = es.cat.shards(format="json", bytes="b")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    # Analyze each node
    node_analysis = []
    shards_by_node = defaultdict(int)
    for s in shards:
        node = s.get("node")
        if node and node != "null":
            shards_by_node[node] += 1

    for node_id, node_data in node_stats.get("nodes", {}).items():
        node_name = node_data.get("name", node_id)
        fs = node_data.get("fs", {}).get("total", {})
        jvm = node_data.get("jvm", {}).get("mem", {})
        os_info = node_data.get("os", {})

        total_disk = fs.get("total_in_bytes", 0)
        avail_disk = fs.get("available_in_bytes", 0)
        heap_max = jvm.get("heap_max_in_bytes", 0)
        heap_used_pct = jvm.get("heap_used_percent", 0)
        cpu_pct = os_info.get("cpu", {}).get("percent", 0)
        total_ram = os_info.get("mem", {}).get("total_in_bytes", 0)

        shard_count = shards_by_node.get(node_name, 0)

        # Calculate capacity score (0-100)
        disk_score = max(0, 100 - ((total_disk - avail_disk) / total_disk * 100)) if total_disk > 0 else 0
        heap_score = max(0, 100 - heap_used_pct)
        cpu_score = max(0, 100 - cpu_pct)
        shard_score = max(0, 100 - (shard_count / MAX_SHARDS_PER_NODE * 100))

        capacity_score = (disk_score * 0.4 + heap_score * 0.3 + cpu_score * 0.15 + shard_score * 0.15)

        node_analysis.append({
            "node": node_name,
            "total_disk": bytes_to_human(total_disk),
            "avail_disk": bytes_to_human(avail_disk),
            "disk_pct": round((total_disk - avail_disk) / total_disk * 100, 1) if total_disk > 0 else 0,
            "heap_max": bytes_to_human(heap_max),
            "heap_used_pct": heap_used_pct,
            "cpu_pct": cpu_pct,
            "ram": bytes_to_human(total_ram),
            "shards": shard_count,
            "capacity_score": round(capacity_score, 1),
        })

    node_analysis.sort(key=lambda x: x["capacity_score"], reverse=True)

    # Display
    console.print("[bold cyan]Node Resource Analysis & Allocation Strategy[/bold cyan]\n")

    table = Table(title="Node Capacity", box=box.ROUNDED)
    table.add_column("Node", style="cyan")
    table.add_column("Disk Avail", style="green", justify="right")
    table.add_column("Disk %", style="yellow", justify="right")
    table.add_column("Heap %", style="magenta", justify="right")
    table.add_column("CPU %", style="red", justify="right")
    table.add_column("Shards", style="blue", justify="right")
    table.add_column("Capacity", style="white", justify="right")

    for n in node_analysis:
        cap_color = "green" if n["capacity_score"] > 60 else "yellow" if n["capacity_score"] > 30 else "red"
        table.add_row(
            n["node"],
            n["avail_disk"],
            f"{n['disk_pct']}%",
            f"{n['heap_used_pct']}%",
            f"{n['cpu_pct']}%",
            str(n["shards"]),
            f"[{cap_color}]{n['capacity_score']}%[/{cap_color}]",
        )

    console.print(table)

    # Strategy recommendations
    console.print(f"\n[bold cyan]Allocation Strategy Recommendations:[/bold cyan]\n")

    strategies = []

    # Hot-warm-cold tiering
    if len(node_analysis) >= 3:
        strategies.append(
            "Consider implementing hot-warm-cold data tiering:\n"
            "  - Hot tier: nodes with high CPU/RAM for recent data\n"
            "  - Warm tier: balanced nodes for older, less-queried data\n"
            "  - Cold tier: high-disk/low-CPU nodes for archival data"
        )

    # Awareness attributes
    strategies.append(
        "Enable allocation awareness for fault tolerance:\n"
        "  PUT /_cluster/settings {\"persistent\": {\"cluster.routing.allocation.awareness.attributes\": \"zone\"}}\n"
        "  This distributes replicas across availability zones."
    )

    # Shard-per-node limits
    high_shard_nodes = [n for n in node_analysis if n["shards"] > MAX_SHARDS_PER_NODE * 0.8]
    if high_shard_nodes:
        strategies.append(
            f"Set total_shards_per_node on large indices to prevent overloading:\n"
            f"  PUT /my-index/_settings {{\"index.routing.allocation.total_shards_per_node\": 2}}"
        )

    # Rebalance throttling
    strategies.append(
        "Configure rebalance throttling for large clusters:\n"
        "  PUT /_cluster/settings {\"persistent\": {\n"
        "    \"cluster.routing.allocation.cluster_concurrent_rebalance\": 2,\n"
        "    \"indices.recovery.max_bytes_per_sec\": \"100mb\"\n"
        "  }}"
    )

    for i, s in enumerate(strategies, 1):
        console.print(f"  {i}. {s}\n")

    console.print()
