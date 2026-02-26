"""
Index Template Optimizer for Elastic Janitor.
Analyzes existing index templates and suggests mapping optimizations including
field type recommendations, _source and _all optimizations, dynamic mapping
improvements, and storage-efficient field configurations.
"""
import json
from collections import defaultdict
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, GOD_MODE, PROTECT_SYSTEM
from ..utils import (
    safe_input, is_system, confirm_action, show_breadcrumb,
    select_from_list, get_number_input, get_text_input, bytes_to_human,
)
import questionary


# ── Optimization rules ──────────────────────────────────────────────

def _analyze_field_type(field_name, field_mapping, parent_path=""):
    """Analyze a single field mapping and return optimization suggestions."""
    suggestions = []
    full_path = f"{parent_path}.{field_name}" if parent_path else field_name
    field_type = field_mapping.get("type", "object")

    # Rule 1: text fields that should be keyword
    if field_type == "text":
        # Common patterns suggesting keyword is better
        keyword_patterns = [
            "id", "uuid", "code", "status", "type", "category", "tag",
            "name", "key", "level", "severity", "action", "method",
            "protocol", "version", "country", "region", "zone",
            "hostname", "ip", "port", "path", "url", "uri", "email",
        ]
        lower_name = field_name.lower()
        if any(p in lower_name for p in keyword_patterns):
            has_keyword_sub = "fields" in field_mapping and "keyword" in field_mapping.get("fields", {})
            if not has_keyword_sub:
                suggestions.append({
                    "field": full_path,
                    "current_type": "text",
                    "suggested_type": "keyword",
                    "reason": (
                        f"Field '{field_name}' appears to be an identifier/categorical value. "
                        "keyword type is more efficient for exact matching, sorting, and aggregations."
                    ),
                    "impact": "Reduced storage, faster aggregations and filtering",
                    "severity": "high",
                })
            else:
                suggestions.append({
                    "field": full_path,
                    "current_type": "text + keyword sub-field",
                    "suggested_type": "keyword (primary)",
                    "reason": (
                        f"Field '{field_name}' has both text and keyword mappings. "
                        "If full-text search is not needed, use keyword as the primary type."
                    ),
                    "impact": "Reduced storage by removing text analyzer overhead",
                    "severity": "low",
                })

    # Rule 2: text fields without a keyword sub-field
    if field_type == "text":
        has_keyword = "fields" in field_mapping and "keyword" in field_mapping.get("fields", {})
        if not has_keyword:
            suggestions.append({
                "field": full_path,
                "current_type": "text",
                "suggested_type": "text + keyword sub-field",
                "reason": (
                    "Text field without keyword sub-field. Adding a keyword sub-field "
                    "enables exact match, sorting, and aggregation without reindexing."
                ),
                "impact": "Enables aggregations and exact-match queries",
                "severity": "medium",
            })

    # Rule 3: numeric strings that should be numeric types
    if field_type == "keyword":
        numeric_patterns = ["count", "total", "amount", "price", "score", "size", "length", "duration", "latency", "rate"]
        if any(p in field_name.lower() for p in numeric_patterns):
            suggestions.append({
                "field": full_path,
                "current_type": "keyword",
                "suggested_type": "long or double",
                "reason": (
                    f"Field '{field_name}' appears numeric but is mapped as keyword. "
                    "Numeric types enable range queries and numeric aggregations."
                ),
                "impact": "Enables range queries, better compression for numeric data",
                "severity": "medium",
            })

    # Rule 4: date fields stored as keyword or text
    if field_type in ("keyword", "text"):
        date_patterns = ["date", "timestamp", "time", "created", "updated", "modified", "expires", "_at", "_on"]
        if any(p in field_name.lower() for p in date_patterns):
            suggestions.append({
                "field": full_path,
                "current_type": field_type,
                "suggested_type": "date",
                "reason": (
                    f"Field '{field_name}' appears to contain dates but is mapped as {field_type}. "
                    "Date type enables date math, range queries, and date histograms."
                ),
                "impact": "Enables time-based queries and date histogram aggregations",
                "severity": "high",
            })

    # Rule 5: boolean fields stored as keyword
    if field_type == "keyword":
        bool_patterns = ["is_", "has_", "enabled", "active", "deleted", "visible", "flag", "bool"]
        if any(p in field_name.lower() for p in bool_patterns):
            suggestions.append({
                "field": full_path,
                "current_type": "keyword",
                "suggested_type": "boolean",
                "reason": (
                    f"Field '{field_name}' appears to be boolean but is mapped as keyword. "
                    "Boolean type is more storage-efficient."
                ),
                "impact": "Reduced storage, clearer semantics",
                "severity": "low",
            })

    # Rule 6: IP address fields
    if field_type in ("keyword", "text"):
        ip_patterns = ["ip", "addr", "address", "source_ip", "dest_ip", "client_ip", "remote_ip"]
        if any(field_name.lower() == p or field_name.lower().endswith(f"_{p}") for p in ip_patterns):
            suggestions.append({
                "field": full_path,
                "current_type": field_type,
                "suggested_type": "ip",
                "reason": (
                    f"Field '{field_name}' appears to contain IP addresses. "
                    "ip type enables CIDR range queries."
                ),
                "impact": "Enables CIDR queries like 10.0.0.0/8",
                "severity": "medium",
            })

    # Rule 7: doc_values disabled unnecessarily
    if field_mapping.get("doc_values") is False and field_type in ("keyword", "long", "double", "date"):
        suggestions.append({
            "field": full_path,
            "current_type": field_type,
            "suggested_type": f"{field_type} (enable doc_values)",
            "reason": (
                "doc_values is disabled. This prevents sorting and aggregations on this field. "
                "Only disable doc_values if you never sort/aggregate on this field."
            ),
            "impact": "Enables sorting and aggregations",
            "severity": "medium",
        })

    # Rule 8: norms enabled on keyword fields
    if field_type == "keyword" and field_mapping.get("norms", False):
        suggestions.append({
            "field": full_path,
            "current_type": "keyword (norms: true)",
            "suggested_type": "keyword (norms: false)",
            "reason": "Norms are enabled on keyword field. Keywords don't use scoring, so norms waste space.",
            "impact": "Reduced memory and storage usage",
            "severity": "low",
        })

    return suggestions


