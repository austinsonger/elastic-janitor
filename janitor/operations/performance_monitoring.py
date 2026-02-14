"""
Performance & Monitoring operations for Elastic Janitor.
Analyze query performance, indexing rates, search latency, and resource usage.
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import time
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich import box
from rich.text import Text
from ..config import console
from ..utils import show_breadcrumb, safe_input, get_number_input
from ..utils.formatters import bytes_to_human


def option_slow_query_analyzer(es):
    """Fetch and parse Elasticsearch slow query logs."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Slow Query Analyzer"])
    
    console.print("\n[cyan]Analyzing slow queries...[/cyan]\n")
    
    try:
        # Get index slow log settings
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching slow query data..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            # Get index stats which includes search stats
            stats = es.indices.stats(metric="search")
        
        # Parse search stats
        indices_stats = stats.get("indices", {})
        
        slow_queries = []
        for index_name, index_data in indices_stats.items():
            search_stats = index_data.get("total", {}).get("search", {})
            query_total = search_stats.get("query_total", 0)
            query_time_ms = search_stats.get("query_time_in_millis", 0)
            
            if query_total > 0:
                avg_time = query_time_ms / query_total
                slow_queries.append({
                    "index": index_name,
                    "total_queries": query_total,
                    "total_time_ms": query_time_ms,
                    "avg_time_ms": avg_time
                })
        
        # Sort by average time
        slow_queries.sort(key=lambda x: x["avg_time_ms"], reverse=True)
        
        if not slow_queries:
            console.print("[yellow]🟡 No query statistics available.[/yellow]\n")
            return
        
        # Display top 20 slowest
        table = Table(title="Slowest Queries by Index", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Index", style="cyan")
        table.add_column("Total Queries", justify="right", style="white")
        table.add_column("Total Time", justify="right", style="yellow")
        table.add_column("Avg Time (ms)", justify="right", style="red")
        
        for item in slow_queries[:20]:
            table.add_row(
                item["index"],
                f"{item['total_queries']:,}",
                f"{item['total_time_ms']:,} ms",
                f"{item['avg_time_ms']:.2f}"
            )
        
        console.print(table)
        console.print()
        
        # Recommendations
        recommendations = Panel(
            "[bold yellow]Recommendations:[/bold yellow]\n\n"
            "• Consider adding filters to reduce query scope\n"
            "• Review and optimize field mappings\n"
            "• Use query profiling API for detailed analysis\n"
            "• Consider using index patterns to limit search scope\n"
            "• Enable query caching for frequently used queries",
            title="💡 Optimization Tips",
            box=box.ROUNDED,
            style="yellow"
        )
        console.print(recommendations)
        console.print()
        
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch slow query data: {e}[/red]\n")


def _display_indexing_recommendations(bottleneck_data, node_info, indexing_data, nodes):
    """
    Generate and display detailed, actionable recommendations for indexing bottlenecks.

    Args:
        bottleneck_data: List of dicts with bottleneck information per node/pool
        node_info: Dict of node resource information (CPU, heap, etc.)
        indexing_data: List of dicts with indexing performance per index
        nodes: Raw nodes data from Elasticsearch
    """
    console.print("[bold cyan]📊 Detailed Bottleneck Analysis & Recommendations[/bold cyan]\n")

    # Categorize bottlenecks by severity
    critical_nodes = []  # >100k rejections
    important_nodes = []  # >1k rejections
    warning_nodes = []  # >0 rejections or queued

    cluster_wide_issue = len(bottleneck_data) >= len(nodes) * 0.5
    high_throughput_indices = [idx for idx in indexing_data if idx["docs_per_sec"] > 15000]

    for bottleneck in bottleneck_data:
        if bottleneck["rejected"] > 100000:
            critical_nodes.append(bottleneck)
        elif bottleneck["rejected"] > 1000:
            important_nodes.append(bottleneck)
        else:
            warning_nodes.append(bottleneck)

    # Build recommendations content
    recommendations = []

    # === CRITICAL ACTIONS ===
    if critical_nodes:
        recommendations.append("[bold red]🚨 CRITICAL ACTIONS (Immediate)[/bold red]\n")
        for node in critical_nodes:
            node_name = node["node"]
            pool_name = node["pool"]
            rejected = node["rejected"]
            rejection_rate = node["rejection_rate"]

            recommendations.append(
                f"[red]• Node '{node_name}' ({pool_name} pool): {rejected:,} rejections ({rejection_rate:.2f}% rejection rate)[/red]\n"
            )

            # Specific thread pool settings
            current_threads = node.get("threads", 0)
            current_queue_size = node.get("queue_size", 0)

            # Calculate recommended values based on node resources
            node_resources = node_info.get(node_name, {})
            heap_gb = node_resources.get("heap_max", 0) / (1024**3)

            # Recommend thread pool size (typically 1-2x CPU cores, estimate based on heap)
            recommended_threads = max(current_threads + 4, int(heap_gb * 2))
            recommended_queue = max(current_queue_size * 2, 1000)

            recommendations.append(
                f"  [yellow]→ Increase {pool_name} thread pool size:[/yellow]\n"
                f"    PUT /_cluster/settings\n"
                f"    {{\n"
                f"      \"persistent\": {{\n"
                f"        \"thread_pool.{pool_name}.size\": {recommended_threads},\n"
                f"        \"thread_pool.{pool_name}.queue_size\": {recommended_queue}\n"
                f"      }}\n"
                f"    }}\n"
            )

            # Check if node is resource constrained
            cpu = node_resources.get("cpu_percent", 0)
            heap_pct = node_resources.get("heap_percent", 0)

            if cpu > 80 or heap_pct > 85:
                recommendations.append(
                    f"  [red]⚠️  Node is resource-constrained (CPU: {cpu}%, Heap: {heap_pct:.1f}%)[/red]\n"
                    f"  [yellow]→ Thread pool adjustments alone may not help. Consider:[/yellow]\n"
                    f"    • Scale horizontally: Add more data nodes to the cluster\n"
                    f"    • Scale vertically: Increase node CPU/memory resources\n"
                )

        recommendations.append("")

    # === IMPORTANT ACTIONS ===
    if important_nodes:
        recommendations.append("[bold yellow]⚠️  IMPORTANT ACTIONS (Short-term)[/bold yellow]\n")
        for node in important_nodes:
            node_name = node["node"]
            pool_name = node["pool"]
            rejected = node["rejected"]
            rejection_rate = node["rejection_rate"]

            recommendations.append(
                f"[yellow]• Node '{node_name}' ({pool_name} pool): {rejected:,} rejections ({rejection_rate:.2f}% rejection rate)[/yellow]\n"
            )

            current_queue_size = node.get("queue_size", 0)
            recommended_queue = max(current_queue_size + 500, 500)

            recommendations.append(
                f"  [yellow]→ Increase queue size to handle bursts:[/yellow]\n"
                f"    PUT /_cluster/settings\n"
                f"    {{\n"
                f"      \"persistent\": {{\n"
                f"        \"thread_pool.{pool_name}.queue_size\": {recommended_queue}\n"
                f"      }}\n"
                f"    }}\n"
            )

        recommendations.append("")

    # === ROOT CAUSE ANALYSIS ===
    recommendations.append("[bold cyan]🔍 ROOT CAUSE ANALYSIS[/bold cyan]\n")

    if cluster_wide_issue:
        recommendations.append(
            "[red]• Issue Type: CLUSTER-WIDE bottleneck[/red]\n"
            f"  {len(bottleneck_data)} out of {len(nodes)} nodes are experiencing rejections.\n"
            "  This indicates the entire cluster is under-provisioned for the current indexing load.\n"
        )
    else:
        recommendations.append(
            "[yellow]• Issue Type: NODE-SPECIFIC bottleneck[/yellow]\n"
            f"  {len(bottleneck_data)} out of {len(nodes)} nodes are experiencing rejections.\n"
            "  This may indicate uneven shard distribution or hot spots.\n"
        )

    if high_throughput_indices:
        recommendations.append(
            f"\n[yellow]• High-Throughput Indices Detected:[/yellow]\n"
        )
        for idx in high_throughput_indices[:5]:
            recommendations.append(
                f"  - {idx['index']}: {idx['docs_per_sec']:.0f} docs/sec\n"
            )
        recommendations.append(
            "  These indices may be overwhelming specific nodes.\n"
        )

    recommendations.append("")

    # === BULK INDEXING OPTIMIZATION ===
    recommendations.append("[bold cyan]📦 BULK INDEXING OPTIMIZATION[/bold cyan]\n")
    recommendations.append(
        "[yellow]Optimize bulk request parameters:[/yellow]\n"
        "• Reduce bulk request size (try 5-15 MB per request)\n"
        "• Adjust number of concurrent bulk requests\n"
        "• Use the _bulk API with optimal batch sizes\n"
        "\n"
        "[yellow]Example bulk optimization:[/yellow]\n"
        "  # Reduce batch size in your indexing client\n"
        "  bulk_size = 1000  # documents per batch\n"
        "  \n"
        "  # Add retry logic for rejected requests\n"
        "  helpers.bulk(es, actions, chunk_size=bulk_size, \n"
        "               max_retries=3, initial_backoff=2)\n"
    )

    recommendations.append("")

    # === INDEX-LEVEL SETTINGS ===
    recommendations.append("[bold cyan]⚙️  INDEX-LEVEL SETTINGS[/bold cyan]\n")
    recommendations.append(
        "[yellow]Temporarily disable refresh during bulk indexing:[/yellow]\n"
        "  PUT /your-index/_settings\n"
        "  {\n"
        "    \"index\": {\n"
        "      \"refresh_interval\": \"-1\",\n"
        "      \"number_of_replicas\": 0\n"
        "    }\n"
        "  }\n"
        "  \n"
        "  # After bulk indexing completes, restore settings:\n"
        "  PUT /your-index/_settings\n"
        "  {\n"
        "    \"index\": {\n"
        "      \"refresh_interval\": \"30s\",\n"
        "      \"number_of_replicas\": 1\n"
        "    }\n"
        "  }\n"
        "  POST /your-index/_refresh\n"
    )

    recommendations.append("")

    # === MONITORING & VERIFICATION ===
    recommendations.append("[bold cyan]📈 MONITORING & VERIFICATION[/bold cyan]\n")
    recommendations.append(
        "[yellow]After making changes, monitor with these commands:[/yellow]\n"
        "\n"
        "1. Check thread pool stats:\n"
        "   GET /_nodes/stats/thread_pool\n"
        "\n"
        "2. Monitor rejection rates:\n"
        "   GET /_cat/thread_pool/write,bulk?v&h=node_name,name,active,queue,rejected,completed\n"
        "\n"
        "3. Watch cluster health:\n"
        "   GET /_cluster/health\n"
        "\n"
        "4. Track indexing performance:\n"
        "   GET /_stats/indexing\n"
    )

    recommendations.append("")

    # === PREVENTIVE ACTIONS ===
    if warning_nodes or important_nodes or critical_nodes:
        recommendations.append("[bold cyan]🛡️  PREVENTIVE ACTIONS (Long-term)[/bold cyan]\n")

        if cluster_wide_issue:
            recommendations.append(
                "[yellow]• Cluster Scaling:[/yellow]\n"
                "  - Add more data nodes to distribute indexing load\n"
                "  - Target: 3-5 nodes minimum for production workloads\n"
                "  - Consider dedicated master nodes for cluster stability\n"
            )

        recommendations.append(
            "\n[yellow]• Implement Index Lifecycle Management (ILM):[/yellow]\n"
            "  - Use time-based indices (e.g., logs-2024.01.15)\n"
            "  - Configure rollover policies to manage index size\n"
            "  - Archive old data to warm/cold nodes\n"
            "\n"
            "[yellow]• Optimize Shard Strategy:[/yellow]\n"
            "  - Target shard size: 10-50 GB\n"
            "  - Avoid over-sharding (too many small shards)\n"
            "  - Use _shrink API to consolidate small shards\n"
            "\n"
            "[yellow]• Review Mapping & Analysis:[/yellow]\n"
            "  - Disable unnecessary fields (_all, _source if not needed)\n"
            "  - Use appropriate field types (keyword vs text)\n"
            "  - Limit dynamic mapping where possible\n"
        )

    # Display recommendations in a panel
    recommendations_text = "".join(recommendations)

    panel = Panel(
        recommendations_text,
        title="💡 Actionable Recommendations",
        box=box.DOUBLE_EDGE,
        border_style="cyan",
        padding=(1, 2)
    )

    console.print(panel)
    console.print()


def option_indexing_performance_monitor(es):
    """Display current indexing rates and identify bottlenecks."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Indexing Performance Monitor"])

    console.print("\n[cyan]Monitoring indexing performance...[/cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indexing metrics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            stats = es.indices.stats(metric="indexing")
            nodes_stats = es.nodes.stats(metric=["thread_pool", "os", "jvm"])

        # Parse indexing stats per index
        indices_stats = stats.get("indices", {})
        indexing_data = []

        for index_name, index_data in indices_stats.items():
            indexing_stats = index_data.get("total", {}).get("indexing", {})
            index_total = indexing_stats.get("index_total", 0)
            index_time_ms = indexing_stats.get("index_time_in_millis", 0)

            if index_total > 0:
                indexing_data.append({
                    "index": index_name,
                    "docs_indexed": index_total,
                    "time_ms": index_time_ms,
                    "docs_per_sec": (index_total / (index_time_ms / 1000)) if index_time_ms > 0 else 0
                })

        indexing_data.sort(key=lambda x: x["docs_per_sec"], reverse=True)

        # Display indexing rates
        table = Table(title="Indexing Performance by Index", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Index", style="cyan")
        table.add_column("Docs Indexed", justify="right", style="white")
        table.add_column("Time (ms)", justify="right", style="yellow")
        table.add_column("Docs/Sec", justify="right", style="green")

        for item in indexing_data[:20]:
            table.add_row(
                item["index"],
                f"{item['docs_indexed']:,}",
                f"{item['time_ms']:,}",
                f"{item['docs_per_sec']:.2f}"
            )

        console.print(table)
        console.print()

        # Check for bottlenecks in thread pools
        console.print("[bold cyan]Thread Pool Status:[/bold cyan]\n")

        bottleneck_table = Table(title="Potential Bottlenecks", box=box.ROUNDED, title_style="bold yellow")
        bottleneck_table.add_column("Node", style="cyan")
        bottleneck_table.add_column("Pool", style="white")
        bottleneck_table.add_column("Queue", justify="right", style="yellow")
        bottleneck_table.add_column("Rejected", justify="right", style="red")
        bottleneck_table.add_column("Rejection Rate", justify="right", style="red")

        nodes = nodes_stats.get("nodes", {})
        has_bottlenecks = False

        # Collect bottleneck data for analysis
        bottleneck_data = []
        node_info = {}

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            thread_pools = node_data.get("thread_pool", {})

            # Collect node resource info for recommendations
            node_info[node_name] = {
                "cpu_percent": node_data.get("os", {}).get("cpu", {}).get("percent", 0),
                "heap_used": node_data.get("jvm", {}).get("mem", {}).get("heap_used_in_bytes", 0),
                "heap_max": node_data.get("jvm", {}).get("mem", {}).get("heap_max_in_bytes", 1),
                "heap_percent": node_data.get("jvm", {}).get("mem", {}).get("heap_used_percent", 0),
            }

            # Check write/bulk pools
            for pool_name in ["write", "bulk"]:
                if pool_name in thread_pools:
                    pool = thread_pools[pool_name]
                    queue = pool.get("queue", 0)
                    rejected = pool.get("rejected", 0)
                    completed = pool.get("completed", 0)

                    # Calculate rejection rate
                    total_requests = completed + rejected
                    rejection_rate = (rejected / total_requests * 100) if total_requests > 0 else 0

                    if queue > 0 or rejected > 0:
                        has_bottlenecks = True
                        bottleneck_table.add_row(
                            node_name,
                            pool_name,
                            str(queue),
                            f"{rejected:,}",
                            f"{rejection_rate:.2f}%"
                        )

                        bottleneck_data.append({
                            "node": node_name,
                            "pool": pool_name,
                            "queue": queue,
                            "rejected": rejected,
                            "completed": completed,
                            "rejection_rate": rejection_rate,
                            "queue_size": pool.get("queue_size", 0),
                            "threads": pool.get("threads", 0),
                        })

        if has_bottlenecks:
            console.print(bottleneck_table)
            console.print()
            console.print("[yellow]⚠️  Bottlenecks detected! Consider increasing thread pool sizes or reducing indexing rate.[/yellow]\n")

            # Generate detailed recommendations
            _display_indexing_recommendations(
                bottleneck_data,
                node_info,
                indexing_data,
                nodes
            )
        else:
            console.print("[green]✅ No bottlenecks detected in thread pools.[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch indexing performance data: {e}[/red]\n")


def option_search_performance_dashboard(es):
    """Show search query latency, throughput, and cache hit rates."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Search Performance Dashboard"])

    console.print("\n[cyan]Analyzing search performance...[/cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching search metrics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            stats = es.indices.stats(metric=["search", "request_cache"])
            nodes_stats = es.nodes.stats(metric=["indices"])

        # Calculate cluster-wide metrics
        all_stats = stats.get("_all", {}).get("total", {})
        search_stats = all_stats.get("search", {})
        cache_stats = all_stats.get("request_cache", {})

        query_total = search_stats.get("query_total", 0)
        query_time_ms = search_stats.get("query_time_in_millis", 0)
        fetch_total = search_stats.get("fetch_total", 0)
        fetch_time_ms = search_stats.get("fetch_time_in_millis", 0)

        cache_hits = cache_stats.get("hit_count", 0)
        cache_misses = cache_stats.get("miss_count", 0)
        cache_total = cache_hits + cache_misses
        cache_hit_rate = (cache_hits / cache_total * 100) if cache_total > 0 else 0

        # Display cluster-wide metrics
        metrics_table = Table(title="Cluster-Wide Search Metrics", box=box.DOUBLE_EDGE, title_style="bold cyan")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="white")

        avg_query_time = (query_time_ms / query_total) if query_total > 0 else 0
        avg_fetch_time = (fetch_time_ms / fetch_total) if fetch_total > 0 else 0

        metrics_table.add_row("Total Queries", f"{query_total:,}")
        metrics_table.add_row("Avg Query Time (ms)", f"{avg_query_time:.2f}")
        metrics_table.add_row("Total Fetch Operations", f"{fetch_total:,}")
        metrics_table.add_row("Avg Fetch Time (ms)", f"{avg_fetch_time:.2f}")
        metrics_table.add_row("Cache Hit Rate", f"{cache_hit_rate:.2f}%")
        metrics_table.add_row("Cache Hits", f"{cache_hits:,}")
        metrics_table.add_row("Cache Misses", f"{cache_misses:,}")

        console.print(metrics_table)
        console.print()

        # Per-index search performance
        indices_stats = stats.get("indices", {})
        index_performance = []

        for index_name, index_data in indices_stats.items():
            idx_search = index_data.get("total", {}).get("search", {})
            idx_query_total = idx_search.get("query_total", 0)
            idx_query_time = idx_search.get("query_time_in_millis", 0)

            if idx_query_total > 0:
                index_performance.append({
                    "index": index_name,
                    "queries": idx_query_total,
                    "avg_latency": idx_query_time / idx_query_total,
                    "qps": idx_query_total  # This is cumulative, not per-second
                })

        index_performance.sort(key=lambda x: x["avg_latency"], reverse=True)

        perf_table = Table(title="Slowest Indices by Query Latency", box=box.ROUNDED, title_style="bold yellow")
        perf_table.add_column("Index", style="cyan")
        perf_table.add_column("Total Queries", justify="right", style="white")
        perf_table.add_column("Avg Latency (ms)", justify="right", style="red")

        for item in index_performance[:15]:
            perf_table.add_row(
                item["index"],
                f"{item['queries']:,}",
                f"{item['avg_latency']:.2f}"
            )

        console.print(perf_table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch search performance data: {e}[/red]\n")


def option_cluster_health_timeline(es):
    """Display historical cluster health status changes."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Cluster Health Timeline"])

    console.print("\n[cyan]Fetching cluster health timeline...[/cyan]\n")

    # Prompt for time range
    console.print("[bold]Select time range:[/bold]")
    console.print("1) Last 7 days")
    console.print("2) Last 30 days")
    console.print("3) Last 90 days\n")

    choice = safe_input("Select option (default 1): ").strip() or "1"

    days_map = {"1": 7, "2": 30, "3": 90}
    days = days_map.get(choice, 7)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching cluster stats..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            # Get current cluster health
            health = es.cluster.health()
            # Get cluster stats for historical context
            stats = es.cluster.stats()

        # Display current health
        current_table = Table(title=f"Current Cluster Health", box=box.DOUBLE_EDGE, title_style="bold cyan")
        current_table.add_column("Metric", style="cyan")
        current_table.add_column("Value", style="white")

        status = health.get("status", "unknown")
        status_color = {"green": "green", "yellow": "yellow", "red": "red"}.get(status, "white")

        current_table.add_row("Status", f"[{status_color}]{status}[/{status_color}]")
        current_table.add_row("Nodes", str(health.get("number_of_nodes", 0)))
        current_table.add_row("Active Shards", str(health.get("active_shards", 0)))
        current_table.add_row("Unassigned Shards", str(health.get("unassigned_shards", 0)))
        current_table.add_row("Relocating Shards", str(health.get("relocating_shards", 0)))
        current_table.add_row("Initializing Shards", str(health.get("initializing_shards", 0)))

        console.print(current_table)
        console.print()

        # Note about historical data
        info_panel = Panel(
            f"[yellow]Note:[/yellow] Elasticsearch does not store historical cluster health data by default.\n\n"
            f"To track health changes over time, consider:\n"
            f"• Setting up monitoring with Elastic Stack Monitoring\n"
            f"• Using Metricbeat to collect cluster metrics\n"
            f"• Implementing custom health check logging\n\n"
            f"Current snapshot shows health status as of: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            title="ℹ️  Historical Data Limitation",
            box=box.ROUNDED,
            style="yellow"
        )
        console.print(info_panel)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch cluster health data: {e}[/red]\n")


def option_node_resource_usage(es):
    """Display per-node CPU, memory, disk usage, and JVM stats."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Node Resource Usage"])

    console.print("\n[cyan]Fetching node resource usage...[/cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching node statistics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            nodes_stats = es.nodes.stats(metric=["os", "jvm", "fs"])

        nodes = nodes_stats.get("nodes", {})

        if not nodes:
            console.print("[yellow]🟡 No node data available.[/yellow]\n")
            return

        # Display resource usage per node
        table = Table(title="Node Resource Usage", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Node", style="cyan")
        table.add_column("CPU %", justify="right", style="yellow")
        table.add_column("Heap Used", justify="right", style="white")
        table.add_column("Heap %", justify="right", style="yellow")
        table.add_column("Disk Used", justify="right", style="white")
        table.add_column("Disk %", justify="right", style="red")

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)

            # CPU usage
            os_stats = node_data.get("os", {})
            cpu_percent = os_stats.get("cpu", {}).get("percent", 0)

            # JVM heap
            jvm_stats = node_data.get("jvm", {})
            heap_used_bytes = jvm_stats.get("mem", {}).get("heap_used_in_bytes", 0)
            heap_max_bytes = jvm_stats.get("mem", {}).get("heap_max_in_bytes", 1)
            heap_percent = (heap_used_bytes / heap_max_bytes * 100) if heap_max_bytes > 0 else 0

            # Disk usage
            fs_stats = node_data.get("fs", {})
            total_bytes = fs_stats.get("total", {}).get("total_in_bytes", 1)
            available_bytes = fs_stats.get("total", {}).get("available_in_bytes", 0)
            used_bytes = total_bytes - available_bytes
            disk_percent = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0

            # Format sizes
            from ..utils.formatters import bytes_to_human

            table.add_row(
                node_name,
                f"{cpu_percent}%",
                bytes_to_human(heap_used_bytes),
                f"{heap_percent:.1f}%",
                bytes_to_human(used_bytes),
                f"{disk_percent:.1f}%"
            )

        console.print(table)
        console.print()

        # JVM details table
        jvm_table = Table(title="JVM Statistics", box=box.ROUNDED, title_style="bold cyan")
        jvm_table.add_column("Node", style="cyan")
        jvm_table.add_column("Uptime", style="white")
        jvm_table.add_column("GC Count", justify="right", style="yellow")
        jvm_table.add_column("GC Time", justify="right", style="yellow")

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            jvm_stats = node_data.get("jvm", {})

            uptime_ms = jvm_stats.get("uptime_in_millis", 0)
            uptime_hours = uptime_ms / (1000 * 60 * 60)

            gc_collectors = jvm_stats.get("gc", {}).get("collectors", {})
            total_gc_count = 0
            total_gc_time = 0

            for collector_name, collector_data in gc_collectors.items():
                total_gc_count += collector_data.get("collection_count", 0)
                total_gc_time += collector_data.get("collection_time_in_millis", 0)

            jvm_table.add_row(
                node_name,
                f"{uptime_hours:.1f}h",
                f"{total_gc_count:,}",
                f"{total_gc_time:,} ms"
            )

        console.print(jvm_table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch node resource data: {e}[/red]\n")


def option_hot_spot_detector(es):
    """Analyze shard distribution and query load to identify hot spots."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Hot Spot Detector"])

    console.print("\n[cyan]Analyzing cluster for hot spots...[/cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching shard and node data..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            # Get shard allocation
            shards = es.cat.shards(format="json", h="index,shard,prirep,state,node,store")
            # Get node stats
            nodes_stats = es.nodes.stats(metric=["indices"])

        # Analyze shard distribution per node
        node_shard_count = defaultdict(int)
        node_shard_size = defaultdict(int)

        for shard in shards:
            node = shard.get("node")
            if node and node != "UNASSIGNED":
                node_shard_count[node] += 1
                # Parse size
                size_str = shard.get("store", "0b")
                from ..utils.formatters import size_to_bytes
                node_shard_size[node] += size_to_bytes(size_str)

        # Display shard distribution
        shard_table = Table(title="Shard Distribution by Node", box=box.ROUNDED, title_style="bold cyan")
        shard_table.add_column("Node", style="cyan")
        shard_table.add_column("Shard Count", justify="right", style="white")
        shard_table.add_column("Total Size", justify="right", style="yellow")
        shard_table.add_column("Status", style="white")

        avg_shard_count = sum(node_shard_count.values()) / len(node_shard_count) if node_shard_count else 0

        for node, count in sorted(node_shard_count.items(), key=lambda x: x[1], reverse=True):
            from ..utils.formatters import bytes_to_human
            size = node_shard_size[node]

            # Determine if this is a hot spot (>20% above average)
            status = "🔥 HOT SPOT" if count > avg_shard_count * 1.2 else "✅ Normal"

            shard_table.add_row(
                node,
                str(count),
                bytes_to_human(size),
                status
            )

        console.print(shard_table)
        console.print()

        # Analyze query load per node
        nodes = nodes_stats.get("nodes", {})
        node_query_load = []

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            indices_stats = node_data.get("indices", {})
            search_stats = indices_stats.get("search", {})

            query_total = search_stats.get("query_total", 0)
            query_time = search_stats.get("query_time_in_millis", 0)

            node_query_load.append({
                "node": node_name,
                "queries": query_total,
                "time_ms": query_time,
                "avg_time": (query_time / query_total) if query_total > 0 else 0
            })

        node_query_load.sort(key=lambda x: x["queries"], reverse=True)

        query_table = Table(title="Query Load by Node", box=box.ROUNDED, title_style="bold yellow")
        query_table.add_column("Node", style="cyan")
        query_table.add_column("Total Queries", justify="right", style="white")
        query_table.add_column("Total Time (ms)", justify="right", style="yellow")
        query_table.add_column("Avg Time (ms)", justify="right", style="red")

        for item in node_query_load:
            query_table.add_row(
                item["node"],
                f"{item['queries']:,}",
                f"{item['time_ms']:,}",
                f"{item['avg_time']:.2f}"
            )

        console.print(query_table)
        console.print()

        # Recommendations
        recommendations = Panel(
            "[bold yellow]Hot Spot Mitigation Strategies:[/bold yellow]\n\n"
            "• Rebalance shards across nodes using cluster reroute API\n"
            "• Consider adding more nodes to distribute load\n"
            "• Review index allocation settings and shard allocation awareness\n"
            "• Use index lifecycle management to move old data to dedicated nodes\n"
            "• Monitor and adjust shard size (target: 10-50GB per shard)",
            title="💡 Recommendations",
            box=box.ROUNDED,
            style="yellow"
        )
        console.print(recommendations)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not analyze hot spots: {e}[/red]\n")


def option_realtime_metrics_dashboard(es):
    """Display a live, auto-refreshing dashboard with real-time cluster metrics."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Real-time Metrics Dashboard"])

    console.print("\n[cyan]Starting real-time metrics dashboard...[/cyan]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    def generate_dashboard():
        """Generate the dashboard layout with current metrics."""
        try:
            # Fetch current metrics
            health = es.cluster.health()
            nodes_stats = es.nodes.stats(metric=["os", "jvm", "indices"])

            # Create layout
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="footer", size=3)
            )

            # Header with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header_table = Table.grid(expand=True)
            header_table.add_column(justify="center")
            header_table.add_row(f"[bold cyan]Real-time Metrics Dashboard[/bold cyan] | Last Update: {timestamp}")
            layout["header"].update(Panel(header_table, style="cyan"))

            # Body split into sections
            layout["body"].split_row(
                Layout(name="left"),
                Layout(name="right")
            )

            # Cluster status section
            status = health.get("status", "unknown")
            status_color = {"green": "green", "yellow": "yellow", "red": "red"}.get(status, "white")

            cluster_table = Table(title="Cluster Status", box=box.ROUNDED, title_style="bold cyan")
            cluster_table.add_column("Metric", style="cyan")
            cluster_table.add_column("Value", style="white")
            cluster_table.add_row("Status", f"[{status_color}]●[/{status_color}] {status.upper()}")
            cluster_table.add_row("Nodes", str(health.get("number_of_nodes", 0)))
            cluster_table.add_row("Active Shards", str(health.get("active_shards", 0)))
            cluster_table.add_row("Unassigned", str(health.get("unassigned_shards", 0)))

            # Node metrics section
            nodes = nodes_stats.get("nodes", {})
            node_table = Table(title="Node Metrics", box=box.ROUNDED, title_style="bold cyan")
            node_table.add_column("Node", style="cyan")
            node_table.add_column("CPU %", justify="right", style="yellow")
            node_table.add_column("Memory", justify="right", style="white")

            total_indexing_rate = 0
            total_search_rate = 0

            for node_id, node_data in nodes.items():
                node_name = node_data.get("name", node_id)[:20]

                # CPU
                cpu_percent = node_data.get("os", {}).get("cpu", {}).get("percent", 0)

                # Memory
                heap_used = node_data.get("jvm", {}).get("mem", {}).get("heap_used_in_bytes", 0)
                heap_max = node_data.get("jvm", {}).get("mem", {}).get("heap_max_in_bytes", 1)
                heap_percent = (heap_used / heap_max * 100) if heap_max > 0 else 0

                node_table.add_row(
                    node_name,
                    f"{cpu_percent}%",
                    f"{bytes_to_human(heap_used)} ({heap_percent:.0f}%)"
                )

                # Calculate rates
                indices_stats = node_data.get("indices", {})
                indexing_stats = indices_stats.get("indexing", {})
                search_stats = indices_stats.get("search", {})

                total_indexing_rate += indexing_stats.get("index_total", 0)
                total_search_rate += search_stats.get("query_total", 0)

            # Performance metrics section
            perf_table = Table(title="Performance Metrics", box=box.ROUNDED, title_style="bold cyan")
            perf_table.add_column("Metric", style="cyan")
            perf_table.add_column("Value", justify="right", style="white")
            perf_table.add_row("Total Docs Indexed", f"{total_indexing_rate:,}")
            perf_table.add_row("Total Queries", f"{total_search_rate:,}")

            # Arrange sections
            layout["left"].split_column(
                Layout(cluster_table),
                Layout(perf_table)
            )
            layout["right"].update(node_table)

            # Footer
            footer_table = Table.grid(expand=True)
            footer_table.add_column(justify="center")
            footer_table.add_row("[dim]Auto-refreshing every 3 seconds | Press Ctrl+C to exit[/dim]")
            layout["footer"].update(Panel(footer_table, style="dim"))

            return layout

        except Exception as e:
            error_panel = Panel(
                f"[red]Error fetching metrics: {e}[/red]",
                title="Error",
                box=box.ROUNDED
            )
            return error_panel

    try:
        with Live(generate_dashboard(), refresh_per_second=0.5, console=console) as live:
            while True:
                time.sleep(3)
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        console.print("\n[green]✅ Dashboard closed.[/green]\n")
    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not start dashboard: {e}[/red]\n")


