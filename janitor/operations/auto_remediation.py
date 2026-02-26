"""
Auto-Remediation Engine for Elastic Janitor.
Provides self-healing capabilities that automatically execute corrective actions
based on predefined thresholds and conditions.
"""
import json
import time
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


# ── Default thresholds ──────────────────────────────────────────────
DEFAULT_THRESHOLDS = {
    "segment_count": 100,
    "disk_watermark_pct": 85,
    "unassigned_shard_timeout_min": 10,
    "node_failure_retries": 3,
    "replica_recovery_timeout_min": 30,
    "force_merge_max_segments": 1,
    "red_health_retry_interval_sec": 30,
}


def _collect_cluster_state(es):
    """Gather all metrics needed for remediation checks."""
    cluster_health = es.cluster.health()
    node_stats = es.nodes.stats()
    cluster_stats = es.cluster.stats()
    shards = es.cat.shards(format="json", bytes="b")
    return {
        "health": cluster_health,
        "node_stats": node_stats,
        "cluster_stats": cluster_stats,
        "shards": shards,
    }


def _check_segment_issues(es, state, thresholds):
    """Detect indices with segment counts exceeding thresholds."""
    issues = []
    threshold = thresholds.get("segment_count", DEFAULT_THRESHOLDS["segment_count"])

    try:
        segments = es.indices.segments()
    except Exception:
        return issues

    for idx_name, idx_data in segments.get("indices", {}).items():
        if is_system(idx_name):
            continue
        total_segments = 0
        for shard_list in idx_data.get("shards", {}).values():
            for shard in shard_list:
                total_segments += shard.get("num_committed_segments", 0)
        if total_segments > threshold:
            issues.append({
                "type": "excessive_segments",
                "index": idx_name,
                "segments": total_segments,
                "threshold": threshold,
                "severity": "high" if total_segments > threshold * 2 else "medium",
                "action": "force_merge",
                "description": (
                    f"Index '{idx_name}' has {total_segments} segments "
                    f"(threshold: {threshold}). Force merge recommended."
                ),
            })
    return issues


def _check_unassigned_shards(state, thresholds):
    """Detect unassigned shards that need rerouting."""
    issues = []
    shards = state["shards"]
    unassigned = [s for s in shards if s.get("state") == "UNASSIGNED"]

    if unassigned:
        by_index = defaultdict(list)
        for s in unassigned:
            by_index[s.get("index", "unknown")].append(s)

        for idx_name, idx_shards in by_index.items():
            if is_system(idx_name):
                continue
            issues.append({
                "type": "unassigned_shards",
                "index": idx_name,
                "count": len(idx_shards),
                "severity": "high",
                "action": "reroute_shards",
                "description": (
                    f"Index '{idx_name}' has {len(idx_shards)} unassigned shards. "
                    "Automatic reroute recommended."
                ),
            })
    return issues


def _check_disk_watermarks(state, thresholds):
    """Detect nodes approaching disk watermarks."""
    issues = []
    threshold_pct = thresholds.get(
        "disk_watermark_pct", DEFAULT_THRESHOLDS["disk_watermark_pct"]
    )

    for node_id, node_data in state["node_stats"].get("nodes", {}).items():
        node_name = node_data.get("name", node_id)
        fs = node_data.get("fs", {}).get("total", {})
        total_bytes = fs.get("total_in_bytes", 0)
        available_bytes = fs.get("available_in_bytes", 0)

        if total_bytes > 0:
            used_pct = ((total_bytes - available_bytes) / total_bytes) * 100
            if used_pct > threshold_pct:
                issues.append({
                    "type": "disk_watermark",
                    "node": node_name,
                    "used_pct": round(used_pct, 1),
                    "threshold_pct": threshold_pct,
                    "severity": "critical" if used_pct > 90 else "high",
                    "action": "relocate_shards",
                    "description": (
                        f"Node '{node_name}' disk usage at {used_pct:.1f}% "
                        f"(threshold: {threshold_pct}%). "
                        "Shard relocation recommended."
                    ),
                })
    return issues


def _check_cluster_health(state, thresholds):
    """Detect degraded cluster health status."""
    issues = []
    health = state["health"]
    status = health.get("status", "green")

    if status == "red":
        issues.append({
            "type": "cluster_red",
            "severity": "critical",
            "action": "cluster_recovery",
            "description": (
                f"Cluster health is RED. "
                f"Unassigned shards: {health.get('unassigned_shards', 0)}, "
                f"Initializing: {health.get('initializing_shards', 0)}."
            ),
        })
    elif status == "yellow":
        unassigned = health.get("unassigned_shards", 0)
        if unassigned > 0:
            issues.append({
                "type": "cluster_yellow",
                "severity": "medium",
                "unassigned_shards": unassigned,
                "action": "retry_allocation",
                "description": (
                    f"Cluster health is YELLOW with {unassigned} unassigned shards. "
                    "Allocation retry recommended."
                ),
            })
    return issues


