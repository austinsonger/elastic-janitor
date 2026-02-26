"""
Query Performance Analyzer for Elastic Janitor.
Identifies slow-performing queries, suggests specific optimizations based on
query patterns and cluster metrics, and detects common performance anti-patterns.
"""
import re
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console, GOD_MODE, PROTECT_SYSTEM, SLOW_QUERY_TIMEOUT
from ..utils import (
    safe_input, is_system, confirm_action, show_breadcrumb,
    select_from_list, get_number_input, get_text_input, bytes_to_human,
)
from ..core import get_all_indices_info
import questionary


# ── Anti-pattern definitions ────────────────────────────────────────

ANTI_PATTERNS = {
    "wildcard_leading": {
        "name": "Leading Wildcard Query",
        "description": "Queries starting with '*' or '?' force full index scan",
        "pattern": r'"wildcard"\s*:\s*\{[^}]*"[^"]*"\s*:\s*"[\*\?]',
        "severity": "high",
        "recommendation": (
            "Replace leading wildcard with ngram tokenizer or reverse token filter. "
            "Expected improvement: 10-100x faster search."
        ),
    },
    "deep_pagination": {
        "name": "Deep Pagination (from + size)",
        "description": "Using large 'from' values causes excessive memory usage",
        "severity": "high",
        "recommendation": (
            "Use search_after or scroll API for deep pagination. "
            "Expected improvement: constant memory usage regardless of page depth."
        ),
    },
    "script_scoring": {
        "name": "Script-Based Scoring",
        "description": "Scripts in scoring context are executed per-document",
        "pattern": r'"script_score"',
        "severity": "medium",
        "recommendation": (
            "Pre-compute scores at index time into a numeric field and use "
            "function_score with field_value_factor. "
            "Expected improvement: 2-5x faster scoring."
        ),
    },
    "nested_aggregation": {
        "name": "Deeply Nested Aggregations",
        "description": "Multiple levels of sub-aggregations cause combinatorial explosion",
        "severity": "medium",
        "recommendation": (
            "Flatten aggregation hierarchy or use composite aggregation for "
            "paginated results. Expected improvement: 3-10x less memory usage."
        ),
    },
    "fetch_all_fields": {
        "name": "Fetching All Fields (_source: true without filter)",
        "description": "Returning entire _source for large documents wastes bandwidth",
        "severity": "low",
        "recommendation": (
            "Use _source filtering or stored fields to return only needed fields. "
            "Expected improvement: 2-5x faster response serialization."
        ),
    },
    "match_all_with_size": {
        "name": "match_all with Large Size",
        "description": "Fetching many documents with match_all is inefficient",
        "pattern": r'"match_all"\s*:\s*\{\}',
        "severity": "medium",
        "recommendation": (
            "Use scroll or search_after for bulk retrieval. "
            "Add filters to reduce result set. "
            "Expected improvement: predictable memory usage."
        ),
    },
    "terms_large_list": {
        "name": "Large Terms List",
        "description": "Terms queries with hundreds of values are slow",
        "pattern": r'"terms"\s*:',
        "severity": "medium",
        "recommendation": (
            "Use terms lookup to a dedicated terms index, or restructure "
            "data to avoid large IN-clause style queries. "
            "Expected improvement: 5-20x faster for large lists."
        ),
    },
}


def _analyze_slow_log_entries(es):
    """Fetch slow log data from cluster stats."""
    entries = []
    try:
        node_stats = es.nodes.stats(metric=["indices"])
        for node_id, node_data in node_stats.get("nodes", {}).items():
            node_name = node_data.get("name", node_id)
            search_stats = node_data.get("indices", {}).get("search", {})

            query_total = search_stats.get("query_total", 0)
            query_time_ms = search_stats.get("query_time_in_millis", 0)
            fetch_total = search_stats.get("fetch_total", 0)
            fetch_time_ms = search_stats.get("fetch_time_in_millis", 0)

            avg_query_ms = query_time_ms / query_total if query_total > 0 else 0
            avg_fetch_ms = fetch_time_ms / fetch_total if fetch_total > 0 else 0

            entries.append({
                "node": node_name,
                "query_total": query_total,
                "query_time_ms": query_time_ms,
                "avg_query_ms": round(avg_query_ms, 2),
                "fetch_total": fetch_total,
                "fetch_time_ms": fetch_time_ms,
                "avg_fetch_ms": round(avg_fetch_ms, 2),
            })
    except Exception:
        pass
    return entries