def _analyze_mapping_recursively(properties, parent_path=""):
    """Recursively analyze all fields in a mapping."""
    all_suggestions = []
    for field_name, field_mapping in properties.items():
        suggestions = _analyze_field_type(field_name, field_mapping, parent_path)
        all_suggestions.extend(suggestions)

        # Recurse into nested/object properties
        if "properties" in field_mapping:
            full_path = f"{parent_path}.{field_name}" if parent_path else field_name
            nested = _analyze_mapping_recursively(field_mapping["properties"], full_path)
            all_suggestions.extend(nested)

    return all_suggestions


def _analyze_template_settings(template_body):
    """Analyze template-level settings for optimization opportunities."""
    suggestions = []
    settings = template_body.get("settings", {}).get("index", {}) or template_body.get("settings", {})

    # Check number of shards
    num_shards = int(settings.get("number_of_shards", 1))
    if num_shards > 5:
        suggestions.append({
            "category": "Settings",
            "issue": f"High default shard count ({num_shards})",
            "recommendation": (
                "Start with 1 shard for small indices. Use rollover for time-series data. "
                "Target 20-50GB per shard."
            ),
            "severity": "medium",
        })

    # Check number of replicas
    num_replicas = int(settings.get("number_of_replicas", 1))
    if num_replicas > 2:
        suggestions.append({
            "category": "Settings",
            "issue": f"High replica count ({num_replicas})",
            "recommendation": "1 replica is sufficient for most use cases. More replicas increase storage cost.",
            "severity": "low",
        })

    # Check refresh interval
    refresh_interval = settings.get("refresh_interval", "1s")
    if refresh_interval == "1s":
        suggestions.append({
            "category": "Settings",
            "issue": "Default refresh interval (1s)",
            "recommendation": (
                "For write-heavy indices, increase to 30s or 60s. "
                "For bulk indexing, set to -1 and refresh after completion."
            ),
            "severity": "low",
        })

    return suggestions