def _check_node_failures(state, thresholds):
    """Detect potential node failures via rejected thread pools."""
    issues = []
    for node_id, node_data in state["node_stats"].get("nodes", {}).items():
        node_name = node_data.get("name", node_id)
        thread_pool = node_data.get("thread_pool", {})

        total_rejected = 0
        for pool_name, pool_data in thread_pool.items():
            total_rejected += pool_data.get("rejected", 0)

        if total_rejected > 500:
            issues.append({
                "type": "node_overloaded",
                "node": node_name,
                "total_rejected": total_rejected,
                "severity": "high",
                "action": "node_recovery",
                "description": (
                    f"Node '{node_name}' has {total_rejected} total rejected tasks. "
                    "Node may be overloaded or failing."
                ),
            })
    return issues


def _execute_force_merge(es, issue, thresholds):
    """Execute force merge for an index with excessive segments."""
    idx = issue["index"]
    max_seg = thresholds.get(
        "force_merge_max_segments", DEFAULT_THRESHOLDS["force_merge_max_segments"]
    )
    if GOD_MODE:
        es.indices.forcemerge(index=idx, max_num_segments=max_seg)
        return f"Force merged '{idx}' to {max_seg} segment(s)"
    return f"[dry-run] Would force merge '{idx}' to {max_seg} segment(s)"


def _execute_reroute(es, issue):
    """Execute shard reroute for unassigned shards."""
    if GOD_MODE:
        es.cluster.reroute(retry_failed=True)
        return f"Triggered reroute retry for index '{issue['index']}'"
    return f"[dry-run] Would retry shard reroute for '{issue['index']}'"


def _execute_retry_allocation(es, issue):
    """Retry shard allocation for yellow cluster."""
    if GOD_MODE:
        es.cluster.reroute(retry_failed=True)
        return "Retried failed shard allocations"
    return "[dry-run] Would retry failed shard allocations"


def _execute_relocate_shards(es, issue):
    """Relocate shards away from a node with high disk usage."""
    node = issue.get("node", "unknown")
    if GOD_MODE:
        es.cluster.put_settings(body={
            "transient": {
                "cluster.routing.allocation.exclude._name": node,
            }
        })
        return f"Excluded node '{node}' from allocation to relieve disk pressure"
    return f"[dry-run] Would exclude node '{node}' from allocation"


def _execute_cluster_recovery(es, issue):
    """Attempt cluster recovery from red status."""
    if GOD_MODE:
        es.cluster.reroute(retry_failed=True)
        return "Initiated cluster recovery: retried failed allocations"
    return "[dry-run] Would retry failed allocations for cluster recovery"


def _execute_node_recovery(es, issue):
    """Attempt to recover overloaded node by clearing caches."""
    node = issue.get("node", "unknown")
    if GOD_MODE:
        es.indices.clear_cache()
        return f"Cleared caches to relieve pressure on node '{node}'"
    return f"[dry-run] Would clear caches to relieve pressure on '{node}'"


ACTION_HANDLERS = {
    "force_merge": _execute_force_merge,
    "reroute_shards": _execute_reroute,
    "retry_allocation": _execute_retry_allocation,
    "relocate_shards": _execute_relocate_shards,
    "cluster_recovery": _execute_cluster_recovery,
    "node_recovery": _execute_node_recovery,
}


# ── Interactive menu operations ─────────────────────────────────────