def _analyze_index_search_stats(es, pattern="*"):
    """Analyze per-index search performance."""
    stats_list = []
    try:
        stats = es.indices.stats(index=pattern, metric=["search", "indexing"])
        for idx_name, idx_stats in stats.get("indices", {}).items():
            if is_system(idx_name):
                continue
            search = idx_stats.get("total", {}).get("search", {})
            query_total = search.get("query_total", 0)
            query_time_ms = search.get("query_time_in_millis", 0)
            fetch_total = search.get("fetch_total", 0)
            fetch_time_ms = search.get("fetch_time_in_millis", 0)
            scroll_total = search.get("scroll_total", 0)
            scroll_time_ms = search.get("scroll_time_in_millis", 0)

            avg_query_ms = query_time_ms / query_total if query_total > 0 else 0

            stats_list.append({
                "index": idx_name,
                "query_total": query_total,
                "query_time_ms": query_time_ms,
                "avg_query_ms": round(avg_query_ms, 2),
                "fetch_total": fetch_total,
                "fetch_time_ms": fetch_time_ms,
                "scroll_total": scroll_total,
                "scroll_time_ms": scroll_time_ms,
            })
    except Exception:
        pass
    return stats_list


def _detect_n_plus_one(es, pattern="*"):
    """
    Detect potential N+1 query patterns by analysing search-after-search
    rates across indices. A high ratio of fetch-to-query or very high query
    counts on related indices suggests N+1 behaviour.
    """
    findings = []
    try:
        stats = es.indices.stats(index=pattern, metric=["search"])
        idx_stats = {}
        for idx_name, data in stats.get("indices", {}).items():
            if is_system(idx_name):
                continue
            search = data.get("total", {}).get("search", {})
            idx_stats[idx_name] = {
                "query_total": search.get("query_total", 0),
                "fetch_total": search.get("fetch_total", 0),
            }

        # Detect: if fetch_total >> query_total, possible N+1
        for idx_name, s in idx_stats.items():
            if s["query_total"] > 100 and s["fetch_total"] > s["query_total"] * 5:
                findings.append({
                    "index": idx_name,
                    "query_total": s["query_total"],
                    "fetch_total": s["fetch_total"],
                    "ratio": round(s["fetch_total"] / max(s["query_total"], 1), 1),
                    "description": (
                        f"Index '{idx_name}' has a fetch/query ratio of "
                        f"{s['fetch_total']}/{s['query_total']}. "
                        "This may indicate N+1 query patterns."
                    ),
                    "recommendation": (
                        "Use multi-get (_mget) or multi-search (_msearch) to batch "
                        "related lookups. Consider denormalizing data to avoid "
                        "cross-index joins."
                    ),
                })
    except Exception:
        pass
    return findings


def _detect_heavy_aggregations(es, pattern="*"):
    """Detect indices with heavy aggregation usage."""
    findings = []
    try:
        node_stats = es.nodes.stats(metric=["indices"])
        for node_id, node_data in node_stats.get("nodes", {}).items():
            node_name = node_data.get("name", node_id)
            search = node_data.get("indices", {}).get("search", {})
            query_total = search.get("query_total", 0)
            query_time = search.get("query_time_in_millis", 0)

            if query_total > 0:
                avg_ms = query_time / query_total
                if avg_ms > 500:  # Avg query > 500ms
                    findings.append({
                        "node": node_name,
                        "avg_query_ms": round(avg_ms, 2),
                        "query_total": query_total,
                        "description": (
                            f"Node '{node_name}' has avg query time of "
                            f"{avg_ms:.0f}ms across {query_total} queries."
                        ),
                        "recommendation": (
                            "Review slow query log. Consider pre-aggregating data "
                            "with transforms or reducing aggregation complexity."
                        ),
                    })
    except Exception:
        pass
    return findings


# ── Interactive menu operations ─────────────────────────────────────

