"""
Policy-Based Actions System for Elastic Janitor.
Provides an IFTTT-style rule engine that allows users to define conditional
automation rules for routine Elasticsearch maintenance tasks.
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, GOD_MODE, PROTECT_SYSTEM, DEFAULT_RETENTION_DAYS
from ..utils import (
    safe_input, is_system, confirm_action, show_breadcrumb,
    select_from_list, get_number_input, get_text_input, bytes_to_human,
    log_operation, parse_epoch_millis,
)
from ..core import get_all_indices_info
import questionary


# ── Policy storage ──────────────────────────────────────────────────
POLICY_FILE = os.path.join(os.path.expanduser("~"), ".elastic_janitor_policies.json")


def _load_policies():
    """Load saved policies from disk."""
    if os.path.exists(POLICY_FILE):
        try:
            with open(POLICY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_policies(policies):
    """Save policies to disk."""
    with open(POLICY_FILE, "w") as f:
        json.dump(policies, f, indent=2, default=str)


# ── Built-in condition evaluators ───────────────────────────────────

def _eval_disk_usage(es, params):
    """Evaluate disk usage condition. Returns (bool, context_dict)."""
    threshold_pct = params.get("threshold_pct", 85)
    node_stats = es.nodes.stats(metric=["fs"])
    triggered_nodes = []

    for node_id, node_data in node_stats.get("nodes", {}).items():
        node_name = node_data.get("name", node_id)
        fs = node_data.get("fs", {}).get("total", {})
        total = fs.get("total_in_bytes", 0)
        available = fs.get("available_in_bytes", 0)
        if total > 0:
            used_pct = ((total - available) / total) * 100
            if used_pct > threshold_pct:
                triggered_nodes.append({
                    "node": node_name,
                    "used_pct": round(used_pct, 1),
                })

    return len(triggered_nodes) > 0, {"triggered_nodes": triggered_nodes}


def _eval_cluster_health(es, params):
    """Evaluate cluster health condition."""
    target_status = params.get("status", "red")
    health = es.cluster.health()
    current = health.get("status", "green")
    return current == target_status, {"current_status": current}


def _eval_index_age(es, params):
    """Evaluate whether indices older than N days exist."""
    max_age_days = params.get("max_age_days", 30)
    pattern = params.get("pattern", "*")
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    indices_info = get_all_indices_info(es)
    old_indices = []

    for idx_name, idx_data in indices_info.items():
        if is_system(idx_name):
            continue
        if pattern != "*" and pattern.replace("*", "") not in idx_name:
            continue
        created = idx_data.get("created")
        if created and created < cutoff:
            old_indices.append({
                "index": idx_name,
                "created": str(created),
                "size": idx_data.get("size", "unknown"),
            })

    return len(old_indices) > 0, {"old_indices": old_indices}


def _eval_shard_count(es, params):
    """Evaluate whether total shard count exceeds a threshold."""
    threshold = params.get("threshold", 1000)
    health = es.cluster.health()
    total_shards = health.get("active_shards", 0) + health.get("unassigned_shards", 0)
    return total_shards > threshold, {"total_shards": total_shards}


def _eval_index_count(es, params):
    """Evaluate whether total index count exceeds a threshold."""
    threshold = params.get("threshold", 500)
    stats = es.cat.indices(format="json")
    count = len([i for i in stats if not is_system(i.get("index", ""))])
    return count > threshold, {"index_count": count}


CONDITION_EVALUATORS = {
    "disk_usage_exceeds": _eval_disk_usage,
    "cluster_health_is": _eval_cluster_health,
    "indices_older_than": _eval_index_age,
    "shard_count_exceeds": _eval_shard_count,
    "index_count_exceeds": _eval_index_count,
}


# ── Built-in action executors ───────────────────────────────────────

def _action_delete_old_indices(es, params, context):
    """Delete indices older than N days."""
    old_indices = context.get("old_indices", [])
    deleted = 0
    for idx_info in old_indices:
        idx_name = idx_info["index"]
        if is_system(idx_name):
            continue
        if GOD_MODE:
            try:
                es.indices.delete(index=idx_name)
                deleted += 1
            except Exception as e:
                console.print(f"  [red]Error deleting '{idx_name}': {e}[/red]")
        else:
            deleted += 1
    mode = "" if GOD_MODE else "[dry-run] "
    return f"{mode}Deleted {deleted}/{len(old_indices)} old indices"


def _action_pause_indexing(es, params, context):
    """Pause non-critical indexing by setting indices to read-only."""
    pattern = params.get("pattern", "*")
    if GOD_MODE:
        try:
            es.indices.put_settings(
                index=pattern,
                body={"index.blocks.write": True},
            )
            return f"Set write block on indices matching '{pattern}'"
        except Exception as e:
            return f"Failed to pause indexing: {e}"
    return f"[dry-run] Would set write block on '{pattern}'"


def _action_relocate_shards(es, params, context):
    """Relocate shards from nodes with high disk usage."""
    nodes = context.get("triggered_nodes", [])
    if not nodes:
        return "No nodes to relocate from"
    node_names = [n["node"] for n in nodes]
    if GOD_MODE:
        es.cluster.put_settings(body={
            "transient": {
                "cluster.routing.allocation.exclude._name": ",".join(node_names),
            }
        })
        return f"Excluded {len(node_names)} node(s) from allocation"
    return f"[dry-run] Would exclude {len(node_names)} node(s) from allocation"


def _action_retry_allocation(es, params, context):
    """Retry shard allocation."""
    if GOD_MODE:
        es.cluster.reroute(retry_failed=True)
        return "Retried failed shard allocations"
    return "[dry-run] Would retry failed shard allocations"


def _action_reduce_replicas(es, params, context):
    """Reduce replica count for indices matching a pattern."""
    pattern = params.get("pattern", "*")
    replicas = params.get("replicas", 0)
    if GOD_MODE:
        try:
            es.indices.put_settings(
                index=pattern,
                body={"index.number_of_replicas": replicas},
            )
            return f"Set replicas to {replicas} for '{pattern}'"
        except Exception as e:
            return f"Failed: {e}"
    return f"[dry-run] Would set replicas to {replicas} for '{pattern}'"


ACTION_EXECUTORS = {
    "delete_old_indices": _action_delete_old_indices,
    "pause_indexing": _action_pause_indexing,
    "relocate_shards": _action_relocate_shards,
    "retry_allocation": _action_retry_allocation,
    "reduce_replicas": _action_reduce_replicas,
}


# ── Built-in policy templates ──────────────────────────────────────

POLICY_TEMPLATES = [
    {
        "name": "Disk Cleanup on High Usage",
        "description": "If disk usage exceeds 85%, delete indices older than 30 days",
        "condition": "disk_usage_exceeds",
        "condition_params": {"threshold_pct": 85},
        "action": "delete_old_indices",
        "action_params": {"max_age_days": 30},
        "enabled": True,
    },
    {
        "name": "Pause Indexing on Red Health",
        "description": "If cluster health becomes red, pause non-critical indexing",
        "condition": "cluster_health_is",
        "condition_params": {"status": "red"},
        "action": "pause_indexing",
        "action_params": {"pattern": "*,-.*"},
        "enabled": True,
    },
    {
        "name": "Auto-Relocate on Disk Pressure",
        "description": "If disk usage exceeds 90%, relocate shards off hot nodes",
        "condition": "disk_usage_exceeds",
        "condition_params": {"threshold_pct": 90},
        "action": "relocate_shards",
        "action_params": {},
        "enabled": True,
    },
    {
        "name": "Retry Allocation on Yellow Health",
        "description": "If cluster health is yellow, retry failed shard allocations",
        "condition": "cluster_health_is",
        "condition_params": {"status": "yellow"},
        "action": "retry_allocation",
        "action_params": {},
        "enabled": True,
    },
    {
        "name": "Reduce Replicas on High Index Count",
        "description": "If index count exceeds 500, reduce replicas on old indices",
        "condition": "index_count_exceeds",
        "condition_params": {"threshold": 500},
        "action": "reduce_replicas",
        "action_params": {"pattern": "*", "replicas": 0},
        "enabled": False,
    },
]


# ── Interactive menu operations ─────────────────────────────────────

def option_policy_list(es):
    """List all configured policies."""
    show_breadcrumb(["Main Menu", "Policy-Based Actions", "List Policies"])
    console.print()

    policies = _load_policies()

    if not policies:
        console.print("[yellow]No custom policies configured.[/yellow]")
        console.print("[dim]Use 'Create from Template' to get started.[/dim]\n")
        return

    table = Table(title=f"{len(policies)} Configured Policies", box=box.ROUNDED)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Condition", style="yellow")
    table.add_column("Action", style="green")
    table.add_column("Status", style="white")

    for i, pol in enumerate(policies, 1):
        status = "[green]Enabled[/green]" if pol.get("enabled") else "[red]Disabled[/red]"
        table.add_row(
            str(i),
            pol.get("name", "Unnamed"),
            pol.get("condition", "unknown"),
            pol.get("action", "unknown"),
            status,
        )

    console.print(table)
    console.print()


def option_policy_create(es):
    """Create a new policy from a template or custom definition."""
    show_breadcrumb(["Main Menu", "Policy-Based Actions", "Create Policy"])
    console.print()

    console.print("[bold cyan]Create a New Policy[/bold cyan]\n")
    console.print("Choose a template or create a custom policy:\n")

    template_choices = [
        questionary.Choice(
            f"{t['name']} - {t['description']}",
            value=str(i),
        )
        for i, t in enumerate(POLICY_TEMPLATES)
    ]
    template_choices.append(questionary.Separator())
    template_choices.append(questionary.Choice("Custom Policy", value="custom"))
    template_choices.append(questionary.Choice("Cancel", value="cancel"))

    try:
        choice = questionary.select(
            "Select template:",
            choices=template_choices,
        ).ask()
    except KeyboardInterrupt:
        return

    if choice is None or choice == "cancel":
        return

    if choice == "custom":
        _create_custom_policy()
    else:
        template = POLICY_TEMPLATES[int(choice)]
        _create_from_template(template)


def _create_from_template(template):
    """Create a policy from a built-in template."""
    console.print(f"\n[cyan]Creating policy from template: {template['name']}[/cyan]\n")

    name = get_text_input(
        f"Policy name (default: {template['name']}): ",
        default=template["name"],
    )
    if not name:
        return

    policy = {
        "name": name,
        "description": template["description"],
        "condition": template["condition"],
        "condition_params": dict(template["condition_params"]),
        "action": template["action"],
        "action_params": dict(template["action_params"]),
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Allow customising condition params
    console.print("\n[dim]Condition parameters:[/dim]")
    for key, value in policy["condition_params"].items():
        new_val = get_text_input(f"  {key} (default: {value}): ", default=str(value))
        if new_val and new_val != str(value):
            try:
                policy["condition_params"][key] = type(value)(new_val)
            except (ValueError, TypeError):
                policy["condition_params"][key] = new_val

    # Allow customising action params
    if policy["action_params"]:
        console.print("\n[dim]Action parameters:[/dim]")
        for key, value in policy["action_params"].items():
            new_val = get_text_input(
                f"  {key} (default: {value}): ", default=str(value)
            )
            if new_val and new_val != str(value):
                try:
                    policy["action_params"][key] = type(value)(new_val)
                except (ValueError, TypeError):
                    policy["action_params"][key] = new_val

    policies = _load_policies()
    policies.append(policy)
    _save_policies(policies)

    console.print(f"\n[green]Policy '{name}' created successfully.[/green]\n")


def _create_custom_policy():
    """Create a fully custom policy."""
    console.print("\n[bold cyan]Custom Policy Builder[/bold cyan]\n")

    name = get_text_input("Policy name: ")
    if not name:
        return

    description = get_text_input("Description: ")

    # Select condition
    condition_choices = [
        questionary.Choice(f"{k}", value=k)
        for k in CONDITION_EVALUATORS.keys()
    ]

    try:
        condition = questionary.select(
            "Select condition:",
            choices=condition_choices,
        ).ask()
    except KeyboardInterrupt:
        return

    if not condition:
        return

    # Condition params
    console.print("\n[dim]Enter condition parameters (JSON format):[/dim]")
    params_str = get_text_input("Condition params (e.g. {\"threshold_pct\": 85}): ", default="{}")
    try:
        condition_params = json.loads(params_str) if params_str else {}
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON. Using empty params.[/red]")
        condition_params = {}

    # Select action
    action_choices = [
        questionary.Choice(f"{k}", value=k)
        for k in ACTION_EXECUTORS.keys()
    ]

    try:
        action = questionary.select(
            "Select action:",
            choices=action_choices,
        ).ask()
    except KeyboardInterrupt:
        return

    if not action:
        return

    # Action params
    console.print("\n[dim]Enter action parameters (JSON format):[/dim]")
    action_params_str = get_text_input("Action params (e.g. {\"pattern\": \"*\"}): ", default="{}")
    try:
        action_params = json.loads(action_params_str) if action_params_str else {}
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON. Using empty params.[/red]")
        action_params = {}

    policy = {
        "name": name,
        "description": description or "",
        "condition": condition,
        "condition_params": condition_params,
        "action": action,
        "action_params": action_params,
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    policies = _load_policies()
    policies.append(policy)
    _save_policies(policies)

    console.print(f"\n[green]Custom policy '{name}' created successfully.[/green]\n")


def option_policy_evaluate(es):
    """Evaluate all enabled policies and show which would trigger."""
    show_breadcrumb(["Main Menu", "Policy-Based Actions", "Evaluate Policies"])
    console.print()

    policies = _load_policies()
    enabled = [p for p in policies if p.get("enabled", False)]

    if not enabled:
        console.print("[yellow]No enabled policies to evaluate.[/yellow]\n")
        return

    console.print(f"[cyan]Evaluating {len(enabled)} enabled policies...[/cyan]\n")

    results = []
    for pol in enabled:
        condition = pol.get("condition")
        evaluator = CONDITION_EVALUATORS.get(condition)

        if not evaluator:
            results.append({
                "policy": pol["name"],
                "triggered": False,
                "error": f"Unknown condition: {condition}",
            })
            continue

        try:
            triggered, context = evaluator(es, pol.get("condition_params", {}))
            results.append({
                "policy": pol["name"],
                "condition": condition,
                "action": pol.get("action", ""),
                "triggered": triggered,
                "context": context,
            })
        except Exception as e:
            results.append({
                "policy": pol["name"],
                "triggered": False,
                "error": str(e),
            })

    table = Table(title="Policy Evaluation Results", box=box.ROUNDED)
    table.add_column("Policy", style="cyan")
    table.add_column("Condition", style="yellow")
    table.add_column("Triggered", style="white")
    table.add_column("Action", style="green")

    for r in results:
        triggered_str = (
            "[bold red]YES[/bold red]"
            if r["triggered"]
            else "[green]No[/green]"
        )
        table.add_row(
            r.get("policy", ""),
            r.get("condition", r.get("error", "")),
            triggered_str,
            r.get("action", "") if r["triggered"] else "-",
        )

    console.print(table)

    # Offer to execute triggered policies
    triggered_policies = [r for r in results if r["triggered"]]
    if triggered_policies:
        console.print(
            f"\n[bold yellow]{len(triggered_policies)} policy(ies) triggered![/bold yellow]"
        )
        if confirm_action("Execute triggered policy actions?"):
            _execute_triggered_policies(es, policies, results)
    else:
        console.print("\n[green]No policies triggered. Cluster is compliant.[/green]")

    console.print()


def _execute_triggered_policies(es, policies, results):
    """Execute actions for triggered policies."""
    console.print()
    for r in results:
        if not r.get("triggered"):
            continue
        pol_name = r["policy"]
        pol = next((p for p in policies if p["name"] == pol_name), None)
        if not pol:
            continue

        action = pol.get("action")
        executor = ACTION_EXECUTORS.get(action)
        if not executor:
            console.print(f"  [yellow]No executor for action: {action}[/yellow]")
            continue

        try:
            # Merge condition context into action params for context-aware actions
            combined_params = {**pol.get("action_params", {}), **pol.get("condition_params", {})}
            msg = executor(es, combined_params, r.get("context", {}))
            console.print(f"  [green]{pol_name}: {msg}[/green]")
        except Exception as e:
            console.print(f"  [red]{pol_name}: Failed - {e}[/red]")

    if not GOD_MODE:
        console.print(
            "\n[yellow]SAFE MODE: Actions above were simulated[/yellow]"
        )

    log_operation("policy_actions", "Executed triggered policy actions")


def option_policy_delete(es):
    """Delete saved policies."""
    show_breadcrumb(["Main Menu", "Policy-Based Actions", "Delete Policies"])
    console.print()

    policies = _load_policies()
    if not policies:
        console.print("[yellow]No policies to delete.[/yellow]\n")
        return

    choices = [
        questionary.Choice(f"{p['name']} ({p.get('condition', '')} -> {p.get('action', '')})", value=str(i))
        for i, p in enumerate(policies)
    ]
    choices.append(questionary.Separator())
    choices.append(questionary.Choice("Cancel", value="cancel"))

    try:
        selected = questionary.checkbox(
            "Select policies to delete:",
            choices=choices,
        ).ask()
    except KeyboardInterrupt:
        return

    if not selected or "cancel" in selected:
        return

    indices_to_remove = sorted([int(s) for s in selected if s != "cancel"], reverse=True)
    for idx in indices_to_remove:
        if 0 <= idx < len(policies):
            removed = policies.pop(idx)
            console.print(f"  [red]Removed: {removed['name']}[/red]")

    _save_policies(policies)
    console.print(f"\n[green]Deleted {len(indices_to_remove)} policy(ies).[/green]\n")


def option_policy_toggle(es):
    """Enable or disable existing policies."""
    show_breadcrumb(["Main Menu", "Policy-Based Actions", "Toggle Policies"])
    console.print()

    policies = _load_policies()
    if not policies:
        console.print("[yellow]No policies configured.[/yellow]\n")
        return

    choices = [
        questionary.Choice(
            f"{'[ON]' if p.get('enabled') else '[OFF]'} {p['name']}",
            value=str(i),
        )
        for i, p in enumerate(policies)
    ]
    choices.append(questionary.Separator())
    choices.append(questionary.Choice("Cancel", value="cancel"))

    try:
        selected = questionary.checkbox(
            "Select policies to toggle:",
            choices=choices,
        ).ask()
    except KeyboardInterrupt:
        return

    if not selected or "cancel" in selected:
        return

    for idx_str in selected:
        if idx_str == "cancel":
            continue
        idx = int(idx_str)
        if 0 <= idx < len(policies):
            policies[idx]["enabled"] = not policies[idx].get("enabled", False)
            state = "enabled" if policies[idx]["enabled"] else "disabled"
            console.print(f"  {policies[idx]['name']}: {state}")

    _save_policies(policies)
    console.print(f"\n[green]Updated {len(selected)} policy(ies).[/green]\n")
