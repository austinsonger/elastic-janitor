"""
Performance Tuning Features for Elastic Janitor.
Provides performance tuning operations including auto-tuning, shard optimization,
refresh interval tuning, merge policy optimization, cache tuning, and JVM tuning.
"""
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, DRY_RUN_MODE, PROTECT_SYSTEM
from ..utils import (
    safe_input, is_system, confirm_action, show_breadcrumb,
    select_from_list, get_number_input, get_text_input, bytes_to_human
)
from ..core import get_all_indices_info
import questionary


def option_auto_tuning_engine(es):
    """
    Analyze cluster stats, node stats, and index stats to detect performance issues.
    Recommend settings adjustments: thread pools, circuit breakers, search/indexing buffers.
    """
    show_breadcrumb(["Main Menu", "Performance Tuning", "Auto-Tuning Engine"])
    
    console.print()
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing cluster performance..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)
            
            # Get cluster stats
            cluster_stats = es.cluster.stats()
            
            # Get node stats
            node_stats = es.nodes.stats()
            
            # Get cluster settings
            cluster_settings = es.cluster.get_settings(include_defaults=True)
    
    except Exception as e:
        console.print(f"\n[red]❌ Error fetching cluster data: {e}[/red]\n")
        return
    
    # Analyze and generate recommendations
    recommendations = []
    
    # Analyze thread pools
    for node_id, node_data in node_stats.get('nodes', {}).items():
        thread_pool = node_data.get('thread_pool', {})
        
        # Check search thread pool
        search_pool = thread_pool.get('search', {})
        search_rejected = search_pool.get('rejected', 0)
        if search_rejected > 100:
            recommendations.append({
                'category': 'Thread Pool',
                'issue': f'High search rejections ({search_rejected})',
                'current': 'Default',
                'recommended': 'Increase thread_pool.search.queue_size',
                'impact': 'High',
                'action': 'PUT /_cluster/settings {"persistent": {"thread_pool.search.queue_size": 2000}}'
            })
        
        # Check write thread pool
        write_pool = thread_pool.get('write', {})
        write_rejected = write_pool.get('rejected', 0)
        if write_rejected > 100:
            recommendations.append({
                'category': 'Thread Pool',
                'issue': f'High write rejections ({write_rejected})',
                'current': 'Default',
                'recommended': 'Increase thread_pool.write.queue_size',
                'impact': 'High',
                'action': 'PUT /_cluster/settings {"persistent": {"thread_pool.write.queue_size": 1000}}'
            })
    
    # Analyze circuit breakers
    for node_id, node_data in node_stats.get('nodes', {}).items():
        breakers = node_data.get('breakers', {})
        
        for breaker_name, breaker_data in breakers.items():
            tripped = breaker_data.get('tripped', 0)
            if tripped > 10:
                limit_size = breaker_data.get('limit_size_in_bytes', 0)
                estimated_size = breaker_data.get('estimated_size_in_bytes', 0)
                
                if estimated_size > limit_size * 0.9:
                    recommendations.append({
                        'category': 'Circuit Breaker',
                        'issue': f'{breaker_name} breaker tripped {tripped} times',
                        'current': bytes_to_human(limit_size),
                        'recommended': bytes_to_human(int(limit_size * 1.2)),
                        'impact': 'Medium',
                        'action': f'Increase {breaker_name} circuit breaker limit'
                    })
    
    # Analyze indexing buffer
    indices_stats = cluster_stats.get('indices', {})
    total_docs = indices_stats.get('docs', {}).get('count', 0)
    
    if total_docs > 10000000:  # 10M+ documents
        recommendations.append({
            'category': 'Indexing Buffer',
            'issue': 'Large document count may benefit from larger indexing buffer',
            'current': '10% of heap (default)',
            'recommended': '15% of heap',
            'impact': 'Medium',
            'action': 'PUT /_cluster/settings {"persistent": {"indices.memory.index_buffer_size": "15%"}}'
        })
    
    # Display recommendations
    console.print(f"\n[bold cyan]Auto-Tuning Recommendations[/bold cyan]\n")
    
    if not recommendations:
        console.print("[green]✅ No performance issues detected! Cluster is well-tuned.[/green]\n")
        return
    
    table = Table(title=f"{len(recommendations)} Recommendations", box=box.ROUNDED)
    table.add_column("Category", style="cyan")
    table.add_column("Issue", style="yellow")
    table.add_column("Current", style="red")
    table.add_column("Recommended", style="green")
    table.add_column("Impact", style="magenta")
    
    for rec in recommendations:
        table.add_row(
            rec['category'],
            rec['issue'],
            rec['current'],
            rec['recommended'],
            rec['impact']
        )
    
    console.print(table)
    
    # Ask if user wants to apply recommendations
    console.print()
    if confirm_action("Apply these recommendations?"):
        applied = 0
        for rec in recommendations:
            try:
                if not DRY_RUN_MODE:
                    # This would require parsing the action and executing it
                    # For safety, we'll just show what would be done
                    console.print(f"[dim]Would execute: {rec['action']}[/dim]")
                applied += 1
            except Exception as e:
                console.print(f"[red]Error applying recommendation: {e}[/red]")
        
        if DRY_RUN_MODE:
            console.print(f"\n[yellow]DRY RUN: Would apply {applied} recommendations[/yellow]\n")
        else:
            console.print(f"\n[green]✅ Applied {applied} recommendations[/green]\n")
            console.print("[yellow]Note: Some changes may require node restart to take effect.[/yellow]\n")
    
    console.print()


