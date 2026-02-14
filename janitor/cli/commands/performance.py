"""
Performance monitoring and optimization commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info, warning
from ...utils.formatters import bytes_to_human


@click.group()
def perf():
    """Performance monitoring and optimization commands."""
    pass


@perf.command()
@click.option('--threshold', '-t', default=1000, help='Slow query threshold in milliseconds', type=int)
@click.option('--index', '-i', default='*', help='Index pattern to analyze')
@common_options
@handle_errors
@pass_es_client
def aggregations(es, threshold, index, output, verbose, quiet):
    """
    Analyze slow aggregation queries and provide optimization recommendations.
    
    This command analyzes query performance and provides specific recommendations
    for optimizing expensive aggregation queries based on field mappings and
    query patterns.
    
    Examples:
    
        # Analyze with default 1000ms threshold
        elastic-janitor perf aggregations
        
        # Custom threshold and pattern
        elastic-janitor perf aggregations --threshold 500 --index "logs-*"
        
        # JSON output
        elastic-janitor perf aggregations --output json
        
        # CSV output
        elastic-janitor perf aggregations --output csv
    """
    try:
        if not quiet:
            info(f"Analyzing aggregation performance (threshold: {threshold}ms)")
            info(f"Index pattern: {index}")
        
        # Get index statistics
        try:
            stats = es.indices.stats(index=index, metric="search")
        except Exception as e:
            error(f"Failed to fetch statistics: {e}")
            exit(1)
        
        indices_stats = stats.get("indices", {})
        
        if not indices_stats:
            error(f"No indices found matching pattern: {index}")
            exit(5)
        
        # Analyze query performance
        slow_queries = []
        
        for index_name, idx_stats in indices_stats.items():
            search_stats = idx_stats.get("total", {}).get("search", {})
            query_total = search_stats.get("query_total", 0)
            query_time_ms = search_stats.get("query_time_in_millis", 0)
            
            if query_total == 0:
                continue
            
            avg_time_ms = query_time_ms / query_total
            
            if avg_time_ms >= threshold:
                slow_queries.append({
                    "index": index_name,
                    "query_count": query_total,
                    "avg_time_ms": round(avg_time_ms, 2),
                    "total_time_ms": query_time_ms,
                    "issue": _identify_issue(avg_time_ms)
                })
        
        # Sort by average time
        slow_queries.sort(key=lambda x: x["avg_time_ms"], reverse=True)
        
        if not slow_queries:
            if not quiet:
                success(f"No slow queries found above {threshold}ms threshold")
            exit(0)
        
        # Generate recommendations
        recommendations = []
        
        for query in slow_queries[:10]:  # Top 10 slow queries
            index_name = query["index"]
            
            # Try to get mapping for recommendations
            try:
                mapping = es.indices.get_mapping(index=index_name)
                index_mapping = mapping.get(index_name, {}).get("mappings", {})
                properties = index_mapping.get("properties", {})
                
                # Check for optimization opportunities
                for field_name, field_config in properties.items():
                    field_type = field_config.get("type", "")
                    
                    if field_type == "keyword" and not field_config.get("eager_global_ordinals", False):
                        if query["avg_time_ms"] > 2000:
                            recommendations.append({
                                "index": index_name,
                                "field": field_name,
                                "current_perf": f"{query['avg_time_ms']:.0f}ms",
                                "issue": "Keyword field without eager global ordinals",
                                "recommendation": "Enable eager_global_ordinals",
                                "improvement": "30-50%"
                            })
            except:
                # If mapping fetch fails, add general recommendation
                recommendations.append({
                    "index": index_name,
                    "field": "N/A",
                    "current_perf": f"{query['avg_time_ms']:.0f}ms",
                    "issue": "Slow aggregation queries",
                    "recommendation": "Use composite aggregations",
                    "improvement": "40-70%"
                })
        
        # Add general best practices
        if slow_queries:
            recommendations.extend([
                {
                    "index": "General",
                    "field": "Terms Aggregation",
                    "current_perf": "Varies",
                    "issue": "High cardinality",
                    "recommendation": "Use composite aggregation with pagination",
                    "improvement": "50-80%"
                },
                {
                    "index": "General",
                    "field": "Date Histogram",
                    "current_perf": "Varies",
                    "issue": "Fine-grained intervals",
                    "recommendation": "Increase interval or use auto_date_histogram",
                    "improvement": "30-60%"
                }
            ])
        
        # Output results
        if output == OutputFormat.JSON:
            result = {
                "slow_queries": slow_queries,
                "recommendations": recommendations[:10]
            }
            format_output([result], output)
        elif output == OutputFormat.CSV:
            format_output(recommendations[:10], output)
        elif output == OutputFormat.TABLE:
            if not quiet:
                success(f"Found {len(slow_queries)} slow queries:")
                for query in slow_queries[:5]:
                    info(f"\n{query['index']}:")
                    info(f"  Avg time: {query['avg_time_ms']:.2f}ms")
                    info(f"  Query count: {query['query_count']:,}")
                    info(f"  Issue: {query['issue']}")
                
                info(f"\nTop Recommendations:")
                for i, rec in enumerate(recommendations[:5], 1):
                    info(f"\n{i}. {rec['index']} - {rec['field']}")
                    info(f"   Issue: {rec['issue']}")
                    info(f"   Recommendation: {rec['recommendation']}")
                    info(f"   Potential improvement: {rec['improvement']}")
        
    except Exception as e:
        error(f"Aggregation analysis failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)


def _identify_issue(avg_time_ms):
    """Identify the likely issue causing slow queries."""
    if avg_time_ms > 5000:
        return "Very slow - likely aggregation issue"
    elif avg_time_ms > 2000:
        return "Slow - check aggregations"
    elif avg_time_ms > 1000:
        return "Moderate - optimize if frequent"
    else:
        return "Acceptable performance"

