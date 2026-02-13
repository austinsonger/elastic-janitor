"""
Cluster health and diagnostics commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...utils.formatters import bytes_to_human


@click.group()
def cluster():
    """Cluster health and diagnostics commands."""
    pass


@cluster.command()
@common_options
@handle_errors
@pass_es_client
def health(es, output, verbose, quiet):
    """
    Display cluster health overview.
    
    Examples:
    
        # Basic health check
        elastic-janitor cluster health
        
        # JSON output for scripting
        elastic-janitor cluster health --output json
        
        # Verbose output
        elastic-janitor cluster health --verbose
    """
    try:
        # Get cluster health
        health_data = es.cluster.health()
        
        # Get cluster stats for additional info
        stats = es.cluster.stats()
        
        # Build output data
        data = {
            "cluster_name": health_data.get("cluster_name", "unknown"),
            "status": health_data.get("status", "unknown").upper(),
            "nodes": health_data.get("number_of_nodes", 0),
            "data_nodes": health_data.get("number_of_data_nodes", 0),
            "active_shards": health_data.get("active_shards", 0),
            "active_primary_shards": health_data.get("active_primary_shards", 0),
            "relocating_shards": health_data.get("relocating_shards", 0),
            "initializing_shards": health_data.get("initializing_shards", 0),
            "unassigned_shards": health_data.get("unassigned_shards", 0),
            "delayed_unassigned_shards": health_data.get("delayed_unassigned_shards", 0),
            "pending_tasks": health_data.get("number_of_pending_tasks", 0),
            "in_flight_fetch": health_data.get("number_of_in_flight_fetch", 0),
            "task_max_waiting_time": health_data.get("task_max_waiting_in_queue_millis", 0),
            "active_shards_percent": f"{health_data.get('active_shards_percent_as_number', 0):.1f}%"
        }
        
        # Add stats if verbose
        if verbose:
            indices_stats = stats.get("indices", {})
            data.update({
                "total_indices": indices_stats.get("count", 0),
                "total_shards": indices_stats.get("shards", {}).get("total", 0),
                "total_docs": indices_stats.get("docs", {}).get("count", 0),
                "total_size": bytes_to_human(indices_stats.get("store", {}).get("size_in_bytes", 0)),
            })
        
        # Format output
        if output == 'json':
            format_output(data, OutputFormat.JSON)
        elif output == 'yaml':
            format_output(data, OutputFormat.YAML)
        elif output == 'csv':
            format_output([data], OutputFormat.CSV)
        else:
            # Table output with color coding
            status = health_data.get("status", "unknown").lower()
            status_emoji = {
                "green": "🟢",
                "yellow": "🟡",
                "red": "🔴"
            }.get(status, "⚪")
            
            if not quiet:
                info(f"Cluster: {data['cluster_name']}")
                
                status_color = {
                    "green": "green",
                    "yellow": "yellow",
                    "red": "red"
                }.get(status, "white")
                
                from ...config import console
                console.print(f"\n{status_emoji} Status: [{status_color}]{data['status']}[/{status_color}]")
                console.print(f"Nodes: {data['nodes']} ({data['data_nodes']} data nodes)")
                console.print(f"Shards: {data['active_shards']} active ({data['active_primary_shards']} primary)")
                
                if data['unassigned_shards'] > 0:
                    console.print(f"[yellow]⚠ Unassigned shards: {data['unassigned_shards']}[/yellow]")
                
                if data['relocating_shards'] > 0:
                    console.print(f"[cyan]ℹ Relocating shards: {data['relocating_shards']}[/cyan]")
                
                if data['initializing_shards'] > 0:
                    console.print(f"[cyan]ℹ Initializing shards: {data['initializing_shards']}[/cyan]")
                
                console.print(f"Active shards: {data['active_shards_percent']}")
                
                if verbose:
                    console.print(f"\nIndices: {data['total_indices']}")
                    console.print(f"Documents: {data['total_docs']:,}")
                    console.print(f"Total size: {data['total_size']}")
                
                console.print()
        
        # Exit with appropriate code based on status
        if health_data.get("status") == "red":
            exit(7)  # Operation failed
        elif health_data.get("status") == "yellow":
            exit(0)  # Success but with warnings
        else:
            exit(0)  # Success
            
    except Exception as e:
        error(f"Failed to get cluster health: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)


@cluster.command()
@common_options
@handle_errors
@pass_es_client
def nodes(es, output, verbose, quiet):
    """
    Display node information.
    
    Examples:
    
        # List all nodes
        elastic-janitor cluster nodes
        
        # JSON output
        elastic-janitor cluster nodes --output json
    """
    try:
        # Get node stats
        nodes_info = es.nodes.info()
        nodes_stats = es.nodes.stats()
        
        nodes_data = []
        
        for node_id, node in nodes_info.get("nodes", {}).items():
            stats = nodes_stats.get("nodes", {}).get(node_id, {})
            
            node_data = {
                "name": node.get("name", "unknown"),
                "role": ",".join(node.get("roles", [])),
                "ip": node.get("ip", "unknown"),
                "version": node.get("version", "unknown"),
            }
            
            if verbose:
                jvm = stats.get("jvm", {})
                os = stats.get("os", {})
                node_data.update({
                    "heap_used": bytes_to_human(jvm.get("mem", {}).get("heap_used_in_bytes", 0)),
                    "heap_max": bytes_to_human(jvm.get("mem", {}).get("heap_max_in_bytes", 0)),
                    "cpu_percent": os.get("cpu", {}).get("percent", 0),
                })
            
            nodes_data.append(node_data)
        
        # Format output
        format_output(nodes_data, OutputFormat[output.upper()], title="Cluster Nodes")
        
    except Exception as e:
        error(f"Failed to get node information: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)


@cluster.command()
@common_options
@handle_errors
@pass_es_client
def stats(es, output, verbose, quiet):
    """
    Display cluster statistics.
    
    Examples:
    
        # Show cluster stats
        elastic-janitor cluster stats
        
        # JSON output
        elastic-janitor cluster stats --output json
    """
    try:
        stats_data = es.cluster.stats()
        
        indices = stats_data.get("indices", {})
        nodes = stats_data.get("nodes", {})
        
        data = {
            "cluster_name": stats_data.get("cluster_name", "unknown"),
            "indices_count": indices.get("count", 0),
            "shards_total": indices.get("shards", {}).get("total", 0),
            "docs_count": indices.get("docs", {}).get("count", 0),
            "docs_deleted": indices.get("docs", {}).get("deleted", 0),
            "store_size": bytes_to_human(indices.get("store", {}).get("size_in_bytes", 0)),
            "nodes_count": nodes.get("count", {}).get("total", 0),
        }
        
        if verbose:
            data.update({
                "segments_count": indices.get("segments", {}).get("count", 0),
                "segments_memory": bytes_to_human(indices.get("segments", {}).get("memory_in_bytes", 0)),
                "fielddata_memory": bytes_to_human(indices.get("fielddata", {}).get("memory_size_in_bytes", 0)),
                "query_cache_memory": bytes_to_human(indices.get("query_cache", {}).get("memory_size_in_bytes", 0)),
            })
        
        # Format output
        format_output(data, OutputFormat[output.upper()], title="Cluster Statistics")
        
    except Exception as e:
        error(f"Failed to get cluster statistics: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)

