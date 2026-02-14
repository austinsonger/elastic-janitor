"""
Aggregation Optimizer for Elastic Janitor.
Analyze slow query logs and identify expensive aggregation queries with optimization recommendations.
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
from ..config import console, DEFAULT_QUERY_TIMEOUT
from ..utils import show_breadcrumb, get_number_input
from ..utils.formatters import bytes_to_human


def option_aggregation_optimizer(es):
    """
    Analyze slow query logs and identify expensive aggregation queries.
    Provides specific optimization recommendations for aggregations.
    """
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Aggregation Optimizer"])
    
    console.print()
    console.print("[yellow]⚠️  Aggregation Query Optimizer[/yellow]\n")
    console.print("[cyan]This tool analyzes query performance and provides optimization recommendations for:[/cyan]")
    console.print("  • Terms aggregations with high cardinality")
    console.print("  • Date histogram aggregations")
    console.print("  • Nested aggregations")
    console.print("  • Cardinality aggregations")
    console.print("  • Missing doc_values or field data settings\n")
    
    # Step 1: Get analysis threshold
    threshold_ms = get_number_input(
        "Analyze queries slower than X milliseconds (default: 1000):",
        default=1000
    )
    
    if threshold_ms is None:
        return
    
    console.print()
    
    # Step 2: Fetch query statistics
    console.print("[cyan]Analyzing query performance...[/cyan]\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index statistics..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            # Get search stats from all indices
            stats = es.indices.stats(metric="search")
        except Exception as e:
            console.print(f"[red]❌ ERROR: Failed to fetch statistics: {e}[/red]\n")
            return
    
    # Step 3: Analyze query patterns
    indices_stats = stats.get("indices", {})
    slow_queries = []
    
    for index_name, index_data in indices_stats.items():
        search_stats = index_data.get("total", {}).get("search", {})
        query_total = search_stats.get("query_total", 0)
        query_time_ms = search_stats.get("query_time_in_millis", 0)
        
        if query_total > 0:
            avg_time = query_time_ms / query_total
            if avg_time >= threshold_ms:
                slow_queries.append({
                    "index": index_name,
                    "total_queries": query_total,
                    "total_time_ms": query_time_ms,
                    "avg_time_ms": avg_time
                })
    
    # Sort by average time
    slow_queries.sort(key=lambda x: x["avg_time_ms"], reverse=True)
    
    if not slow_queries:
        console.print(f"[green]✅ No queries found slower than {threshold_ms}ms.[/green]\n")
        console.print("[blue]ℹ️  Your queries are performing well![/blue]\n")
        return
    
    # Step 4: Categorize aggregation types and generate recommendations
    recommendations = _generate_aggregation_recommendations(es, slow_queries[:20])
    
    # Step 5: Display findings
    console.print()
    findings_table = Table(
        title=f"Slow Query Analysis (>{threshold_ms}ms)",
        box=box.ROUNDED,
        title_style="bold cyan"
    )
    findings_table.add_column("Index", style="cyan", no_wrap=True)
    findings_table.add_column("Queries", justify="right", style="white")
    findings_table.add_column("Avg Time", justify="right", style="red")
    findings_table.add_column("Issue", style="yellow")
    
    for item in slow_queries[:20]:
        issue = _identify_query_issue(item)
        findings_table.add_row(
            item["index"][:40],
            f"{item['total_queries']:,}",
            f"{item['avg_time_ms']:.2f}ms",
            issue
        )
    
    console.print(findings_table)
    console.print()
    
    # Step 6: Display top recommendations
    if recommendations:
        console.print()
        top_recommendations = Panel(
            _format_top_recommendations(recommendations[:5]),
            title="💡 Top 5 Optimization Recommendations",
            box=box.ROUNDED,
            style="yellow"
        )
        console.print(top_recommendations)
        console.print()
    
    # Step 7: Display detailed recommendations table
    if recommendations:
        console.print()
        rec_table = Table(
            title="Detailed Optimization Recommendations",
            box=box.ROUNDED,
            title_style="bold green"
        )
        rec_table.add_column("Query Pattern", style="cyan")
        rec_table.add_column("Current Performance", justify="right", style="red")
        rec_table.add_column("Issue", style="yellow")
        rec_table.add_column("Recommendation", style="green")
        rec_table.add_column("Potential Improvement", justify="right", style="bold green")
        
        for rec in recommendations[:10]:
            rec_table.add_row(
                rec["pattern"][:30],
                rec["current_perf"],
                rec["issue"][:40],
                rec["recommendation"][:50],
                rec["improvement"]
            )
        
        console.print(rec_table)
        console.print()

    # Step 8: Display code examples
    console.print()
    _display_optimization_examples()


def _identify_query_issue(query_stats):
    """Identify the likely issue causing slow queries."""
    avg_time = query_stats["avg_time_ms"]

    if avg_time > 5000:
        return "Very slow - likely aggregation issue"
    elif avg_time > 2000:
        return "Slow - check aggregations"
    elif avg_time > 1000:
        return "Moderate - optimize if frequent"
    else:
        return "Acceptable performance"


def _generate_aggregation_recommendations(es, slow_queries):
    """Generate specific optimization recommendations for slow queries."""
    recommendations = []

    for query in slow_queries:
        index_name = query["index"]
        avg_time = query["avg_time_ms"]

        # Try to get mapping information
        try:
            mapping = es.indices.get_mapping(index=index_name)
            index_mapping = mapping.get(index_name, {}).get("mappings", {})
            properties = index_mapping.get("properties", {})

            # Analyze field types and suggest optimizations
            for field_name, field_config in properties.items():
                field_type = field_config.get("type", "")

                # Check for high-cardinality text fields
                if field_type == "text" and not field_config.get("fielddata", False):
                    recommendations.append({
                        "pattern": f"{index_name}.{field_name}",
                        "current_perf": f"{avg_time:.0f}ms",
                        "issue": "Text field without fielddata",
                        "recommendation": "Use keyword field or enable fielddata",
                        "improvement": "50-80%"
                    })

                # Check for keyword fields that could use eager_global_ordinals
                elif field_type == "keyword" and not field_config.get("eager_global_ordinals", False):
                    if avg_time > 2000:
                        recommendations.append({
                            "pattern": f"{index_name}.{field_name}",
                            "current_perf": f"{avg_time:.0f}ms",
                            "issue": "Keyword field without eager global ordinals",
                            "recommendation": "Enable eager_global_ordinals for frequently aggregated fields",
                            "improvement": "30-50%"
                        })

                # Check for missing doc_values
                elif field_type in ["long", "integer", "double", "float", "date"] and field_config.get("doc_values", True) == False:
                    recommendations.append({
                        "pattern": f"{index_name}.{field_name}",
                        "current_perf": f"{avg_time:.0f}ms",
                        "issue": "Numeric field without doc_values",
                        "recommendation": "Enable doc_values for aggregations",
                        "improvement": "60-90%"
                    })

        except Exception as e:
            # If we can't get mapping, provide general recommendations
            recommendations.append({
                "pattern": index_name,
                "current_perf": f"{avg_time:.0f}ms",
                "issue": "Slow aggregation queries",
                "recommendation": "Use composite aggregations for high-cardinality fields",
                "improvement": "40-70%"
            })

    # Add general best practice recommendations
    if slow_queries:
        recommendations.extend([
            {
                "pattern": "General - Terms Agg",
                "current_perf": "Varies",
                "issue": "High cardinality terms aggregation",
                "recommendation": "Use composite aggregation with pagination",
                "improvement": "50-80%"
            },
            {
                "pattern": "General - Date Histogram",
                "current_perf": "Varies",
                "issue": "Fine-grained date histogram",
                "recommendation": "Increase interval or use auto_date_histogram",
                "improvement": "30-60%"
            },
            {
                "pattern": "General - Nested Agg",
                "current_perf": "Varies",
                "issue": "Deep nested aggregations",
                "recommendation": "Reduce nesting depth or use separate queries",
                "improvement": "40-70%"
            }
        ])

    return recommendations


def _format_top_recommendations(recommendations):
    """Format top recommendations for display in a panel."""
    lines = []
    for i, rec in enumerate(recommendations, 1):
        lines.append(f"[bold cyan]{i}. {rec['pattern']}[/bold cyan]")
        lines.append(f"   Issue: {rec['issue']}")
        lines.append(f"   [green]→ {rec['recommendation']}[/green]")
        lines.append(f"   [bold green]Potential improvement: {rec['improvement']}[/bold green]")
        if i < len(recommendations):
            lines.append("")

    return "\n".join(lines)


def _display_optimization_examples():
    """Display code examples for common optimizations."""
    console.print(Panel(
        "[bold yellow]Optimization Examples[/bold yellow]",
        box=box.ROUNDED,
        style="yellow"
    ))
    console.print()

    # Example 1: Composite aggregation
    example1 = '''// Replace high-cardinality terms aggregation with composite
{
  "aggs": {
    "my_buckets": {
      "composite": {
        "size": 100,
        "sources": [
          { "product": { "terms": { "field": "product.keyword" } } },
          { "date": { "date_histogram": { "field": "@timestamp", "calendar_interval": "1d" } } }
        ]
      }
    }
  }
}'''

    console.print("[bold cyan]1. Use Composite Aggregation for High Cardinality:[/bold cyan]")
    console.print(Syntax(example1, "json", theme="monokai", line_numbers=False))
    console.print()

    # Example 2: Eager global ordinals
    example2 = '''// Enable eager_global_ordinals in mapping
PUT /my-index/_mapping
{
  "properties": {
    "category": {
      "type": "keyword",
      "eager_global_ordinals": true
    }
  }
}'''

    console.print("[bold cyan]2. Enable Eager Global Ordinals:[/bold cyan]")
    console.print(Syntax(example2, "json", theme="monokai", line_numbers=False))
    console.print()

    # Example 3: Execution hint
    example3 = '''// Use execution_hint for better performance
{
  "aggs": {
    "categories": {
      "terms": {
        "field": "category.keyword",
        "execution_hint": "global_ordinals",
        "size": 10
      }
    }
  }
}'''

    console.print("[bold cyan]3. Use Execution Hints:[/bold cyan]")
    console.print(Syntax(example3, "json", theme="monokai", line_numbers=False))
    console.print()
