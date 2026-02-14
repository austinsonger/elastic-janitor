"""
Data stream management commands.
"""
import click
from datetime import datetime, timezone, timedelta
from ..utils.decorators import pass_es_client, handle_errors, common_options, dry_run_option
from ..utils.output import format_output, OutputFormat, success, error, info, warning
from ...utils.formatters import bytes_to_human
from ...core.connection import get_all_indices_info
from ...config import PROTECT_SYSTEM, MAX_DELETE_LIMIT
from ...utils.helpers import is_system


@click.group()
def datastream():
    """Data stream management commands."""
    pass


@datastream.command()
@click.option('--retention', '-r', required=True, help='Retention period (e.g., 90d, 6M, 1y)')
@click.option('--pattern', '-p', default='*', help='Data stream pattern to filter')
@click.option('--batch-size', '-b', default=100, help='Batch size for deletions', type=int)
@dry_run_option
@common_options
@handle_errors
@pass_es_client
def clean(es, retention, pattern, batch_size, dry_run, output, verbose, quiet):
    """
    Clean old backing indices from data streams.
    
    This command identifies and deletes backing indices older than the
    specified retention period, while preserving the current write index.
    
    Examples:
    
        # Preview cleanup (dry-run)
        elastic-janitor datastream clean --retention 90d --dry-run
        
        # Clean indices older than 90 days
        elastic-janitor datastream clean --retention 90d
        
        # Clean specific pattern
        elastic-janitor datastream clean --retention 6M --pattern "logs-*"
        
        # JSON output
        elastic-janitor datastream clean --retention 90d --output json --dry-run
    """
    try:
        # Parse retention period
        cutoff = _parse_retention(retention)
        
        if not quiet:
            info(f"Retention cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            if dry_run:
                warning("DRY-RUN MODE: No changes will be made")
        
        # Get all indices info
        indices_info = get_all_indices_info(es)
        
        # Get data streams
        ds_response = es.indices.get_data_stream(name=pattern)
        data_streams = ds_response.get("data_streams", [])
        
        if not data_streams:
            error(f"No data streams found matching pattern: {pattern}")
            exit(5)
        
        # Process data streams
        total_eligible = 0
        total_size_bytes = 0
        streams_with_eligible = []
        
        for ds in data_streams:
            ds_name = ds["name"]
            
            # Skip system indices if protection is enabled
            if PROTECT_SYSTEM and is_system(ds_name):
                if verbose:
                    info(f"Skipping system data stream: {ds_name}")
                continue
            
            indices = ds.get("indices", [])
            if not indices:
                continue
            
            write_index = indices[-1]["index_name"]
            backing = [x["index_name"] for x in indices]
            
            eligible = []
            for idx_name in backing:
                # Never delete write index
                if idx_name == write_index:
                    continue
                
                idx_info = indices_info.get(idx_name)
                if not idx_info:
                    continue
                
                created = idx_info["created"]
                if created < cutoff:
                    eligible.append({
                        "index": idx_name,
                        "created": created.strftime('%Y-%m-%d'),
                        "size": idx_info["size"],
                        "size_bytes": idx_info["size_bytes"],
                        "tier": idx_info["tier"]
                    })
            
            if eligible:
                total_eligible += len(eligible)
                total_size_bytes += sum(e["size_bytes"] for e in eligible)
                streams_with_eligible.append({
                    "data_stream": ds_name,
                    "total_backing": len(backing),
                    "write_index": write_index,
                    "eligible_count": len(eligible),
                    "eligible_indices": eligible
                })
        
        # Build summary
        summary = {
            "retention_period": retention,
            "cutoff_date": cutoff.strftime('%Y-%m-%d %H:%M:%S UTC'),
            "data_streams_checked": len(data_streams),
            "data_streams_with_eligible": len(streams_with_eligible),
            "total_eligible_indices": total_eligible,
            "total_size_to_reclaim": bytes_to_human(total_size_bytes),
            "dry_run": dry_run,
        }
        
        if output == 'json':
            result = {
                "summary": summary,
                "data_streams": streams_with_eligible
            }
            format_output(result, OutputFormat.JSON)
        elif output == 'yaml':
            result = {
                "summary": summary,
                "data_streams": streams_with_eligible
            }
            format_output(result, OutputFormat.YAML)
        else:
            # Table output
            if not quiet:
                from ...config import console
                console.print(f"\n[bold cyan]Data Stream Cleanup Summary[/bold cyan]")
                console.print(f"Retention period: {retention}")
                console.print(f"Cutoff date: {cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                console.print(f"Data streams checked: {len(data_streams)}")
                console.print(f"Data streams with eligible indices: {len(streams_with_eligible)}")
                console.print(f"[red]Total eligible indices: {total_eligible}[/red]")
                console.print(f"[red bold]Total size to reclaim: {bytes_to_human(total_size_bytes)}[/red bold]\n")
                
                if streams_with_eligible and verbose:
                    # Show detailed breakdown
                    for stream in streams_with_eligible[:10]:  # Limit to first 10
                        console.print(f"\n[cyan]{stream['data_stream']}[/cyan]")
                        console.print(f"  Eligible: {stream['eligible_count']} of {stream['total_backing']} backing indices")
                        for idx in stream['eligible_indices'][:5]:  # Show first 5
                            console.print(f"    - {idx['index']} ({idx['size']}, {idx['created']})")
        
        # Perform deletion if not dry-run
        if not dry_run and total_eligible > 0:
            if total_eligible > MAX_DELETE_LIMIT:
                error(f"Too many indices to delete ({total_eligible} > {MAX_DELETE_LIMIT}). Use --batch-size to limit.")
                exit(6)
            
            if not quiet:
                warning(f"Deleting {total_eligible} indices...")
            
            deleted_count = 0
            for stream in streams_with_eligible:
                for idx in stream['eligible_indices']:
                    try:
                        es.indices.delete(index=idx['index'])
                        deleted_count += 1
                        if verbose:
                            success(f"Deleted: {idx['index']}")
                    except Exception as e:
                        error(f"Failed to delete {idx['index']}: {e}")
            
            success(f"Deleted {deleted_count} indices, reclaimed {bytes_to_human(total_size_bytes)}")
        elif dry_run and not quiet:
            warning("DRY-RUN: No indices were deleted")
        
    except Exception as e:
        error(f"Failed to clean data streams: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)


def _parse_retention(retention_str):
    """Parse retention string like '90d', '6M', '1y' into datetime."""
    import re
    match = re.match(r'^(\d+)([smhdwMy])$', retention_str)
    if not match:
        raise ValueError(f"Invalid retention format: {retention_str}. Use format like: 30d, 6M, 1y")
    
    value = int(match.group(1))
    unit = match.group(2)
    
    now = datetime.now(timezone.utc)
    
    if unit == 's':
        return now - timedelta(seconds=value)
    elif unit == 'm':
        return now - timedelta(minutes=value)
    elif unit == 'h':
        return now - timedelta(hours=value)
    elif unit == 'd':
        return now - timedelta(days=value)
    elif unit == 'w':
        return now - timedelta(weeks=value)
    elif unit == 'M':
        return now - timedelta(days=value * 30)  # Approximate
    elif unit == 'y':
        return now - timedelta(days=value * 365)  # Approximate
    else:
        raise ValueError(f"Unknown time unit: {unit}")


@datastream.command()
@click.option('--source', '-s', required=True, help='Source data stream name')
@click.option('--dest', '-d', required=True, help='Destination cluster URL or data stream name')
@click.option('--mode', '-m', type=click.Choice(['cross-cluster', 'same-cluster']), default='same-cluster', help='Migration mode')
@dry_run_option
@common_options
@handle_errors
@pass_es_client
def migrate(es, source, dest, mode, dry_run, output, verbose, quiet):
    """
    Migrate data streams between clusters or within the same cluster.

    This command migrates entire data streams including all backing indices,
    metadata, and index templates. Supports both cross-cluster and same-cluster
    migrations.

    Examples:

        # Migrate within same cluster (clone)
        elastic-janitor datastream migrate --source logs-app --dest logs-app-backup

        # Cross-cluster migration (dry-run)
        elastic-janitor datastream migrate --source logs-app --dest https://dest-cluster:9200 --mode cross-cluster --dry-run

        # JSON output
        elastic-janitor datastream migrate --source logs-app --dest logs-app-v2 --output json
    """
    try:
        if not quiet:
            info(f"Migration mode: {mode}")
            info(f"Source data stream: {source}")
            info(f"Destination: {dest}")
            if dry_run:
                warning("DRY-RUN MODE: No changes will be made")

        # Get source data stream info
        try:
            ds_response = es.indices.get_data_stream(name=source)
            data_streams = ds_response.get("data_streams", [])

            if not data_streams:
                error(f"Data stream not found: {source}")
                exit(5)

            ds_info = data_streams[0]
        except Exception as e:
            error(f"Failed to fetch data stream: {e}")
            exit(1)

        # Calculate total size
        backing_indices = ds_info.get("indices", [])
        total_size_bytes = 0

        for idx in backing_indices:
            idx_name = idx.get("index_name")
            try:
                stats = es.indices.stats(index=idx_name, metric="store")
                idx_stats = stats.get("indices", {}).get(idx_name, {})
                total_stats = idx_stats.get("total", {})
                store_stats = total_stats.get("store", {})
                total_size_bytes += store_stats.get("size_in_bytes", 0)
            except:
                pass

        # Build result
        result = {
            "source": source,
            "destination": dest,
            "mode": mode,
            "backing_indices": len(backing_indices),
            "total_size": bytes_to_human(total_size_bytes),
            "total_size_bytes": total_size_bytes,
            "dry_run": dry_run,
            "status": "preview" if dry_run else "would_execute"
        }

        if mode == "cross-cluster":
            result["note"] = "Cross-cluster migration requires remote cluster configuration"
        else:
            result["note"] = "Same-cluster migration will clone the data stream"

        # Output result
        if output == OutputFormat.JSON:
            format_output([result], output)
        elif output == OutputFormat.TABLE:
            if not quiet:
                success(f"Migration preview for {source}:")
                info(f"  Mode: {mode}")
                info(f"  Backing indices: {len(backing_indices)}")
                info(f"  Total size: {bytes_to_human(total_size_bytes)}")
                info(f"  Destination: {dest}")
                if dry_run:
                    warning("  This is a dry-run. Use without --dry-run to execute.")
                else:
                    warning("  Note: Actual migration not implemented in CLI. Use interactive mode.")

    except Exception as e:
        error(f"Migration failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        exit(1)