def option_query_performance_overview(es):
    """Display a comprehensive overview of query performance across the cluster."""
    show_breadcrumb(["Main Menu", "Query Performance Analyzer", "Performance Overview"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing query performance..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)
            node_entries = _analyze_slow_log_entries(es)
    except Exception as e:
        console.print(f"\n[red]Error analyzing performance: {e}[/red]\n")
        return

    console.print("[bold cyan]Query Performance Overview[/bold cyan]\n")

    if not node_entries:
        console.print("[yellow]No search statistics available.[/yellow]\n")
        return

    table = Table(title="Per-Node Search Performance", box=box.ROUNDED)
    table.add_column("Node", style="cyan")
    table.add_column("Total Queries", style="yellow", justify="right")
    table.add_column("Total Query Time", style="red", justify="right")
    table.add_column("Avg Query (ms)", style="magenta", justify="right")
    table.add_column("Total Fetches", style="blue", justify="right")
    table.add_column("Avg Fetch (ms)", style="white", justify="right")

    for entry in node_entries:
        query_time_str = f"{entry['query_time_ms'] / 1000:.1f}s"
        table.add_row(
            entry["node"],
            f"{entry['query_total']:,}",
            query_time_str,
            f"{entry['avg_query_ms']:.1f}",
            f"{entry['fetch_total']:,}",
            f"{entry['avg_fetch_ms']:.1f}",
        )

    console.print(table)

    # Highlight slow nodes
    slow_nodes = [e for e in node_entries if e["avg_query_ms"] > 100]
    if slow_nodes:
        console.print(f"\n[bold yellow]Slow Nodes ({len(slow_nodes)}):[/bold yellow]")
        for sn in slow_nodes:
            console.print(
                f"  [yellow]{sn['node']}[/yellow]: avg {sn['avg_query_ms']:.1f}ms/query"
            )

    console.print()


def option_query_slow_index_analysis(es):
    """Identify the slowest indices by search performance."""
    show_breadcrumb(["Main Menu", "Query Performance Analyzer", "Slow Index Analysis"])
    console.print()

    pattern = get_text_input("Enter index pattern (default: *): ", default="*")
    if pattern is None:
        return

    top_n = get_number_input("Show top N slowest indices (default: 20): ", default=20)
    if top_n is None:
        return

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing index search performance..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)
            index_stats = _analyze_index_search_stats(es, pattern)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    if not index_stats:
        console.print("[yellow]No search statistics available.[/yellow]\n")
        return

    # Sort by avg query time
    index_stats.sort(key=lambda x: x["avg_query_ms"], reverse=True)
    index_stats = index_stats[:top_n]

    console.print("[bold cyan]Slowest Indices by Search Performance[/bold cyan]\n")

    table = Table(title=f"Top {len(index_stats)} Slowest Indices", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Avg Query (ms)", style="red", justify="right")
    table.add_column("Total Queries", style="yellow", justify="right")
    table.add_column("Total Time (s)", style="magenta", justify="right")
    table.add_column("Total Fetches", style="blue", justify="right")
    table.add_column("Scrolls", style="white", justify="right")

    for s in index_stats:
        table.add_row(
            s["index"],
            f"{s['avg_query_ms']:.1f}",
            f"{s['query_total']:,}",
            f"{s['query_time_ms'] / 1000:.1f}",
            f"{s['fetch_total']:,}",
            f"{s['scroll_total']:,}",
        )

    console.print(table)

    # Show optimization suggestions for slow indices
    very_slow = [s for s in index_stats if s["avg_query_ms"] > 200]
    if very_slow:
        console.print(f"\n[bold yellow]Optimization Suggestions:[/bold yellow]")
        for s in very_slow[:5]:
            console.print(f"\n  [cyan]{s['index']}[/cyan] (avg: {s['avg_query_ms']:.0f}ms):")
            console.print("    - Check mapping for unanalyzed text fields used in filters")
            console.print("    - Consider adding keyword sub-fields for exact match queries")
            console.print("    - Review shard count (over-sharding increases latency)")
            if s["scroll_total"] > s["query_total"] * 0.5:
                console.print("    - High scroll usage detected; consider search_after instead")

    console.print()


def option_query_anti_pattern_detector(es):
    """Detect common query anti-patterns in cluster usage."""
    show_breadcrumb(["Main Menu", "Query Performance Analyzer", "Anti-Pattern Detector"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Scanning for query anti-patterns..."),
            transient=True,
        ) as progress:
            progress.add_task("scan", total=None)

            findings = []

            # N+1 detection
            n_plus_one = _detect_n_plus_one(es)
            for f in n_plus_one:
                findings.append({
                    "pattern": "N+1 Query Pattern",
                    "severity": "high",
                    "location": f["index"],
                    "detail": f["description"],
                    "recommendation": f["recommendation"],
                })

            # Heavy aggregation detection
            heavy_aggs = _detect_heavy_aggregations(es)
            for f in heavy_aggs:
                findings.append({
                    "pattern": "Heavy Aggregations",
                    "severity": "medium",
                    "location": f["node"],
                    "detail": f["description"],
                    "recommendation": f["recommendation"],
                })

            # Deep pagination detection (from search stats)
            node_stats = es.nodes.stats(metric=["indices"])
            for node_id, node_data in node_stats.get("nodes", {}).items():
                node_name = node_data.get("name", node_id)
                search = node_data.get("indices", {}).get("search", {})
                scroll_total = search.get("scroll_total", 0)
                open_contexts = search.get("open_contexts", 0)

                if open_contexts > 50:
                    findings.append({
                        "pattern": "Excessive Open Scroll Contexts",
                        "severity": "high",
                        "location": node_name,
                        "detail": (
                            f"Node '{node_name}' has {open_contexts} open scroll "
                            "contexts. This consumes significant heap memory."
                        ),
                        "recommendation": (
                            "Close unused scroll contexts. Switch to search_after "
                            "for pagination. Set scroll timeout to minimum needed."
                        ),
                    })
    except Exception as e:
        console.print(f"\n[red]Error scanning: {e}[/red]\n")
        return

    console.print("[bold cyan]Query Anti-Pattern Analysis[/bold cyan]\n")

    if not findings:
        console.print("[green]No anti-patterns detected. Query patterns look healthy.[/green]\n")
        return

    table = Table(title=f"{len(findings)} Anti-Patterns Detected", box=box.ROUNDED)
    table.add_column("Pattern", style="cyan")
    table.add_column("Severity", style="white")
    table.add_column("Location", style="yellow")
    table.add_column("Detail", style="white", max_width=50)

    severity_styles = {
        "high": "[red]HIGH[/red]",
        "medium": "[yellow]MEDIUM[/yellow]",
        "low": "[green]LOW[/green]",
    }

    for f in findings:
        table.add_row(
            f["pattern"],
            severity_styles.get(f["severity"], "LOW"),
            f["location"],
            f["detail"],
        )

    console.print(table)

    # Show recommendations
    console.print(f"\n[bold cyan]Recommendations:[/bold cyan]\n")
    for f in findings:
        console.print(f"  [cyan]{f['pattern']}[/cyan] ({f['location']}):")
        console.print(f"    {f['recommendation']}")
        console.print()


def option_query_optimization_suggestions(es):
    """Provide targeted optimization suggestions based on cluster search metrics."""
    show_breadcrumb(["Main Menu", "Query Performance Analyzer", "Optimization Suggestions"])
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Generating optimization suggestions..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            cluster_stats = es.cluster.stats()
            node_stats = es.nodes.stats(metric=["indices", "jvm"])
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        return

    suggestions = []

    # Analyze search performance
    total_queries = 0
    total_query_time = 0
    total_fetches = 0
    total_fetch_time = 0
    total_scroll_contexts = 0

    for node_id, node_data in node_stats.get("nodes", {}).items():
        search = node_data.get("indices", {}).get("search", {})
        total_queries += search.get("query_total", 0)
        total_query_time += search.get("query_time_in_millis", 0)
        total_fetches += search.get("fetch_total", 0)
        total_fetch_time += search.get("fetch_time_in_millis", 0)
        total_scroll_contexts += search.get("open_contexts", 0)

    avg_query_ms = total_query_time / total_queries if total_queries > 0 else 0
    avg_fetch_ms = total_fetch_time / total_fetches if total_fetches > 0 else 0

    # Query cache analysis
    query_cache_total = 0
    query_cache_hits = 0
    query_cache_misses = 0
    for node_id, node_data in node_stats.get("nodes", {}).items():
        qc = node_data.get("indices", {}).get("query_cache", {})
        query_cache_hits += qc.get("hit_count", 0)
        query_cache_misses += qc.get("miss_count", 0)
        query_cache_total = query_cache_hits + query_cache_misses

    cache_hit_rate = (
        (query_cache_hits / query_cache_total * 100) if query_cache_total > 0 else 0
    )

    # Generate suggestions
    if avg_query_ms > 200:
        suggestions.append({
            "category": "Query Latency",
            "finding": f"Average query latency is {avg_query_ms:.0f}ms (ideal: <50ms)",
            "impact": "High",
            "steps": [
                "Enable slow query log: PUT /_settings {\"index.search.slowlog.threshold.query.warn\": \"200ms\"}",
                "Review query patterns for wildcards, scripts, and deep aggregations",
                "Consider adding keyword fields for exact-match filters",
                "Ensure indices have appropriate shard counts (target 20-50GB/shard)",
            ],
            "expected_improvement": "50-80% reduction in avg query latency",
        })

    if avg_fetch_ms > 100:
        suggestions.append({
            "category": "Fetch Latency",
            "finding": f"Average fetch latency is {avg_fetch_ms:.0f}ms (ideal: <20ms)",
            "impact": "Medium",
            "steps": [
                "Use _source filtering to return only needed fields",
                "Reduce fetch size (default 10 is usually sufficient)",
                "Consider using stored fields for frequently accessed data",
                "Enable doc_values for sort/aggregation fields",
            ],
            "expected_improvement": "30-60% reduction in fetch latency",
        })

    if cache_hit_rate < 50 and query_cache_total > 1000:
        suggestions.append({
            "category": "Query Cache",
            "finding": f"Query cache hit rate is {cache_hit_rate:.1f}% (ideal: >70%)",
            "impact": "Medium",
            "steps": [
                "Use filter context instead of query context for non-scoring filters",
                "Increase query cache size if evictions are high",
                "Ensure queries use deterministic parameters (avoid now/random)",
                "Review timestamp-based queries for cache-friendliness",
            ],
            "expected_improvement": "20-50% reduction in repeated query latency",
        })

    if total_scroll_contexts > 100:
        suggestions.append({
            "category": "Scroll Contexts",
            "finding": f"{total_scroll_contexts} open scroll contexts (ideal: <50)",
            "impact": "High",
            "steps": [
                "Migrate from scroll to search_after for pagination",
                "Reduce scroll keepalive time to minimum needed",
                "Ensure application code closes scroll contexts after use",
                "Monitor with GET /_nodes/stats/indices/search",
            ],
            "expected_improvement": "Significant reduction in heap memory usage",
        })

    # Shard count check
    total_shards = cluster_stats.get("indices", {}).get("shards", {}).get("total", 0)
    node_count = cluster_stats.get("nodes", {}).get("count", {}).get("total", 1)
    shards_per_node = total_shards / node_count if node_count > 0 else 0

    if shards_per_node > 600:
        suggestions.append({
            "category": "Shard Count",
            "finding": f"{shards_per_node:.0f} shards/node (recommended: <600)",
            "impact": "High",
            "steps": [
                "Consolidate small indices using rollover and ILM",
                "Increase shard size target to 20-50GB",
                "Delete old, unused indices",
                "Use data streams with appropriate rollover conditions",
            ],
            "expected_improvement": "Reduced cluster overhead and faster searches",
        })

    # Display
    console.print("[bold cyan]Query Optimization Suggestions[/bold cyan]\n")

    if not suggestions:
        console.print("[green]Cluster query performance looks good. No critical suggestions.[/green]\n")
        return

    for s in suggestions:
        impact_color = {"High": "red", "Medium": "yellow", "Low": "green"}.get(s["impact"], "white")
        console.print(Panel(
            f"[{impact_color}]Impact: {s['impact']}[/{impact_color}]\n\n"
            f"[yellow]Finding:[/yellow] {s['finding']}\n\n"
            f"[green]Expected Improvement:[/green] {s['expected_improvement']}\n\n"
            "[cyan]Steps:[/cyan]\n" + "\n".join(f"  {i+1}. {step}" for i, step in enumerate(s["steps"])),
            title=f"[bold]{s['category']}[/bold]",
            box=box.ROUNDED,
        ))
        console.print()


def option_query_known_patterns(es):
    """Display known anti-pattern reference guide."""
    show_breadcrumb(["Main Menu", "Query Performance Analyzer", "Known Anti-Patterns"])
    console.print()

    console.print("[bold cyan]Known Query Anti-Pattern Reference[/bold cyan]\n")

    table = Table(title="Query Anti-Pattern Guide", box=box.ROUNDED)
    table.add_column("Anti-Pattern", style="cyan")
    table.add_column("Severity", style="white")
    table.add_column("Description", style="yellow", max_width=40)
    table.add_column("Recommendation", style="green", max_width=50)

    severity_styles = {
        "high": "[red]HIGH[/red]",
        "medium": "[yellow]MEDIUM[/yellow]",
        "low": "[green]LOW[/green]",
    }

    for key, ap in ANTI_PATTERNS.items():
        table.add_row(
            ap["name"],
            severity_styles.get(ap["severity"], "LOW"),
            ap["description"],
            ap["recommendation"],
        )

    console.print(table)
    console.print()