def _analyze_dynamic_mapping(template_body):
    """Analyze dynamic mapping configuration."""
    suggestions = []
    mappings = template_body.get("mappings", {})

    # Check if dynamic mapping is enabled
    dynamic = mappings.get("dynamic", True)
    if dynamic is True:
        suggestions.append({
            "category": "Dynamic Mapping",
            "issue": "Dynamic mapping is enabled (default)",
            "recommendation": (
                "Consider setting dynamic: 'strict' or 'false' to prevent "
                "mapping explosions from unexpected fields. Use dynamic_templates "
                "for controlled dynamic behavior."
            ),
            "severity": "medium",
        })

    # Check for dynamic templates
    dynamic_templates = mappings.get("dynamic_templates", [])
    if not dynamic_templates and dynamic is True:
        suggestions.append({
            "category": "Dynamic Mapping",
            "issue": "No dynamic templates configured",
            "recommendation": (
                "Add dynamic_templates to control how unmapped fields are typed. "
                "Example: map all strings to keyword by default instead of text+keyword."
            ),
            "severity": "medium",
        })

    # Check _source configuration
    source_config = mappings.get("_source", {})
    if not source_config:
        suggestions.append({
            "category": "Source",
            "issue": "_source is fully enabled (default)",
            "recommendation": (
                "For large documents, consider _source filtering with 'includes'/'excludes' "
                "to reduce storage. Only disable _source if you never need to reindex."
            ),
            "severity": "low",
        })

    return suggestions


# ── Interactive menu operations ─────────────────────────────────────

def option_template_mapping_analyzer(es):
    """Analyze index template mappings and suggest field type optimizations."""
    show_breadcrumb(["Main Menu", "Index Template Optimizer", "Mapping Analyzer"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching index templates..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            templates = es.indices.get_index_template()
    except Exception as e:
        console.print(f"\n[red]Error fetching templates: {e}[/red]\n")
        return

    template_list = templates.get("index_templates", [])
    if not template_list:
        console.print("[yellow]No index templates found.[/yellow]\n")
        return

    # Let user select a template
    choices = [
        questionary.Choice(t["name"], value=str(i))
        for i, t in enumerate(template_list)
        if not t["name"].startswith(".")
    ]
    if not choices:
        console.print("[yellow]No user-defined templates found.[/yellow]\n")
        return

    choices.append(questionary.Separator())
    choices.append(questionary.Choice("Analyze ALL templates", value="all"))
    choices.append(questionary.Choice("Cancel", value="cancel"))

    try:
        selection = questionary.select(
            "Select template to analyze:",
            choices=choices,
        ).ask()
    except KeyboardInterrupt:
        return

    if selection is None or selection == "cancel":
        return

    if selection == "all":
        templates_to_analyze = [
            t for t in template_list if not t["name"].startswith(".")
        ]
    else:
        templates_to_analyze = [template_list[int(selection)]]

    total_suggestions = []

    for tmpl in templates_to_analyze:
        tmpl_name = tmpl["name"]
        tmpl_body = tmpl.get("index_template", {}).get("template", {})
        mappings = tmpl_body.get("mappings", {})
        properties = mappings.get("properties", {})

        console.print(f"\n[bold cyan]Analyzing: {tmpl_name}[/bold cyan]")
        console.print(f"  Fields: {len(properties)}")

        if properties:
            field_suggestions = _analyze_mapping_recursively(properties)
            for s in field_suggestions:
                s["template"] = tmpl_name
            total_suggestions.extend(field_suggestions)

            if field_suggestions:
                console.print(f"  [yellow]{len(field_suggestions)} optimization(s) found[/yellow]")
            else:
                console.print("  [green]No field optimizations needed[/green]")
        else:
            console.print("  [dim]No explicit mappings defined[/dim]")

    if total_suggestions:
        console.print(f"\n[bold cyan]Field Optimization Suggestions[/bold cyan]\n")

        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        total_suggestions.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 2))

        table = Table(title=f"{len(total_suggestions)} Suggestions", box=box.ROUNDED)
        table.add_column("Template", style="cyan")
        table.add_column("Field", style="yellow")
        table.add_column("Current", style="red")
        table.add_column("Suggested", style="green")
        table.add_column("Severity", style="white")
        table.add_column("Impact", style="white", max_width=35)

        severity_styles = {
            "high": "[red]HIGH[/red]",
            "medium": "[yellow]MEDIUM[/yellow]",
            "low": "[green]LOW[/green]",
        }

        for s in total_suggestions[:50]:
            table.add_row(
                s.get("template", ""),
                s["field"],
                s["current_type"],
                s["suggested_type"],
                severity_styles.get(s["severity"], "LOW"),
                s["impact"],
            )

        console.print(table)
    else:
        console.print("\n[green]No field optimizations needed across templates.[/green]")

    console.print()


