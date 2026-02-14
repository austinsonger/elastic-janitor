"""
Index management commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...utils.formatters import bytes_to_human
from ...core.connection import get_all_indices_info


@click.group()
def index():
    """Index management commands."""
    pass


@index.command()
@click.option('--top', '-n', default=25, help='Number of indices to show', type=int)
@click.option('--pattern', '-p', default='*', help='Index pattern to filter')
@common_options
@handle_errors
@pass_es_client
def largest(es, top, pattern, output, verbose, quiet):
    """
    List largest indices by size.
    
    Examples:
    
        # Show top 25 largest indices
        elastic-janitor index largest
        
        # Show top 50
        elastic-janitor index largest --top 50
        
        # Filter by pattern
        elastic-janitor index largest --pattern "logs-*"
        
        # JSON output
        elastic-janitor index largest --output json
    """
    try:
        if not quiet:
            info(f"Fetching index information for pattern: {pattern}")
        
        # Get all indices info
        indices_info = get_all_indices_info(es)
        
        # Filter by pattern if specified
        if pattern != '*':
            import fnmatch
            indices_info = {
                name: info for name, info in indices_info.items()
                if fnmatch.fnmatch(name, pattern)
            }
        
        if not indices_info:
            error(f"No indices found matching pattern: {pattern}")
            exit(5)
        
        # Sort by size
        sorted_indices = sorted(
            indices_info.items(),
            key=lambda x: x[1]['size_bytes'],
            reverse=True
        )[:top]
        
        # Build output data
        indices_data = []
        for idx_name, idx_info in sorted_indices:
            data = {
                "index": idx_name,
                "size": idx_info['size'],
                "primary_size": idx_info['pri_size'],
                "tier": idx_info['tier'],
            }
            
            if verbose:
                data.update({
                    "created": idx_info['created'].strftime('%Y-%m-%d %H:%M:%S'),
                    "size_bytes": idx_info['size_bytes'],
                })
            
            indices_data.append(data)
        
        # Format output
        if output == 'json':
            format_output({"indices": indices_data, "total": len(indices_data)}, OutputFormat.JSON)
        elif output == 'yaml':
            format_output({"indices": indices_data, "total": len(indices_data)}, OutputFormat.YAML)
        elif output == 'csv':
            format_output(indices_data, OutputFormat.CSV)
        else:
            format_output(indices_data, OutputFormat.TABLE, title=f"Top {top} Largest Indices")
            if not quiet:
                success(f"Found {len(indices_data)} indices")
        
    except Exception as e:
        error(f"Failed to list indices: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)


@index.command()
@click.option('--pattern', '-p', default='*', help='Index pattern to check')
@click.option('--status', '-s', multiple=True, help='Filter by status (green, yellow, red)')
@common_options
@handle_errors
@pass_es_client
def health(es, pattern, status, output, verbose, quiet):
    """
    Display index health status.
    
    Examples:
    
        # Check all indices
        elastic-janitor index health
        
        # Check specific pattern
        elastic-janitor index health --pattern "logs-*"
        
        # Show only yellow and red indices
        elastic-janitor index health --status yellow --status red
    """
    try:
        if not quiet:
            info(f"Checking health for pattern: {pattern}")
        
        # Get index health
        health_data = es.cat.indices(
            index=pattern,
            format='json',
            h='index,health,status,pri,rep,docs.count,store.size'
        )
        
        # Filter by status if specified
        if status:
            status_set = set(s.lower() for s in status)
            health_data = [idx for idx in health_data if idx.get('health', '').lower() in status_set]
        
        if not health_data:
            if status:
                info(f"No indices found with status: {', '.join(status)}")
            else:
                error(f"No indices found matching pattern: {pattern}")
            exit(0)
        
        # Build output data
        indices_data = []
        for idx in health_data:
            data = {
                "index": idx.get('index', ''),
                "health": idx.get('health', 'unknown').upper(),
                "status": idx.get('status', 'unknown'),
                "primaries": idx.get('pri', '0'),
                "replicas": idx.get('rep', '0'),
                "docs": idx.get('docs.count', '0'),
                "size": idx.get('store.size', '0b'),
            }
            indices_data.append(data)
        
        # Format output
        format_output(indices_data, OutputFormat[output.upper()], title="Index Health")
        
        if not quiet:
            # Count by health status
            green = sum(1 for idx in indices_data if idx['health'] == 'GREEN')
            yellow = sum(1 for idx in indices_data if idx['health'] == 'YELLOW')
            red = sum(1 for idx in indices_data if idx['health'] == 'RED')
            
            from ...config import console
            console.print(f"\n[green]Green: {green}[/green] | [yellow]Yellow: {yellow}[/yellow] | [red]Red: {red}[/red]\n")
        
    except Exception as e:
        error(f"Failed to check index health: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)


@index.command(name='analyze-patterns')
@click.option('--days', '-d', default=7, help='Number of days to analyze', type=int)
@click.option('--pattern', '-p', default='*', help='Index pattern to filter')
@common_options
@handle_errors
@pass_es_client
def analyze_patterns(es, days, pattern, output, verbose, quiet):
    """
    Analyze query workload and recommend optimal index patterns.

    This command analyzes your index patterns and query workload to recommend
    optimal time-based partitioning, routing strategies, and shard configurations.

    Examples:

        # Analyze patterns over last 7 days
        elastic-janitor index analyze-patterns

        # Analyze specific pattern over 30 days
        elastic-janitor index analyze-patterns --days 30 --pattern "logs-*"

        # JSON output
        elastic-janitor index analyze-patterns --output json
    """
    try:
        if not quiet:
            info(f"Analyzing index patterns over last {days} days")
            info(f"Pattern filter: {pattern}")

        # Get index statistics
        try:
            stats = es.indices.stats(metric="search,store")
            indices_info_raw = es.cat.indices(format="json", h="index,creation.date,docs.count,store.size")
        except Exception as e:
            error(f"Failed to fetch statistics: {e}")
            exit(1)

        # Filter indices by pattern
        import fnmatch
        from collections import defaultdict
        import re

        indices_info = [idx for idx in indices_info_raw if fnmatch.fnmatch(idx.get("index", ""), pattern)]

        if not indices_info:
            error(f"No indices found matching pattern: {pattern}")
            exit(5)

        # Analyze patterns
        pattern_groups = defaultdict(list)
        indices_stats = stats.get("indices", {})

        for idx_info in indices_info:
            index_name = idx_info.get("index", "")

            # Skip system indices
            if index_name.startswith("."):
                continue

            # Detect pattern
            detected_pattern = re.sub(r'\d{4}\.\d{2}\.\d{2}', 'YYYY.MM.DD', index_name)
            detected_pattern = re.sub(r'\d{4}-\d{2}-\d{2}', 'YYYY-MM-DD', detected_pattern)
            detected_pattern = re.sub(r'\d{4}\.\d{2}', 'YYYY.MM', detected_pattern)
            detected_pattern = re.sub(r'\d{4}-\d{2}', 'YYYY-MM', detected_pattern)
            detected_pattern = re.sub(r'-\d{6}$', '-NNNNNN', detected_pattern)

            pattern_groups[detected_pattern].append({
                "name": index_name,
                "docs": int(idx_info.get("docs.count", 0) or 0),
                "size": idx_info.get("store.size", "0b")
            })

        # Build analysis results
        analysis_results = []

        for detected_pattern, indices in pattern_groups.items():
            if len(indices) < 2:
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
            issues = []
            if len(indices) > 365:
                issues.append("Over-partitioned")
            elif len(indices) > 100:
                issues.append("Many indices")
            if avg_response_time > 1000:
                issues.append("Slow queries")

            analysis_results.append({
                "pattern": detected_pattern,
                "index_count": len(indices),
                "total_queries": total_queries,
                "avg_response_time_ms": round(avg_response_time, 2),
                "issues": ", ".join(issues) if issues else "None"
            })

        # Sort by query count
        analysis_results.sort(key=lambda x: x["total_queries"], reverse=True)

        if not analysis_results:
            if not quiet:
                info("No patterns found with multiple indices")
            exit(0)

        # Output results
        if output == OutputFormat.JSON:
            format_output(analysis_results, output)
        elif output == OutputFormat.TABLE:
            if not quiet:
                success(f"Found {len(analysis_results)} index patterns:")
                for result in analysis_results[:10]:  # Show top 10
                    info(f"\nPattern: {result['pattern']}")
                    info(f"  Indices: {result['index_count']}")
                    info(f"  Queries: {result['total_queries']:,}")
                    info(f"  Avg Response: {result['avg_response_time_ms']:.2f}ms")
                    info(f"  Issues: {result['issues']}")

    except Exception as e:
        error(f"Pattern analysis failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)