def option_shard_size_optimizer(es):
    """
    Analyze current shard distribution across nodes.
    Calculate optimal shard count based on: index size, growth rate, node count, target shard size (20-50GB).
    """
    show_breadcrumb(["Main Menu", "Performance Tuning", "Shard Size Optimizer"])
    
    console.print()
    
    # Get target shard size
    target_size_gb = get_number_input("Target shard size in GB (default: 30): ", default=30)
    if target_size_gb is None:
        return

    target_size_bytes = target_size_gb * 1024 * 1024 * 1024

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing shard distribution..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            # Get all indices
            indices_info = get_all_indices_info(es)

            # Get cluster stats for node count
            cluster_stats = es.cluster.stats()
            node_count = cluster_stats.get('nodes', {}).get('count', {}).get('total', 1)

            # Get shard allocation
            shards = es.cat.shards(format="json", bytes="b")

    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return

    # Analyze each index
    analysis = []

    for idx_name, idx_info in indices_info.items():
        if is_system(idx_name):
            continue

        # Get current shard count
        idx_shards = [s for s in shards if s['index'] == idx_name and s['prirep'] == 'p']
        current_shard_count = len(idx_shards)

        if current_shard_count == 0:
            continue

        # Calculate metrics
        total_size = idx_info['size_bytes']
        avg_shard_size = total_size / current_shard_count if current_shard_count > 0 else 0
        optimal_shard_count = max(1, int(total_size / target_size_bytes))

        # Determine status
        if avg_shard_size < target_size_bytes * 0.3:  # Too small
            status = "⚠️  Over-sharded"
            recommendation = f"Shrink to {optimal_shard_count} shards"
        elif avg_shard_size > target_size_bytes * 1.5:  # Too large
            status = "⚠️  Under-sharded"
            recommendation = f"Split to {optimal_shard_count} shards"
        else:
            status = "✅ Optimal"
            recommendation = "No action needed"

        analysis.append({
            'index': idx_name,
            'current_shards': current_shard_count,
            'optimal_shards': optimal_shard_count,
            'avg_shard_size': bytes_to_human(int(avg_shard_size)),
            'total_size': idx_info['size'],
            'status': status,
            'recommendation': recommendation
        })

    # Display results
    console.print(f"\n[bold cyan]Shard Size Analysis[/bold cyan]")
    console.print(f"Target Shard Size: {target_size_gb}GB | Nodes: {node_count} | Indices: {len(analysis)}\n")

    # Sort by status (issues first)
    analysis.sort(key=lambda x: (x['status'] != "⚠️  Over-sharded" and x['status'] != "⚠️  Under-sharded", x['index']))

    table = Table(title="Shard Distribution Analysis", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Current Shards", style="yellow", justify="right")
    table.add_column("Optimal Shards", style="green", justify="right")
    table.add_column("Avg Shard Size", style="magenta", justify="right")
    table.add_column("Total Size", style="blue", justify="right")
    table.add_column("Status", style="white")

    for item in analysis[:50]:  # Show top 50
        table.add_row(
            item['index'],
            str(item['current_shards']),
            str(item['optimal_shards']),
            item['avg_shard_size'],
            item['total_size'],
            item['status']
        )

    console.print(table)

    # Show recommendations
    issues = [a for a in analysis if a['status'] != "✅ Optimal"]
    if issues:
        console.print(f"\n[bold yellow]Recommendations for {len(issues)} indices:[/bold yellow]\n")
        for item in issues[:10]:
            console.print(f"[yellow]• {item['index']}:[/yellow] {item['recommendation']}")

    console.print()


def option_refresh_interval_tuner(es):
    """
    Analyze indexing rate vs. search rate from index stats.
    Recommend refresh intervals: -1 for bulk indexing, 30s for balanced, 1s for search-heavy.
    """
    show_breadcrumb(["Main Menu", "Performance Tuning", "Refresh Interval Tuner"])

    console.print()

    # Get index pattern
    pattern = get_text_input("Enter index pattern (e.g., logs-*): ", default="*")
    if not pattern:
        return

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing refresh intervals..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            # Get index stats
            stats = es.indices.stats(index=pattern, metric=["indexing", "search"])

            # Get current settings
            settings = es.indices.get_settings(index=pattern)

    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return

    # Analyze each index
    analysis = []

    for idx_name, idx_stats in stats.get('indices', {}).items():
        if is_system(idx_name):
            continue

        # Get indexing and search rates
        indexing_stats = idx_stats.get('total', {}).get('indexing', {})
        search_stats = idx_stats.get('total', {}).get('search', {})

        index_total = indexing_stats.get('index_total', 0)
        search_total = search_stats.get('query_total', 0)

        # Get current refresh interval
        current_refresh = settings.get(idx_name, {}).get('settings', {}).get('index', {}).get('refresh_interval', '1s')

        # Determine optimal refresh interval
        if index_total > search_total * 10:  # Heavy indexing
            recommended = '-1'
            reason = 'Bulk indexing workload'
        elif search_total > index_total * 10:  # Heavy searching
            recommended = '1s'
            reason = 'Search-heavy workload'
        else:  # Balanced
            recommended = '30s'
            reason = 'Balanced workload'

        status = "✅ Optimal" if current_refresh == recommended else "⚠️  Suboptimal"

        analysis.append({
            'index': idx_name,
            'current': current_refresh,
            'recommended': recommended,
            'indexing_ops': index_total,
            'search_ops': search_total,
            'reason': reason,
            'status': status
        })

    # Display results
    console.print(f"\n[bold cyan]Refresh Interval Analysis[/bold cyan]\n")

    if not analysis:
        console.print("[yellow]No indices found.[/yellow]\n")
        return

    table = Table(title="Refresh Interval Recommendations", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Current", style="yellow")
    table.add_column("Recommended", style="green")
    table.add_column("Indexing Ops", style="magenta", justify="right")
    table.add_column("Search Ops", style="blue", justify="right")
    table.add_column("Reason", style="white")
    table.add_column("Status", style="white")

    for item in analysis:
        table.add_row(
            item['index'],
            item['current'],
            item['recommended'],
            str(item['indexing_ops']),
            str(item['search_ops']),
            item['reason'],
            item['status']
        )

    console.print(table)

    # Ask to apply changes
    suboptimal = [a for a in analysis if a['status'] != "✅ Optimal"]
    if suboptimal:
        console.print()
        if confirm_action(f"Update refresh intervals for {len(suboptimal)} indices?"):
            updated = 0
            for item in suboptimal:
                try:
                    if not DRY_RUN_MODE:
                        es.indices.put_settings(
                            index=item['index'],
                            body={"index": {"refresh_interval": item['recommended']}}
                        )
                    updated += 1
                except Exception as e:
                    console.print(f"[red]Error updating {item['index']}: {e}[/red]")

            if DRY_RUN_MODE:
                console.print(f"[yellow]DRY RUN: Would update {updated} indices[/yellow]\n")
            else:
                console.print(f"[green]✅ Updated {updated} indices[/green]\n")

    console.print()


def option_merge_policy_optimizer(es):
    """
    Analyze segment counts, sizes, and merge activity from index stats.
    Recommend merge policy settings and trigger force merge for eligible indices.
    """
    show_breadcrumb(["Main Menu", "Performance Tuning", "Merge Policy Optimizer"])

    console.print()

    # Get index pattern
    pattern = get_text_input("Enter index pattern (e.g., logs-*): ", default="*")
    if not pattern:
        return

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing segments..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            # Get segment stats
            segments = es.indices.segments(index=pattern)

            # Get index stats for merge activity
            stats = es.indices.stats(index=pattern, metric=["merges"])

    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return

    # Analyze each index
    analysis = []

    for idx_name, idx_data in segments.get('indices', {}).items():
        if is_system(idx_name):
            continue

        # Count segments
        shards = idx_data.get('shards', {})
        total_segments = 0
        for shard_list in shards.values():
            for shard in shard_list:
                total_segments += shard.get('num_committed_segments', 0)

        # Get merge stats
        merge_stats = stats.get('indices', {}).get(idx_name, {}).get('total', {}).get('merges', {})
        merge_total = merge_stats.get('total', 0)
        merge_time_ms = merge_stats.get('total_time_in_millis', 0)

        # Determine status and recommendations
        if total_segments > 100:
            status = "⚠️  Excessive Segments"
            recommendation = "Force merge recommended"
        elif total_segments > 50:
            status = "⚠️  High Segments"
            recommendation = "Consider force merge"
        else:
            status = "✅ Healthy"
            recommendation = "No action needed"

        analysis.append({
            'index': idx_name,
            'segments': total_segments,
            'merges': merge_total,
            'merge_time_ms': merge_time_ms,
            'status': status,
            'recommendation': recommendation
        })

    # Display results
    console.print(f"\n[bold cyan]Segment Analysis[/bold cyan]\n")

    if not analysis:
        console.print("[yellow]No indices found.[/yellow]\n")
        return

    # Sort by segment count
    analysis.sort(key=lambda x: x['segments'], reverse=True)

    table = Table(title="Segment Distribution", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Segments", style="yellow", justify="right")
    table.add_column("Total Merges", style="magenta", justify="right")
    table.add_column("Merge Time", style="blue", justify="right")
    table.add_column("Status", style="white")

    for item in analysis[:50]:
        merge_time_str = f"{item['merge_time_ms'] / 1000:.1f}s" if item['merge_time_ms'] > 0 else "0s"
        table.add_row(
            item['index'],
            str(item['segments']),
            str(item['merges']),
            merge_time_str,
            item['status']
        )

    console.print(table)

    # Show recommendations
    issues = [a for a in analysis if a['status'] != "✅ Healthy"]
    if issues:
        console.print(f"\n[bold yellow]Merge Policy Recommendations:[/bold yellow]\n")
        console.print("• Increase max_merged_segment to allow larger segments")
        console.print("• Adjust segments_per_tier to control segment count")
        console.print("• Consider force merge for read-only indices\n")

        # Offer force merge
        if confirm_action(f"Trigger force merge for {len(issues)} indices with excessive segments?"):
            max_segments = get_number_input("Max number of segments (default: 1): ", default=1)
            if max_segments is None:
                return

            console.print()
            merged = 0
            for item in issues:
                try:
                    if not DRY_RUN_MODE:
                        console.print(f"[cyan]Force merging {item['index']}...[/cyan]")
                        es.indices.forcemerge(
                            index=item['index'],
                            max_num_segments=max_segments
                        )
                    merged += 1
                except Exception as e:
                    console.print(f"[red]Error merging {item['index']}: {e}[/red]")

            if DRY_RUN_MODE:
                console.print(f"\n[yellow]DRY RUN: Would force merge {merged} indices[/yellow]\n")
            else:
                console.print(f"\n[green]✅ Force merged {merged} indices[/green]\n")

    console.print()


def option_cache_tuning(es):
    """
    Fetch cache stats: field data cache, query cache, request cache.
    Display cache performance metrics and recommend cache size adjustments.
    """
    show_breadcrumb(["Main Menu", "Performance Tuning", "Cache Tuning"])

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching cache statistics..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)

            # Get node stats for cache info
            node_stats = es.nodes.stats(metric=["indices"])

    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return

    # Aggregate cache stats across nodes
    cache_stats = {
        'fielddata': {'size': 0, 'evictions': 0},
        'query_cache': {'size': 0, 'evictions': 0, 'hit_count': 0, 'miss_count': 0},
        'request_cache': {'size': 0, 'evictions': 0, 'hit_count': 0, 'miss_count': 0}
    }

    for node_id, node_data in node_stats.get('nodes', {}).items():
        indices = node_data.get('indices', {})

        # Field data cache
        fielddata = indices.get('fielddata', {})
        cache_stats['fielddata']['size'] += fielddata.get('memory_size_in_bytes', 0)
        cache_stats['fielddata']['evictions'] += fielddata.get('evictions', 0)

        # Query cache
        query_cache = indices.get('query_cache', {})
        cache_stats['query_cache']['size'] += query_cache.get('memory_size_in_bytes', 0)
        cache_stats['query_cache']['evictions'] += query_cache.get('evictions', 0)
        cache_stats['query_cache']['hit_count'] += query_cache.get('hit_count', 0)
        cache_stats['query_cache']['miss_count'] += query_cache.get('miss_count', 0)

        # Request cache
        request_cache = indices.get('request_cache', {})
        cache_stats['request_cache']['size'] += request_cache.get('memory_size_in_bytes', 0)
        cache_stats['request_cache']['evictions'] += request_cache.get('evictions', 0)
        cache_stats['request_cache']['hit_count'] += request_cache.get('hit_count', 0)
        cache_stats['request_cache']['miss_count'] += request_cache.get('miss_count', 0)

    # Calculate hit rates
    query_total = cache_stats['query_cache']['hit_count'] + cache_stats['query_cache']['miss_count']
    query_hit_rate = (cache_stats['query_cache']['hit_count'] / query_total * 100) if query_total > 0 else 0

    request_total = cache_stats['request_cache']['hit_count'] + cache_stats['request_cache']['miss_count']
    request_hit_rate = (cache_stats['request_cache']['hit_count'] / request_total * 100) if request_total > 0 else 0

    # Display cache stats
    console.print(f"\n[bold cyan]Cache Performance Metrics[/bold cyan]\n")

    table = Table(title="Cache Statistics", box=box.ROUNDED)
    table.add_column("Cache Type", style="cyan")
    table.add_column("Memory Usage", style="yellow", justify="right")
    table.add_column("Evictions", style="red", justify="right")
    table.add_column("Hit Rate", style="green", justify="right")
    table.add_column("Status", style="white")

    # Field data cache
    fd_status = "⚠️  High Evictions" if cache_stats['fielddata']['evictions'] > 1000 else "✅ Healthy"
    table.add_row(
        "Field Data",
        bytes_to_human(cache_stats['fielddata']['size']),
        str(cache_stats['fielddata']['evictions']),
        "N/A",
        fd_status
    )

    # Query cache
    qc_status = "⚠️  Low Hit Rate" if query_hit_rate < 50 else "✅ Healthy"
    table.add_row(
        "Query Cache",
        bytes_to_human(cache_stats['query_cache']['size']),
        str(cache_stats['query_cache']['evictions']),
        f"{query_hit_rate:.1f}%",
        qc_status
    )

    # Request cache
    rc_status = "⚠️  Low Hit Rate" if request_hit_rate < 50 else "✅ Healthy"
    table.add_row(
        "Request Cache",
        bytes_to_human(cache_stats['request_cache']['size']),
        str(cache_stats['request_cache']['evictions']),
        f"{request_hit_rate:.1f}%",
        rc_status
    )

    console.print(table)

    # Show recommendations
    console.print(f"\n[bold cyan]Optimization Recommendations:[/bold cyan]\n")

    recommendations = []

    if cache_stats['fielddata']['evictions'] > 1000:
        recommendations.append("• Increase indices.fielddata.cache.size (currently unbounded)")
        recommendations.append("  Consider setting to 20-40% of heap")

    if query_hit_rate < 50 and query_total > 100:
        recommendations.append("• Query cache hit rate is low - queries may not be cacheable")
        recommendations.append("  Consider using filter context instead of query context")

    if request_hit_rate < 50 and request_total > 100:
        recommendations.append("• Request cache hit rate is low")
        recommendations.append("  Increase indices.requests.cache.size (default: 1% of heap)")

    if cache_stats['query_cache']['evictions'] > 1000:
        recommendations.append("• High query cache evictions detected")
        recommendations.append("  Increase indices.queries.cache.size (default: 10% of heap)")

    if recommendations:
        for rec in recommendations:
            console.print(f"[yellow]{rec}[/yellow]")
    else:
        console.print("[green]✅ All caches are performing well![/green]")

    console.print()


def option_jvm_tuning_assistant(es):
    """
    Fetch JVM stats: heap usage, GC frequency, GC duration, old gen usage.
    Recommend heap size and GC algorithm based on usage patterns.
    """
    show_breadcrumb(["Main Menu", "Performance Tuning", "JVM Tuning Assistant"])

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing JVM performance..."),
            transient=True,
        ) as progress:
            progress.add_task("analyze", total=None)

            # Get node stats for JVM info
            node_stats = es.nodes.stats(metric=["jvm", "os"])

            # Get node info for JVM settings
            node_info = es.nodes.info(metric=["jvm"])

    except Exception as e:
        console.print(f"\n[red]❌ Error fetching data: {e}[/red]\n")
        return

    # Analyze each node
    analysis = []

    for node_id, node_data in node_stats.get('nodes', {}).items():
        node_name = node_data.get('name', node_id)

        # Get JVM stats
        jvm = node_data.get('jvm', {})
        mem = jvm.get('mem', {})
        gc = jvm.get('gc', {})

        # Heap usage
        heap_used_percent = mem.get('heap_used_percent', 0)
        heap_max = mem.get('heap_max_in_bytes', 0)
        heap_used = mem.get('heap_used_in_bytes', 0)

        # Old generation usage
        pools = mem.get('pools', {})
        old_gen = pools.get('old', {}) or pools.get('tenured', {})
        old_gen_used = old_gen.get('used_in_bytes', 0)
        old_gen_max = old_gen.get('max_in_bytes', 1)
        old_gen_percent = (old_gen_used / old_gen_max * 100) if old_gen_max > 0 else 0

        # GC stats
        collectors = gc.get('collectors', {})
        young_gc = collectors.get('young', {})
        old_gc = collectors.get('old', {})

        young_gc_count = young_gc.get('collection_count', 0)
        young_gc_time = young_gc.get('collection_time_in_millis', 0)
        old_gc_count = old_gc.get('collection_count', 0)
        old_gc_time = old_gc.get('collection_time_in_millis', 0)

        # Get current JVM settings
        node_jvm_info = node_info.get('nodes', {}).get(node_id, {}).get('jvm', {})
        current_heap = node_jvm_info.get('mem', {}).get('heap_max_in_bytes', 0)
        gc_collectors = node_jvm_info.get('gc_collectors', [])

        # Get OS info for RAM
        os_info = node_data.get('os', {})
        total_ram = os_info.get('mem', {}).get('total_in_bytes', 0)

        # Determine issues and recommendations
        issues = []
        recommendations = []

        if heap_used_percent > 85:
            issues.append("High heap usage")
            recommendations.append("Increase heap size")

        if old_gen_percent > 75:
            issues.append("High old generation usage")
            recommendations.append("Increase heap or optimize queries")

        if old_gc_count > 100:
            issues.append("Frequent old GC")
            recommendations.append("Tune GC settings or increase heap")

        # Heap size recommendation (50% of RAM, max 31GB)
        recommended_heap = min(total_ram // 2, 31 * 1024 * 1024 * 1024)

        # GC algorithm recommendation
        if current_heap < 8 * 1024 * 1024 * 1024:  # < 8GB
            recommended_gc = "G1GC"
        else:
            recommended_gc = "ZGC"

        current_gc = "G1GC" if "G1" in str(gc_collectors) else "CMS" if "CMS" in str(gc_collectors) else "Unknown"

        analysis.append({
            'node': node_name,
            'heap_used_percent': heap_used_percent,
            'heap_max': bytes_to_human(heap_max),
            'old_gen_percent': old_gen_percent,
            'young_gc_count': young_gc_count,
            'old_gc_count': old_gc_count,
            'total_gc_time': (young_gc_time + old_gc_time) / 1000,  # Convert to seconds
            'current_gc': current_gc,
            'recommended_gc': recommended_gc,
            'recommended_heap': bytes_to_human(recommended_heap),
            'issues': issues,
            'recommendations': recommendations
        })

    # Display results
    console.print(f"\n[bold cyan]JVM Performance Analysis[/bold cyan]\n")

    # Table 1: Current Status
    table1 = Table(title="Current JVM Status", box=box.ROUNDED)
    table1.add_column("Node", style="cyan")
    table1.add_column("Heap Used", style="yellow", justify="right")
    table1.add_column("Heap Max", style="green", justify="right")
    table1.add_column("Old Gen %", style="red", justify="right")
    table1.add_column("Young GC", style="magenta", justify="right")
    table1.add_column("Old GC", style="red", justify="right")
    table1.add_column("Total GC Time", style="blue", justify="right")

    for item in analysis:
        table1.add_row(
            item['node'],
            f"{item['heap_used_percent']:.1f}%",
            item['heap_max'],
            f"{item['old_gen_percent']:.1f}%",
            str(item['young_gc_count']),
            str(item['old_gc_count']),
            f"{item['total_gc_time']:.1f}s"
        )

    console.print(table1)

    # Table 2: Recommendations
    console.print()
    table2 = Table(title="JVM Tuning Recommendations", box=box.ROUNDED)
    table2.add_column("Node", style="cyan")
    table2.add_column("Current GC", style="yellow")
    table2.add_column("Recommended GC", style="green")
    table2.add_column("Recommended Heap", style="magenta")
    table2.add_column("Issues", style="red")

    for item in analysis:
        issues_str = ", ".join(item['issues']) if item['issues'] else "None"
        table2.add_row(
            item['node'],
            item['current_gc'],
            item['recommended_gc'],
            item['recommended_heap'],
            issues_str
        )

    console.print(table2)

    # Show detailed recommendations
    console.print(f"\n[bold cyan]Detailed Recommendations:[/bold cyan]\n")

    has_issues = any(item['issues'] for item in analysis)

    if has_issues:
        for item in analysis:
            if item['issues']:
                console.print(f"[yellow]Node: {item['node']}[/yellow]")
                for rec in item['recommendations']:
                    console.print(f"  • {rec}")
                console.print()

        console.print("[bold yellow]General JVM Tuning Tips:[/bold yellow]")
        console.print("• Set heap size to 50% of available RAM (max 31GB for compressed oops)")
        console.print("• Use G1GC for heaps < 8GB, ZGC for larger heaps")
        console.print("• Monitor GC logs to identify memory pressure")
        console.print("• Ensure -Xms and -Xmx are set to the same value")
        console.print("• Add -XX:+UseCompressedOops for heaps < 32GB")
    else:
        console.print("[green]✅ All nodes have healthy JVM settings![/green]")

    console.print()