def option_historical_trend_analysis(es):
    """Analyze historical trends with time-series data and growth rate calculations."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Historical Trend Analysis"])

    console.print("\n[cyan]Analyzing historical trends...[/cyan]\n")

    # Prompt for time range
    console.print("[bold]Select time range:[/bold]")
    console.print("1) Last 1 hour")
    console.print("2) Last 24 hours")
    console.print("3) Last 7 days")
    console.print("4) Last 30 days\n")

    choice = safe_input("Select option (default 2): ").strip() or "2"

    time_ranges = {
        "1": ("1 hour", 1),
        "2": ("24 hours", 24),
        "3": ("7 days", 168),
        "4": ("30 days", 720)
    }

    range_name, hours = time_ranges.get(choice, ("24 hours", 24))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching trend data..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            # Get current stats
            stats = es.indices.stats(metric=["indexing", "search"])
            nodes_stats = es.nodes.stats(metric=["os", "jvm", "indices"])

        # Display limitation notice
        info_panel = Panel(
            f"[yellow]Note:[/yellow] Elasticsearch does not store historical metrics by default.\n\n"
            f"This analysis shows current snapshot data and calculates simple projections.\n\n"
            f"For true historical trend analysis, consider:\n"
            f"• Enabling Stack Monitoring (formerly X-Pack Monitoring)\n"
            f"• Using Metricbeat to collect time-series metrics\n"
            f"• Implementing custom metric collection with Elasticsearch as storage\n\n"
            f"Selected time range: [cyan]{range_name}[/cyan]",
            title="ℹ️  Historical Data Limitation",
            box=box.ROUNDED,
            style="yellow"
        )
        console.print(info_panel)
        console.print()

        # Current snapshot metrics
        all_stats = stats.get("_all", {}).get("total", {})
        indexing_stats = all_stats.get("indexing", {})
        search_stats = all_stats.get("search", {})

        total_indexed = indexing_stats.get("index_total", 0)
        total_queries = search_stats.get("query_total", 0)
        total_query_time = search_stats.get("query_time_in_millis", 0)

        avg_query_latency = (total_query_time / total_queries) if total_queries > 0 else 0

        # Calculate simple projections based on current rates
        nodes = nodes_stats.get("nodes", {})
        total_uptime_hours = 0
        node_count = len(nodes)

        for node_data in nodes.values():
            uptime_ms = node_data.get("jvm", {}).get("uptime_in_millis", 0)
            total_uptime_hours += uptime_ms / (1000 * 60 * 60)

        avg_uptime_hours = total_uptime_hours / node_count if node_count > 0 else 1

        # Current rates
        docs_per_hour = total_indexed / avg_uptime_hours if avg_uptime_hours > 0 else 0
        queries_per_hour = total_queries / avg_uptime_hours if avg_uptime_hours > 0 else 0

        # Projected growth
        projected_docs = docs_per_hour * hours
        projected_queries = queries_per_hour * hours

        # Display current metrics
        current_table = Table(title="Current Snapshot Metrics", box=box.ROUNDED, title_style="bold cyan")
        current_table.add_column("Metric", style="cyan")
        current_table.add_column("Value", justify="right", style="white")
        current_table.add_column("Rate/Hour", justify="right", style="yellow")

        current_table.add_row("Total Documents Indexed", f"{total_indexed:,}", f"{docs_per_hour:,.0f}")
        current_table.add_row("Total Queries", f"{total_queries:,}", f"{queries_per_hour:,.0f}")
        current_table.add_row("Avg Query Latency (ms)", f"{avg_query_latency:.2f}", "-")
        current_table.add_row("Cluster Uptime (avg)", f"{avg_uptime_hours:.1f}h", "-")

        console.print(current_table)
        console.print()

        # Display projections
        projection_table = Table(
            title=f"Projected Growth ({range_name})",
            box=box.ROUNDED,
            title_style="bold yellow"
        )
        projection_table.add_column("Metric", style="cyan")
        projection_table.add_column("Projected Value", justify="right", style="white")
        projection_table.add_column("Growth Rate", justify="right", style="green")

        growth_rate_docs = (projected_docs / total_indexed * 100) if total_indexed > 0 else 0
        growth_rate_queries = (projected_queries / total_queries * 100) if total_queries > 0 else 0

        projection_table.add_row(
            "Documents Indexed",
            f"{projected_docs:,.0f}",
            f"+{growth_rate_docs:.1f}%"
        )
        projection_table.add_row(
            "Queries Executed",
            f"{projected_queries:,.0f}",
            f"+{growth_rate_queries:.1f}%"
        )

        console.print(projection_table)
        console.print()

        # Resource utilization trends
        resource_table = Table(title="Current Resource Utilization", box=box.ROUNDED, title_style="bold cyan")
        resource_table.add_column("Node", style="cyan")
        resource_table.add_column("CPU %", justify="right", style="yellow")
        resource_table.add_column("Heap %", justify="right", style="yellow")
        resource_table.add_column("Status", style="white")

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)

            cpu_percent = node_data.get("os", {}).get("cpu", {}).get("percent", 0)
            heap_used = node_data.get("jvm", {}).get("mem", {}).get("heap_used_in_bytes", 0)
            heap_max = node_data.get("jvm", {}).get("mem", {}).get("heap_max_in_bytes", 1)
            heap_percent = (heap_used / heap_max * 100) if heap_max > 0 else 0

            # Determine status
            if cpu_percent > 80 or heap_percent > 85:
                status = "[red]🔴 Critical[/red]"
            elif cpu_percent > 60 or heap_percent > 70:
                status = "[yellow]🟡 Elevated[/yellow]"
            else:
                status = "[green]🟢 Normal[/green]"

            resource_table.add_row(
                node_name,
                f"{cpu_percent}%",
                f"{heap_percent:.1f}%",
                status
            )

        console.print(resource_table)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch trend data: {e}[/red]\n")


def option_jvm_heap_analysis(es):
    """Detailed JVM memory analyzer showing heap pools and garbage collection statistics."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "JVM Heap Analysis"])

    console.print("\n[cyan]Analyzing JVM heap usage...[/cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching JVM statistics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            nodes_stats = es.nodes.stats(metric="jvm")

        nodes = nodes_stats.get("nodes", {})

        if not nodes:
            console.print("[yellow]🟡 No node data available.[/yellow]\n")
            return

        # Display heap usage per node
        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            jvm_stats = node_data.get("jvm", {})

            console.print(f"[bold cyan]Node: {node_name}[/bold cyan]\n")

            # Heap memory table
            heap_table = Table(title="Heap Memory", box=box.ROUNDED, title_style="bold cyan")
            heap_table.add_column("Metric", style="cyan")
            heap_table.add_column("Value", justify="right", style="white")
            heap_table.add_column("Percentage", justify="right", style="yellow")

            mem_stats = jvm_stats.get("mem", {})
            heap_used = mem_stats.get("heap_used_in_bytes", 0)
            heap_max = mem_stats.get("heap_max_in_bytes", 1)
            heap_committed = mem_stats.get("heap_committed_in_bytes", 0)
            heap_percent = mem_stats.get("heap_used_percent", 0)

            # Determine status
            if heap_percent > 95:
                status = "[red]🔴 CRITICAL[/red]"
            elif heap_percent > 85:
                status = "[yellow]🟡 WARNING[/yellow]"
            else:
                status = "[green]🟢 NORMAL[/green]"

            heap_table.add_row("Heap Used", bytes_to_human(heap_used), f"{heap_percent}%")
            heap_table.add_row("Heap Max", bytes_to_human(heap_max), "100%")
            heap_table.add_row("Heap Committed", bytes_to_human(heap_committed), f"{(heap_committed/heap_max*100):.1f}%")
            heap_table.add_row("Status", status, "")

            console.print(heap_table)
            console.print()

            # Memory pools breakdown
            pools = jvm_stats.get("mem", {}).get("pools", {})

            if pools:
                pools_table = Table(title="Memory Pools Breakdown", box=box.ROUNDED, title_style="bold cyan")
                pools_table.add_column("Pool", style="cyan")
                pools_table.add_column("Used", justify="right", style="white")
                pools_table.add_column("Max", justify="right", style="white")
                pools_table.add_column("Usage %", justify="right", style="yellow")

                for pool_name, pool_data in pools.items():
                    pool_used = pool_data.get("used_in_bytes", 0)
                    pool_max = pool_data.get("max_in_bytes", 0)

                    if pool_max > 0:
                        pool_percent = (pool_used / pool_max * 100)
                        pools_table.add_row(
                            pool_name,
                            bytes_to_human(pool_used),
                            bytes_to_human(pool_max),
                            f"{pool_percent:.1f}%"
                        )
                    else:
                        pools_table.add_row(
                            pool_name,
                            bytes_to_human(pool_used),
                            "N/A",
                            "N/A"
                        )

                console.print(pools_table)
                console.print()

            # Non-heap memory
            non_heap_used = mem_stats.get("non_heap_used_in_bytes", 0)
            non_heap_committed = mem_stats.get("non_heap_committed_in_bytes", 0)

            non_heap_table = Table(title="Non-Heap Memory", box=box.ROUNDED, title_style="bold cyan")
            non_heap_table.add_column("Metric", style="cyan")
            non_heap_table.add_column("Value", justify="right", style="white")

            non_heap_table.add_row("Non-Heap Used", bytes_to_human(non_heap_used))
            non_heap_table.add_row("Non-Heap Committed", bytes_to_human(non_heap_committed))

            console.print(non_heap_table)
            console.print()

            # Garbage collection statistics
            gc_collectors = jvm_stats.get("gc", {}).get("collectors", {})

            if gc_collectors:
                gc_table = Table(title="Garbage Collection Statistics", box=box.ROUNDED, title_style="bold yellow")
                gc_table.add_column("Collector", style="cyan")
                gc_table.add_column("Collection Count", justify="right", style="white")
                gc_table.add_column("Collection Time", justify="right", style="yellow")
                gc_table.add_column("Avg Time (ms)", justify="right", style="red")

                for collector_name, collector_data in gc_collectors.items():
                    gc_count = collector_data.get("collection_count", 0)
                    gc_time = collector_data.get("collection_time_in_millis", 0)
                    avg_gc_time = (gc_time / gc_count) if gc_count > 0 else 0

                    gc_table.add_row(
                        collector_name,
                        f"{gc_count:,}",
                        f"{gc_time:,} ms",
                        f"{avg_gc_time:.2f}"
                    )

                console.print(gc_table)
                console.print()

            console.print("[dim]" + "─" * 80 + "[/dim]\n")

        # Recommendations panel
        recommendations = Panel(
            "[bold yellow]JVM Heap Recommendations:[/bold yellow]\n\n"
            "• [red]Critical (>95%):[/red] Immediate action required - increase heap size or reduce load\n"
            "• [yellow]Warning (>85%):[/yellow] Monitor closely - consider heap tuning\n"
            "• Heap size should be set to 50% of available RAM (max 31GB for compressed oops)\n"
            "• Monitor GC frequency - frequent collections indicate memory pressure\n"
            "• Old generation collections should be infrequent (< 1 per hour)\n"
            "• Consider adjusting GC settings if pause times are high",
            title="💡 Optimization Tips",
            box=box.ROUNDED,
            style="yellow"
        )
        console.print(recommendations)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch JVM heap data: {e}[/red]\n")


def option_thread_pool_monitor(es):
    """Comprehensive thread pool monitoring with bottleneck detection."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Thread Pool Monitor"])

    console.print("\n[cyan]Monitoring thread pools...[/cyan]\n")

    # Thread pools to monitor
    monitored_pools = [
        "search", "write", "bulk", "get", "analyze",
        "snapshot", "warmer", "refresh", "listener", "management"
    ]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching thread pool statistics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            nodes_stats = es.nodes.stats(metric="thread_pool")

        nodes = nodes_stats.get("nodes", {})

        if not nodes:
            console.print("[yellow]🟡 No node data available.[/yellow]\n")
            return

        # Aggregate cluster-wide stats
        cluster_totals = defaultdict(lambda: {
            "active": 0,
            "queue": 0,
            "rejected": 0,
            "completed": 0
        })

        bottlenecks_detected = False

        # Per-node thread pool table
        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            thread_pools = node_data.get("thread_pool", {})

            console.print(f"[bold cyan]Node: {node_name}[/bold cyan]\n")

            node_table = Table(title="Thread Pool Status", box=box.ROUNDED, title_style="bold cyan")
            node_table.add_column("Pool", style="cyan")
            node_table.add_column("Active", justify="right", style="white")
            node_table.add_column("Queue", justify="right", style="yellow")
            node_table.add_column("Queue Size", justify="right", style="white")
            node_table.add_column("Rejected", justify="right", style="red")
            node_table.add_column("Completed", justify="right", style="green")
            node_table.add_column("Status", style="white")

            for pool_name in monitored_pools:
                if pool_name in thread_pools:
                    pool = thread_pools[pool_name]
                    active = pool.get("active", 0)
                    queue = pool.get("queue", 0)
                    queue_size = pool.get("queue_size", 0)
                    rejected = pool.get("rejected", 0)
                    completed = pool.get("completed", 0)

                    # Determine status
                    if rejected > 0:
                        status = "[red]🔴 REJECTING[/red]"
                        bottlenecks_detected = True
                    elif queue > 0:
                        status = "[yellow]🟡 QUEUED[/yellow]"
                        bottlenecks_detected = True
                    else:
                        status = "[green]🟢 OK[/green]"

                    node_table.add_row(
                        pool_name,
                        str(active),
                        str(queue),
                        str(queue_size) if queue_size > 0 else "N/A",
                        str(rejected),
                        f"{completed:,}",
                        status
                    )

                    # Aggregate for cluster totals
                    cluster_totals[pool_name]["active"] += active
                    cluster_totals[pool_name]["queue"] += queue
                    cluster_totals[pool_name]["rejected"] += rejected
                    cluster_totals[pool_name]["completed"] += completed

            console.print(node_table)
            console.print()

        # Cluster-wide totals
        console.print("[bold cyan]Cluster-Wide Thread Pool Totals[/bold cyan]\n")

        cluster_table = Table(title="Aggregated Thread Pool Statistics", box=box.DOUBLE_EDGE, title_style="bold cyan")
        cluster_table.add_column("Pool", style="cyan")
        cluster_table.add_column("Total Active", justify="right", style="white")
        cluster_table.add_column("Total Queue", justify="right", style="yellow")
        cluster_table.add_column("Total Rejected", justify="right", style="red")
        cluster_table.add_column("Total Completed", justify="right", style="green")
        cluster_table.add_column("Status", style="white")

        for pool_name in monitored_pools:
            if pool_name in cluster_totals:
                totals = cluster_totals[pool_name]

                # Determine status
                if totals["rejected"] > 0:
                    status = "[red]🔴 BOTTLENECK[/red]"
                elif totals["queue"] > 0:
                    status = "[yellow]🟡 QUEUED[/yellow]"
                else:
                    status = "[green]🟢 HEALTHY[/green]"

                cluster_table.add_row(
                    pool_name,
                    str(totals["active"]),
                    str(totals["queue"]),
                    str(totals["rejected"]),
                    f"{totals['completed']:,}",
                    status
                )

        console.print(cluster_table)
        console.print()

        # Recommendations if bottlenecks detected
        if bottlenecks_detected:
            recommendations = Panel(
                "[bold red]Bottlenecks Detected![/bold red]\n\n"
                "[bold yellow]Recommendations:[/bold yellow]\n\n"
                "• [red]Rejected tasks:[/red] Increase thread pool size or queue capacity\n"
                "• [yellow]Queued tasks:[/yellow] Monitor for sustained queuing - may indicate capacity issues\n"
                "• Review elasticsearch.yml thread pool settings\n"
                "• Consider scaling horizontally (add more nodes)\n"
                "• For write/bulk pools: reduce indexing rate or increase resources\n"
                "• For search pools: optimize queries or add more search nodes\n"
                "• Monitor system resources (CPU, memory) for underlying constraints",
                title="⚠️  Action Required",
                box=box.ROUNDED,
                style="red"
            )
        else:
            recommendations = Panel(
                "[bold green]All Thread Pools Healthy![/bold green]\n\n"
                "• No queued or rejected tasks detected\n"
                "• Thread pools are operating within capacity\n"
                "• Continue monitoring during peak load periods",
                title="✅ Status: Healthy",
                box=box.ROUNDED,
                style="green"
            )

        console.print(recommendations)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch thread pool data: {e}[/red]\n")


def option_circuit_breaker_status(es):
    """Monitor circuit breaker status and usage across all nodes."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Circuit Breaker Status"])

    console.print("\n[cyan]Monitoring circuit breakers...[/cyan]\n")

    # Circuit breakers to monitor
    breaker_names = [
        "parent", "fielddata", "request", "in_flight_requests",
        "accounting", "model_inference"
    ]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching circuit breaker statistics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            nodes_stats = es.nodes.stats(metric="breaker")

        nodes = nodes_stats.get("nodes", {})

        if not nodes:
            console.print("[yellow]🟡 No node data available.[/yellow]\n")
            return

        critical_breakers = []

        # Per-node circuit breaker status
        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            breakers = node_data.get("breakers", {})

            console.print(f"[bold cyan]Node: {node_name}[/bold cyan]\n")

            breaker_table = Table(title="Circuit Breaker Status", box=box.ROUNDED, title_style="bold cyan")
            breaker_table.add_column("Breaker", style="cyan")
            breaker_table.add_column("Limit", justify="right", style="white")
            breaker_table.add_column("Estimated", justify="right", style="white")
            breaker_table.add_column("Usage %", justify="right", style="yellow")
            breaker_table.add_column("Overhead", justify="right", style="white")
            breaker_table.add_column("Tripped", justify="right", style="red")
            breaker_table.add_column("Status", style="white")

            for breaker_name in breaker_names:
                if breaker_name in breakers:
                    breaker = breakers[breaker_name]
                    limit_bytes = breaker.get("limit_size_in_bytes", 0)
                    estimated_bytes = breaker.get("estimated_size_in_bytes", 0)
                    overhead = breaker.get("overhead", 1.0)
                    tripped = breaker.get("tripped", 0)

                    # Calculate usage percentage
                    usage_percent = (estimated_bytes / limit_bytes * 100) if limit_bytes > 0 else 0

                    # Determine status
                    if usage_percent > 90:
                        status = "[red]🔴 CRITICAL[/red]"
                        critical_breakers.append({
                            "node": node_name,
                            "breaker": breaker_name,
                            "usage": usage_percent
                        })
                    elif usage_percent > 70:
                        status = "[yellow]🟡 WARNING[/yellow]"
                    else:
                        status = "[green]🟢 OK[/green]"

                    breaker_table.add_row(
                        breaker_name,
                        bytes_to_human(limit_bytes),
                        bytes_to_human(estimated_bytes),
                        f"{usage_percent:.1f}%",
                        f"{overhead:.2f}",
                        str(tripped),
                        status
                    )

            console.print(breaker_table)
            console.print()

        # Alert if critical breakers detected
        if critical_breakers:
            alert_table = Table(
                title="⚠️  Critical Circuit Breakers",
                box=box.DOUBLE_EDGE,
                title_style="bold red"
            )
            alert_table.add_column("Node", style="cyan")
            alert_table.add_column("Breaker", style="yellow")
            alert_table.add_column("Usage %", justify="right", style="red")

            for breaker in critical_breakers:
                alert_table.add_row(
                    breaker["node"],
                    breaker["breaker"],
                    f"{breaker['usage']:.1f}%"
                )

            console.print(alert_table)
            console.print()

            recommendations = Panel(
                "[bold red]Critical Circuit Breaker Alert![/bold red]\n\n"
                "[bold yellow]Immediate Actions:[/bold yellow]\n\n"
                "• [red]Parent breaker:[/red] Overall memory pressure - reduce load or increase heap\n"
                "• [red]Fielddata breaker:[/red] Reduce fielddata usage - use doc_values instead\n"
                "• [red]Request breaker:[/red] Large requests detected - optimize query size\n"
                "• [red]In-flight requests:[/red] Too many concurrent requests - implement rate limiting\n"
                "• [red]Accounting breaker:[/red] Internal memory tracking - monitor for memory leaks\n"
                "• [red]Model inference:[/red] ML model memory usage - reduce model size or requests\n\n"
                "Circuit breakers prevent OutOfMemoryErrors by rejecting requests when limits are reached.\n"
                "Adjust limits in elasticsearch.yml if legitimate usage patterns are being blocked.",
                title="🚨 Action Required",
                box=box.ROUNDED,
                style="red"
            )
        else:
            recommendations = Panel(
                "[bold green]All Circuit Breakers Healthy![/bold green]\n\n"
                "• All breakers are operating within safe limits (<70%)\n"
                "• No trips detected recently\n"
                "• Memory usage is well-controlled\n\n"
                "[bold]Circuit Breaker Information:[/bold]\n"
                "• [cyan]Parent:[/cyan] Overall memory limit (default: 95% of heap)\n"
                "• [cyan]Fielddata:[/cyan] Field data cache limit (default: 40% of heap)\n"
                "• [cyan]Request:[/cyan] Per-request memory limit (default: 60% of heap)\n"
                "• [cyan]In-flight requests:[/cyan] All in-flight requests (default: 100% of heap)\n"
                "• [cyan]Accounting:[/cyan] Request accounting (default: 100% of heap)\n"
                "• [cyan]Model inference:[/cyan] ML model memory (default: 50% of heap)",
                title="✅ Status: Healthy",
                box=box.ROUNDED,
                style="green"
            )

        console.print(recommendations)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch circuit breaker data: {e}[/red]\n")


