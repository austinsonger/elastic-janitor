"""
Performance & Monitoring operations for Elastic Janitor.
Analyze query performance, indexing rates, search latency, and resource usage.
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box
from ..config import console
from ..utils import show_breadcrumb, safe_input, get_number_input


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
            nodes_stats = es.nodes.stats(metric="thread_pool")
        
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

        nodes = nodes_stats.get("nodes", {})
        has_bottlenecks = False

        for node_id, node_data in nodes.items():
            node_name = node_data.get("name", node_id)
            thread_pools = node_data.get("thread_pool", {})

            # Check write/bulk pools
            for pool_name in ["write", "bulk"]:
                if pool_name in thread_pools:
                    pool = thread_pools[pool_name]
                    queue = pool.get("queue", 0)
                    rejected = pool.get("rejected", 0)

                    if queue > 0 or rejected > 0:
                        has_bottlenecks = True
                        bottleneck_table.add_row(
                            node_name,
                            pool_name,
                            str(queue),
                            str(rejected)
                        )

        if has_bottlenecks:
            console.print(bottleneck_table)
            console.print()
            console.print("[yellow]⚠️  Bottlenecks detected! Consider increasing thread pool sizes or reducing indexing rate.[/yellow]\n")
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