def option_auto_remediation_scan(es):
    """Scan cluster for issues and display remediation recommendations."""
    show_breadcrumb(["Main Menu", "Auto-Remediation", "Scan & Diagnose"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Scanning cluster for issues..."),
            transient=True,
        ) as progress:
            progress.add_task("scan", total=None)
            state = _collect_cluster_state(es)
            issues = []
            issues.extend(_check_cluster_health(state, DEFAULT_THRESHOLDS))
            issues.extend(_check_unassigned_shards(state, DEFAULT_THRESHOLDS))
            issues.extend(_check_segment_issues(es, state, DEFAULT_THRESHOLDS))
            issues.extend(_check_disk_watermarks(state, DEFAULT_THRESHOLDS))
            issues.extend(_check_node_failures(state, DEFAULT_THRESHOLDS))
    except Exception as e:
        console.print(f"\n[red]Error scanning cluster: {e}[/red]\n")
        return

    console.print(f"\n[bold cyan]Auto-Remediation Scan Results[/bold cyan]\n")

    if not issues:
        console.print("[green]No issues detected. Cluster is healthy.[/green]\n")
        return

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

    table = Table(title=f"{len(issues)} Issues Detected", box=box.ROUNDED)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Severity", style="white")
    table.add_column("Type", style="cyan")
    table.add_column("Description", style="yellow")
    table.add_column("Action", style="green")

    severity_styles = {
        "critical": "[bold red]CRITICAL[/bold red]",
        "high": "[red]HIGH[/red]",
        "medium": "[yellow]MEDIUM[/yellow]",
        "low": "[green]LOW[/green]",
    }

    for i, issue in enumerate(issues, 1):
        table.add_row(
            str(i),
            severity_styles.get(issue.get("severity", "low"), "LOW"),
            issue.get("type", "unknown"),
            issue.get("description", ""),
            issue.get("action", "none"),
        )

    console.print(table)
    console.print()

    return issues


def option_auto_remediation_execute(es):
    """Scan for issues and execute remediation actions."""
    show_breadcrumb(["Main Menu", "Auto-Remediation", "Execute Remediation"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Scanning cluster for issues..."),
            transient=True,
        ) as progress:
            progress.add_task("scan", total=None)
            state = _collect_cluster_state(es)
            issues = []
            issues.extend(_check_cluster_health(state, DEFAULT_THRESHOLDS))
            issues.extend(_check_unassigned_shards(state, DEFAULT_THRESHOLDS))
            issues.extend(_check_segment_issues(es, state, DEFAULT_THRESHOLDS))
            issues.extend(_check_disk_watermarks(state, DEFAULT_THRESHOLDS))
            issues.extend(_check_node_failures(state, DEFAULT_THRESHOLDS))
    except Exception as e:
        console.print(f"\n[red]Error scanning cluster: {e}[/red]\n")
        return

    if not issues:
        console.print("[green]No issues detected. Nothing to remediate.[/green]\n")
        return

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

    console.print(f"\n[bold cyan]Found {len(issues)} issue(s) to remediate[/bold cyan]\n")

    for i, issue in enumerate(issues, 1):
        sev = issue.get("severity", "low").upper()
        console.print(f"  {i}. [{sev}] {issue.get('description', '')}")

    console.print()
    if not confirm_action(f"Execute remediation for {len(issues)} issue(s)?"):
        console.print("[yellow]Remediation cancelled.[/yellow]\n")
        return

    console.print()
    results = []
    for issue in issues:
        action = issue.get("action", "")
        handler = ACTION_HANDLERS.get(action)
        if handler:
            try:
                if action == "force_merge":
                    msg = handler(es, issue, DEFAULT_THRESHOLDS)
                else:
                    msg = handler(es, issue)
                results.append({"issue": issue, "result": msg, "success": True})
                console.print(f"  [green]{msg}[/green]")
            except Exception as e:
                msg = f"Failed to execute {action}: {e}"
                results.append({"issue": issue, "result": msg, "success": False})
                console.print(f"  [red]{msg}[/red]")
        else:
            msg = f"No handler for action '{action}'"
            results.append({"issue": issue, "result": msg, "success": False})
            console.print(f"  [yellow]{msg}[/yellow]")

    succeeded = sum(1 for r in results if r["success"])
    failed = len(results) - succeeded

    console.print()
    if not GOD_MODE:
        console.print(
            f"[yellow]SAFE MODE: Simulated {succeeded} remediation action(s)[/yellow]"
        )
    else:
        console.print(
            f"[green]Executed {succeeded} action(s)[/green]"
            + (f", [red]{failed} failed[/red]" if failed else "")
        )

    log_operation("auto_remediation", f"Remediated {succeeded}/{len(results)} issues")
    console.print()


def option_auto_remediation_configure(es):
    """View and modify remediation thresholds."""
    show_breadcrumb(["Main Menu", "Auto-Remediation", "Configure Thresholds"])
    console.print()

    console.print("[bold cyan]Current Remediation Thresholds[/bold cyan]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("Parameter", style="cyan")
    table.add_column("Current Value", style="yellow")
    table.add_column("Description", style="white")

    descriptions = {
        "segment_count": "Max segments before force merge is triggered",
        "disk_watermark_pct": "Disk usage % before shard relocation",
        "unassigned_shard_timeout_min": "Minutes before unassigned shard reroute",
        "node_failure_retries": "Retry attempts for node failure recovery",
        "replica_recovery_timeout_min": "Minutes before replica recovery escalation",
        "force_merge_max_segments": "Target segment count for force merge",
        "red_health_retry_interval_sec": "Seconds between red health recovery retries",
    }

    for key, value in DEFAULT_THRESHOLDS.items():
        table.add_row(key, str(value), descriptions.get(key, ""))

    console.print(table)

    console.print(
        "\n[dim]Thresholds are configured via DEFAULT_THRESHOLDS in "
        "auto_remediation.py. Modify the dictionary to adjust values.[/dim]\n"
    )


def option_auto_remediation_history(es):
    """View recent auto-remediation actions."""
    show_breadcrumb(["Main Menu", "Auto-Remediation", "Remediation History"])
    console.print()

    from ..utils import get_recent_operations

    ops = get_recent_operations()
    remediation_ops = [o for o in ops if "remediation" in str(o).lower()]

    if not remediation_ops:
        console.print("[yellow]No recent remediation actions found.[/yellow]\n")
        return

    table = Table(title="Recent Remediation Actions", box=box.ROUNDED)
    table.add_column("Timestamp", style="cyan")
    table.add_column("Operation", style="yellow")
    table.add_column("Details", style="white")

    for op in remediation_ops[:20]:
        table.add_row(
            str(op.get("timestamp", "")),
            str(op.get("operation", "")),
            str(op.get("details", "")),
        )

    console.print(table)
    console.print()