def option_disk_io_monitor(es):
    """Monitor disk I/O performance metrics per node."""
    show_breadcrumb(["Main Menu", "Performance & Monitoring", "Disk I/O Monitor"])

    console.print("\n[cyan]Monitoring disk I/O performance...[/cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching disk I/O statistics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            nodes_stats = es.nodes.stats(metric="fs")

        nodes = nodes_stats.get("nodes", {})

        if not nodes:
            console.print("[yellow]🟡 No node data available.[/yellow]\n")
            return

        # Display limitation notice
        info_panel = Panel(
            "[yellow]Note:[/yellow] Elasticsearch provides limited disk I/O metrics.\n\n"
            "Available metrics include filesystem statistics and basic I/O operations.\n"
            "For detailed I/O monitoring, consider:\n"
            "• Using system monitoring tools (iostat, iotop)\n"
            "• Enabling detailed OS-level metrics collection\n"
            "• Metricbeat with system module for comprehensive I/O stats",
            title="ℹ️  I/O Metrics Limitation",
            box=box.ROUNDED,
            style="yellow"
        )
        console.print(info_panel)
        console.print()

        # Per-node disk I/O table
        io_table = Table(title="Disk I/O Statistics", box=box.ROUNDED, title_style="bold cyan")
        io_table.add_column("Node", style="cyan")
        io_table.add_column("Total Space", justify="right", style="white")
        io_table.add_column("Available", justify="right", style="green")
        io_table.add_column("Used", justify="right", style="yellow")
        io_table.add_column("Usage %", justify="right", style="red")
        io_table.add_column("Status", style="white")

        high_usage_nodes = []

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            fs_stats = node_data.get("fs", {})
            total_stats = fs_stats.get("total", {})

            total_bytes = total_stats.get("total_in_bytes", 0)
            available_bytes = total_stats.get("available_in_bytes", 0)
            free_bytes = total_stats.get("free_in_bytes", 0)

            used_bytes = total_bytes - available_bytes
            usage_percent = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0

            # Determine status
            if usage_percent > 90:
                status = "[red]🔴 CRITICAL[/red]"
                high_usage_nodes.append(node_name)
            elif usage_percent > 80:
                status = "[yellow]🟡 WARNING[/yellow]"
            else:
                status = "[green]🟢 OK[/green]"

            io_table.add_row(
                node_name,
                bytes_to_human(total_bytes),
                bytes_to_human(available_bytes),
                bytes_to_human(used_bytes),
                f"{usage_percent:.1f}%",
                status
            )

        console.print(io_table)
        console.print()

        # Detailed I/O operations (if available)
        io_ops_table = Table(title="I/O Operations", box=box.ROUNDED, title_style="bold cyan")
        io_ops_table.add_column("Node", style="cyan")
        io_ops_table.add_column("Read Ops", justify="right", style="white")
        io_ops_table.add_column("Write Ops", justify="right", style="white")
        io_ops_table.add_column("Read KB", justify="right", style="green")
        io_ops_table.add_column("Write KB", justify="right", style="yellow")

        has_io_data = False

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            fs_stats = node_data.get("fs", {})
            io_stats = fs_stats.get("io_stats", {})

            if io_stats and "total" in io_stats:
                has_io_data = True
                total_io = io_stats.get("total", {})

                read_ops = total_io.get("operations", 0)
                write_ops = total_io.get("write_operations", 0)
                read_kb = total_io.get("read_kilobytes", 0)
                write_kb = total_io.get("write_kilobytes", 0)

                io_ops_table.add_row(
                    node_name,
                    f"{read_ops:,}",
                    f"{write_ops:,}",
                    f"{read_kb:,}",
                    f"{write_kb:,}"
                )

        if has_io_data:
            console.print(io_ops_table)
            console.print()
        else:
            console.print("[dim]Detailed I/O operation metrics not available on this cluster.[/dim]\n")

        # Disk latency analysis (if available)
        latency_table = Table(title="Disk Latency Analysis", box=box.ROUNDED, title_style="bold yellow")
        latency_table.add_column("Node", style="cyan")
        latency_table.add_column("Avg Read Time (ms)", justify="right", style="white")
        latency_table.add_column("Avg Write Time (ms)", justify="right", style="white")
        latency_table.add_column("Status", style="white")

        has_latency_data = False
        high_latency_nodes = []

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            fs_stats = node_data.get("fs", {})
            io_stats = fs_stats.get("io_stats", {})

            if io_stats and "total" in io_stats:
                total_io = io_stats.get("total", {})

                read_ops = total_io.get("operations", 0)
                write_ops = total_io.get("write_operations", 0)
                read_time = total_io.get("read_time_in_millis", 0)
                write_time = total_io.get("write_time_in_millis", 0)

                avg_read_latency = (read_time / read_ops) if read_ops > 0 else 0
                avg_write_latency = (write_time / write_ops) if write_ops > 0 else 0

                if avg_read_latency > 0 or avg_write_latency > 0:
                    has_latency_data = True

                    # Determine status (>100ms is concerning)
                    if avg_read_latency > 100 or avg_write_latency > 100:
                        status = "[red]🔴 HIGH LATENCY[/red]"
                        high_latency_nodes.append(node_name)
                    elif avg_read_latency > 50 or avg_write_latency > 50:
                        status = "[yellow]🟡 ELEVATED[/yellow]"
                    else:
                        status = "[green]🟢 NORMAL[/green]"

                    latency_table.add_row(
                        node_name,
                        f"{avg_read_latency:.2f}",
                        f"{avg_write_latency:.2f}",
                        status
                    )

        if has_latency_data:
            console.print(latency_table)
            console.print()

        # Recommendations
        if high_usage_nodes or high_latency_nodes:
            recommendations = Panel(
                "[bold red]Disk Performance Issues Detected![/bold red]\n\n"
                "[bold yellow]Recommendations:[/bold yellow]\n\n"
                + (f"• [red]High disk usage:[/red] {', '.join(high_usage_nodes)}\n"
                   "  - Clean up old indices or snapshots\n"
                   "  - Implement ILM policies for data retention\n"
                   "  - Consider adding more storage capacity\n\n" if high_usage_nodes else "")
                + (f"• [red]High I/O latency:[/red] {', '.join(high_latency_nodes)}\n"
                   "  - Check for disk contention or hardware issues\n"
                   "  - Consider using faster storage (SSD)\n"
                   "  - Review merge and refresh settings\n"
                   "  - Monitor system I/O wait times\n\n" if high_latency_nodes else "")
                + "• Use dedicated data paths for better I/O distribution\n"
                "• Monitor disk queue depth and IOPS limits\n"
                "• Consider RAID configurations for better performance",
                title="⚠️  Action Required",
                box=box.ROUNDED,
                style="red"
            )
        else:
            recommendations = Panel(
                "[bold green]Disk I/O Performance Healthy![/bold green]\n\n"
                "• Disk usage is within acceptable limits (<80%)\n"
                "• I/O latency is normal (<50ms average)\n"
                "• Continue monitoring during peak load periods\n\n"
                "[bold]Best Practices:[/bold]\n"
                "• Maintain disk usage below 85% for optimal performance\n"
                "• Use SSDs for hot/warm tier data\n"
                "• Implement ILM for automatic data lifecycle management\n"
                "• Monitor disk metrics regularly",
                title="✅ Status: Healthy",
                box=box.ROUNDED,
                style="green"
            )

        console.print(recommendations)
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not fetch disk I/O data: {e}[/red]\n")

