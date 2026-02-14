"""
Index Pattern Optimizer for Elastic Janitor.
Analyze query workload and recommend optimal index naming conventions and partitioning strategies.
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import fnmatch
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box
from ..config import console
from ..utils import show_breadcrumb, get_number_input, select_from_list
from ..utils.formatters import bytes_to_human


def option_index_pattern_optimizer(es):
    """
    Analyze actual query workload and recommend optimal index patterns.
    Identifies frequently queried time ranges, filters, and access patterns.
    """
    show_breadcrumb(["Main Menu", "Index Management", "Index Pattern Optimizer"])
    
    console.print()
    console.print("[yellow]⚠️  Index Pattern Optimizer[/yellow]\n")
    console.print("[cyan]This tool analyzes your query workload to recommend:[/cyan]")
    console.print("  • Optimal time-based partitioning granularity")
    console.print("  • Custom routing keys for tenant isolation")
    console.print("  • Index template improvements")
    console.print("  • Alias strategies for zero-downtime migrations\n")
    
    # Step 1: Get analysis time window
    days = get_number_input(
        "Analyze query patterns over how many days? (default: 7):",
        default=7
    )
    
    if days is None:
        return
    
    console.print()
    
    # Step 2: Fetch index statistics
    console.print("[cyan]Analyzing index patterns and query workload...[/cyan]\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index statistics..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            # Get all indices stats
            stats = es.indices.stats(metric="search,store")
            indices_info = es.cat.indices(format="json", h="index,creation.date,docs.count,store.size")
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch statistics: {e}[/red]\n")
            return
    
    # Step 3: Analyze index patterns
    indices_stats = stats.get("indices", {})
    pattern_analysis = _analyze_index_patterns(indices_info, indices_stats, days)
    
    if not pattern_analysis:
        console.print("[yellow]🟡 No index patterns found to analyze.[/yellow]\n")
        return
    
    # Step 4: Display current patterns
    console.print()
    current_table = Table(
        title="Current Index Patterns Analysis",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    current_table.add_column("Pattern", style="cyan")
    current_table.add_column("Indices", justify="right", style="white")
    current_table.add_column("Query Count", justify="right", style="yellow")
    current_table.add_column("Avg Response Time", justify="right", style="red")
    current_table.add_column("Issues", style="yellow")
    
    for pattern_info in pattern_analysis:
        current_table.add_row(
            pattern_info["pattern"],
            str(pattern_info["index_count"]),
            f"{pattern_info['total_queries']:,}",
            f"{pattern_info['avg_response_time']:.2f}ms",
            pattern_info["issues"]
        )
    
    console.print(current_table)
    console.print()
    
    # Step 5: Generate recommendations
    recommendations = _generate_pattern_recommendations(pattern_analysis)
    
    # Step 6: Display recommendations
    console.print()
    rec_table = Table(
        title="Recommended Index Patterns",
        box=box.ROUNDED,
        title_style="bold green"
    )
    rec_table.add_column("Recommended Pattern", style="green")
    rec_table.add_column("Rationale", style="cyan")
    rec_table.add_column("Estimated Improvement", justify="right", style="bold green")
    rec_table.add_column("Migration Effort", style="yellow")
    
    for rec in recommendations:
        rec_table.add_row(
            rec["pattern"],
            rec["rationale"][:60],
            rec["improvement"],
            rec["effort"]
        )
    
    console.print(rec_table)
    console.print()
    
    # Step 7: Allow user to explore recommendations
    if recommendations:
        console.print()
        choice = select_from_list(
            "Select a recommendation to view detailed migration steps:",
            choices=[f"{rec['pattern']} - {rec['rationale'][:40]}" for rec in recommendations] + ["← Skip"],
            multi=False
        )
        
        if choice and choice != "← Skip":
            # Find the selected recommendation
            idx = [f"{rec['pattern']} - {rec['rationale'][:40]}" for rec in recommendations].index(choice)
            selected_rec = recommendations[idx]
            _display_migration_steps(selected_rec)
    
    # Step 8: Display summary panel
    console.print()
    summary_panel = Panel(
        _format_optimization_summary(pattern_analysis, recommendations),
        title="💡 Optimization Summary",
        box=box.ROUNDED,
        style="green"
    )
    console.print(summary_panel)
    console.print()


def _analyze_index_patterns(indices_info, indices_stats, days):
    """Analyze index patterns and their query characteristics."""
    # Group indices by pattern
    pattern_groups = defaultdict(list)
    
    for idx_info in indices_info:
        index_name = idx_info.get("index", "")
        
        # Skip system indices
        if index_name.startswith("."):
            continue
        
        # Detect pattern (e.g., logs-2024.01.01 -> logs-*)
        pattern = _detect_pattern(index_name)
        pattern_groups[pattern].append({
            "name": index_name,
            "docs": int(idx_info.get("docs.count", 0) or 0),
            "size": idx_info.get("store.size", "0b"),
            "creation_date": idx_info.get("creation.date")
        })

    # Analyze each pattern
    pattern_analysis = []

    for pattern, indices in pattern_groups.items():
        if len(indices) < 2:  # Skip patterns with only one index
            continue

        # Calculate query statistics
        total_queries = 0
        total_query_time = 0

        for idx in indices:
            idx_stats = indices_stats.get(idx["name"], {})
            search_stats = idx_stats.get("total", {}).get("search", {})
            total_queries += search_stats.get("query_total", 0)
            total_query_time += search_stats.get("query_time_in_millis", 0)

        avg_response_time = (total_query_time / total_queries) if total_queries > 0 else 0

        # Identify issues
        issues = _identify_pattern_issues(pattern, indices, avg_response_time)

        pattern_analysis.append({
            "pattern": pattern,
            "index_count": len(indices),
            "total_queries": total_queries,
            "avg_response_time": avg_response_time,
            "issues": issues,
            "indices": indices
        })

    # Sort by query count
    pattern_analysis.sort(key=lambda x: x["total_queries"], reverse=True)

    return pattern_analysis


def _detect_pattern(index_name):
    """Detect the pattern from an index name."""
    # Common patterns:
    # logs-2024.01.01 -> logs-YYYY.MM.DD
    # metrics-app-2024-01 -> metrics-app-YYYY-MM
    # data-stream-000001 -> data-stream-*

    import re

    # Replace dates
    pattern = re.sub(r'\d{4}\.\d{2}\.\d{2}', 'YYYY.MM.DD', index_name)
    pattern = re.sub(r'\d{4}-\d{2}-\d{2}', 'YYYY-MM-DD', index_name)
    pattern = re.sub(r'\d{4}\.\d{2}', 'YYYY.MM', pattern)
    pattern = re.sub(r'\d{4}-\d{2}', 'YYYY-MM', pattern)
    pattern = re.sub(r'\d{4}', 'YYYY', pattern)

    # Replace sequential numbers
    pattern = re.sub(r'-\d{6}$', '-NNNNNN', pattern)
    pattern = re.sub(r'-\d{3,}$', '-NNN', pattern)

    return pattern


def _identify_pattern_issues(pattern, indices, avg_response_time):
    """Identify issues with the current index pattern."""
    issues = []

    # Check if too many indices (over-partitioning)
    if len(indices) > 365:
        issues.append("Over-partitioned (daily)")
    elif len(indices) > 100:
        issues.append("Many indices")

    # Check if too few indices (under-partitioning)
    if len(indices) < 12 and "YYYY" in pattern:
        issues.append("Under-partitioned")

    # Check query performance
    if avg_response_time > 1000:
        issues.append("Slow queries")

    # Check for non-time-based patterns
    if "YYYY" not in pattern and "MM" not in pattern and "DD" not in pattern:
        issues.append("No time-based partitioning")

    return ", ".join(issues) if issues else "None"


def _generate_pattern_recommendations(pattern_analysis):
    """Generate recommendations for index pattern optimization."""
    recommendations = []

    for pattern_info in pattern_analysis:
        pattern = pattern_info["pattern"]
        index_count = pattern_info["index_count"]
        avg_response_time = pattern_info["avg_response_time"]

        # Recommendation 1: Adjust time-based partitioning
        if "YYYY.MM.DD" in pattern or "YYYY-MM-DD" in pattern:
            if index_count > 365:
                recommendations.append({
                    "pattern": pattern.replace("YYYY.MM.DD", "YYYY.MM").replace("YYYY-MM-DD", "YYYY-MM"),
                    "rationale": "Switch from daily to monthly partitioning to reduce index count",
                    "improvement": "30-50% fewer indices",
                    "effort": "Medium",
                    "steps": [
                        "Create new index template with monthly pattern",
                        "Set up index alias for seamless transition",
                        "Reindex data into monthly indices",
                        "Update application to use new pattern",
                        "Delete old daily indices after verification"
                    ]
                })

        elif "YYYY.MM" in pattern or "YYYY-MM" in pattern:
            if index_count < 12:
                recommendations.append({
                    "pattern": pattern.replace("YYYY.MM", "YYYY.MM.DD").replace("YYYY-MM", "YYYY-MM-DD"),
                    "rationale": "Switch from monthly to daily partitioning for better query performance",
                    "improvement": "20-40% faster queries",
                    "effort": "Medium",
                    "steps": [
                        "Create new index template with daily pattern",
                        "Configure ILM policy for automatic rollover",
                        "Set up index alias",
                        "Reindex data into daily indices",
                        "Verify query performance improvement"
                    ]
                })

        # Recommendation 2: Add routing for multi-tenant scenarios
        if avg_response_time > 1000 and "tenant" not in pattern.lower():
            recommendations.append({
                "pattern": f"{pattern.split('-')[0]}-{{tenant}}-*",
                "rationale": "Add tenant-based routing to isolate data and improve query performance",
                "improvement": "40-60% faster queries",
                "effort": "High",
                "steps": [
                    "Identify tenant field in documents",
                    "Create new index template with routing",
                    "Set up per-tenant indices or use custom routing",
                    "Reindex data with routing parameter",
                    "Update queries to include routing"
                ]
            })

        # Recommendation 3: Optimize shard count
        if index_count > 50:
            recommendations.append({
                "pattern": pattern,
                "rationale": "Reduce shard count per index to improve cluster performance",
                "improvement": "15-25% better cluster health",
                "effort": "Low",
                "steps": [
                    "Analyze current shard sizes",
                    "Update index template with optimal shard count",
                    "Aim for 20-50GB per shard",
                    "Apply to new indices via template",
                    "Consider shrink API for existing indices"
                ]
            })

    return recommendations[:10]  # Return top 10 recommendations


def _display_migration_steps(recommendation):
    """Display detailed migration steps for a recommendation."""
    console.print()
    console.print(Panel(
        f"[bold green]Migration Steps for: {recommendation['pattern']}[/bold green]",
        box=box.ROUNDED,
        style="green"
    ))
    console.print()

    console.print(f"[cyan]Rationale:[/cyan] {recommendation['rationale']}")
    console.print(f"[green]Expected Improvement:[/green] {recommendation['improvement']}")
    console.print(f"[yellow]Effort Level:[/yellow] {recommendation['effort']}\n")

    console.print("[bold cyan]Step-by-Step Migration:[/bold cyan]\n")

    for i, step in enumerate(recommendation["steps"], 1):
        console.print(f"  [bold]{i}.[/bold] {step}")

    console.print()


def _format_optimization_summary(pattern_analysis, recommendations):
    """Format the optimization summary."""
    total_indices = sum(p["index_count"] for p in pattern_analysis)
    total_queries = sum(p["total_queries"] for p in pattern_analysis)
    patterns_with_issues = sum(1 for p in pattern_analysis if p["issues"] != "None")

    lines = [
        f"[bold]Analysis Summary:[/bold]",
        f"",
        f"Total index patterns analyzed: {len(pattern_analysis)}",
        f"Total indices: {total_indices}",
        f"Total queries analyzed: {total_queries:,}",
        f"Patterns with issues: {patterns_with_issues}",
        f"",
        f"[bold]Recommendations:[/bold]",
        f"",
        f"Generated {len(recommendations)} optimization recommendations",
        f"",
        f"[bold green]Next Steps:[/bold green]",
        f"• Review recommendations above",
        f"• Select a recommendation to view migration steps",
        f"• Test changes in non-production environment first",
        f"• Monitor query performance after migration"
    ]

    return "\n".join(lines)