def option_template_settings_analyzer(es):
    """Analyze template-level settings for optimization opportunities."""
    show_breadcrumb(["Main Menu", "Index Template Optimizer", "Settings Analyzer"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching templates..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            templates = es.indices.get_index_template()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    template_list = templates.get("index_templates", [])
    user_templates = [t for t in template_list if not t["name"].startswith(".")]

    if not user_templates:
        console.print("[yellow]No user-defined templates found.[/yellow]\n")
        return

    all_suggestions = []

    for tmpl in user_templates:
        tmpl_name = tmpl["name"]
        tmpl_body = tmpl.get("index_template", {}).get("template", {})

        settings_suggestions = _analyze_template_settings(tmpl_body)
        dynamic_suggestions = _analyze_dynamic_mapping(tmpl_body)

        for s in settings_suggestions + dynamic_suggestions:
            s["template"] = tmpl_name

        all_suggestions.extend(settings_suggestions)
        all_suggestions.extend(dynamic_suggestions)

    console.print("[bold cyan]Template Settings & Configuration Analysis[/bold cyan]\n")

    if not all_suggestions:
        console.print("[green]All template settings look good.[/green]\n")
        return

    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_suggestions.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 2))

    table = Table(title=f"{len(all_suggestions)} Settings Suggestions", box=box.ROUNDED)
    table.add_column("Template", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Issue", style="red")
    table.add_column("Severity", style="white")
    table.add_column("Recommendation", style="green", max_width=50)

    severity_styles = {
        "high": "[red]HIGH[/red]",
        "medium": "[yellow]MEDIUM[/yellow]",
        "low": "[green]LOW[/green]",
    }

    for s in all_suggestions:
        table.add_row(
            s.get("template", ""),
            s["category"],
            s["issue"],
            severity_styles.get(s["severity"], "LOW"),
            s["recommendation"],
        )

    console.print(table)
    console.print()


def option_template_live_index_analysis(es):
    """Analyze live index mappings (not just templates) for optimization."""
    show_breadcrumb(["Main Menu", "Index Template Optimizer", "Live Index Analysis"])
    console.print()

    pattern = get_text_input("Enter index pattern to analyze (default: *): ", default="*")
    if pattern is None:
        return

    max_indices = get_number_input("Max indices to analyze (default: 10): ", default=10)
    if max_indices is None:
        return

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing live index mappings..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)
            mappings = es.indices.get_mapping(index=pattern)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    indices = {k: v for k, v in mappings.items() if not is_system(k)}
    if not indices:
        console.print("[yellow]No matching indices found.[/yellow]\n")
        return

    # Limit to first N
    index_names = list(indices.keys())[:max_indices]
    total_suggestions = []

    for idx_name in index_names:
        idx_mapping = indices[idx_name]
        properties = idx_mapping.get("mappings", {}).get("properties", {})

        if properties:
            suggestions = _analyze_mapping_recursively(properties)
            for s in suggestions:
                s["index"] = idx_name
            total_suggestions.extend(suggestions)

    console.print(f"[bold cyan]Live Index Mapping Analysis[/bold cyan]")
    console.print(f"Analyzed {len(index_names)} index(es)\n")

    if not total_suggestions:
        console.print("[green]No mapping optimizations found.[/green]\n")
        return

    severity_order = {"high": 0, "medium": 1, "low": 2}
    total_suggestions.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 2))

    table = Table(title=f"{len(total_suggestions)} Mapping Suggestions", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Field", style="yellow")
    table.add_column("Current", style="red")
    table.add_column("Suggested", style="green")
    table.add_column("Severity", style="white")
    table.add_column("Reason", style="white", max_width=40)

    severity_styles = {
        "high": "[red]HIGH[/red]",
        "medium": "[yellow]MEDIUM[/yellow]",
        "low": "[green]LOW[/green]",
    }

    for s in total_suggestions[:50]:
        table.add_row(
            s.get("index", ""),
            s["field"],
            s["current_type"],
            s["suggested_type"],
            severity_styles.get(s["severity"], "LOW"),
            s["reason"][:80],
        )

    console.print(table)

    # Summary
    high = sum(1 for s in total_suggestions if s["severity"] == "high")
    medium = sum(1 for s in total_suggestions if s["severity"] == "medium")
    low = sum(1 for s in total_suggestions if s["severity"] == "low")
    console.print(f"\n[bold]Summary:[/bold] {high} high, {medium} medium, {low} low severity suggestions")
    console.print()


def option_template_optimization_report(es):
    """Generate a comprehensive optimization report across all templates."""
    show_breadcrumb(["Main Menu", "Index Template Optimizer", "Optimization Report"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Generating optimization report..."),
            transient=True,
        ) as progress:
            progress.add_task("report", total=None)
            templates = es.indices.get_index_template()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    template_list = templates.get("index_templates", [])
    user_templates = [t for t in template_list if not t["name"].startswith(".")]

    if not user_templates:
        console.print("[yellow]No user-defined templates found.[/yellow]\n")
        return

    console.print("[bold cyan]Comprehensive Template Optimization Report[/bold cyan]\n")

    overall_field_count = 0
    overall_suggestions = 0
    overall_settings_issues = 0

    for tmpl in user_templates:
        tmpl_name = tmpl["name"]
        tmpl_body = tmpl.get("index_template", {}).get("template", {})
        mappings = tmpl_body.get("mappings", {})
        properties = mappings.get("properties", {})
        index_patterns = tmpl.get("index_template", {}).get("index_patterns", [])

        field_count = len(properties)
        overall_field_count += field_count

        field_suggestions = _analyze_mapping_recursively(properties) if properties else []
        settings_suggestions = _analyze_template_settings(tmpl_body)
        dynamic_suggestions = _analyze_dynamic_mapping(tmpl_body)

        total_issues = len(field_suggestions) + len(settings_suggestions) + len(dynamic_suggestions)
        overall_suggestions += len(field_suggestions)
        overall_settings_issues += len(settings_suggestions) + len(dynamic_suggestions)

        # Per-template summary
        health = "[green]Healthy[/green]" if total_issues == 0 else f"[yellow]{total_issues} issue(s)[/yellow]"
        patterns_str = ", ".join(index_patterns) if index_patterns else "N/A"
        console.print(
            f"  [cyan]{tmpl_name}[/cyan] | "
            f"Patterns: {patterns_str} | "
            f"Fields: {field_count} | "
            f"Status: {health}"
        )

        if field_suggestions:
            high = sum(1 for s in field_suggestions if s["severity"] == "high")
            med = sum(1 for s in field_suggestions if s["severity"] == "medium")
            low = sum(1 for s in field_suggestions if s["severity"] == "low")
            console.print(f"    Field issues: {high} high, {med} medium, {low} low")

        if settings_suggestions:
            console.print(f"    Settings issues: {len(settings_suggestions)}")

        if dynamic_suggestions:
            console.print(f"    Dynamic mapping issues: {len(dynamic_suggestions)}")

    # Overall summary
    console.print(f"\n[bold]Overall Summary:[/bold]")
    console.print(f"  Templates analyzed: {len(user_templates)}")
    console.print(f"  Total fields: {overall_field_count}")
    console.print(f"  Field optimization suggestions: {overall_suggestions}")
    console.print(f"  Settings/config suggestions: {overall_settings_issues}")

    total = overall_suggestions + overall_settings_issues
    if total == 0:
        console.print("\n[green]All templates are well-optimized![/green]")
    else:
        console.print(f"\n[yellow]{total} total optimization(s) available.[/yellow]")
        console.print("[dim]Run 'Mapping Analyzer' or 'Settings Analyzer' for detailed suggestions.[/dim]")

    console.print()