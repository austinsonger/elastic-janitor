"""
AWS Ingestion Diagnostics & Management for Elastic Janitor.
Troubleshoot and manage logs ingested via AWS Firehose and Elastic Serverless Forwarder.
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
import questionary
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
from ..config import (
    console, GOD_MODE, DEFAULT_QUERY_TIMEOUT,
    SLOW_QUERY_TIMEOUT, REQUEST_TIMEOUT, REINDEX_TIMEOUT
)
from ..utils import (
    show_breadcrumb, safe_input, confirm_action, get_number_input,
    get_text_input, is_system, get_index_pattern_selection, select_from_list,
    paginate_table, paginate_renderables
)
from ..utils.formatters import bytes_to_human


def option_firehose_forwarder_health_check(es):
    """
    Check health of AWS Firehose and Elastic Serverless Forwarder ingestion.
    
    Detects indices/data streams receiving data from AWS sources and shows
    last ingestion timestamps and stale streams.
    """
    show_breadcrumb(["Main Menu", "AWS Ingestion Management", "Firehose/Forwarder Health Check"])
    
    console.print("\n[bold cyan]🔥 AWS Firehose/Forwarder Health Check[/bold cyan]\n")
    console.print("[dim]Detecting AWS-sourced data streams and checking ingestion health...[/dim]\n")
    
    # Get index pattern
    index_pattern = get_index_pattern_selection(es)
    
    if not index_pattern:
        return
    
    # Get staleness threshold
    staleness_minutes = get_number_input(
        "Flag streams with no data in last X minutes:",
        default=30,
        min_val=1
    )
    
    if staleness_minutes is None:
        return
    
    try:
        # Get matching indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index,docs.count")
        
        indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if is_system(index_name):
                continue
            doc_count = int(idx.get("docs.count", "0") or 0)
            if doc_count > 0:
                indices.append({"name": index_name, "doc_count": doc_count})
        
        if not indices:
            console.print("\n[yellow]🟡 No matching indices found.[/yellow]\n")
            return
        
        console.print(f"\n[cyan]Analyzing {len(indices)} indices for AWS ingestion...[/cyan]\n")
        
        # Analyze each index for AWS sources
        aws_sources = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=staleness_minutes)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Analyzing indices...", total=len(indices))
            
            for idx_info in indices:
                index_name = idx_info["name"]
                progress.update(task, description=f"[cyan]Analyzing: {index_name[:50]}...")
                
                try:
                    # Check for Firehose data
                    firehose_query = {
                        "query": {
                            "exists": {"field": "aws.firehose"}
                        },
                        "size": 1,
                        "sort": [{"@timestamp": {"order": "desc"}}]
                    }
                    
                    firehose_result = es.search(index=index_name, body=firehose_query)
                    firehose_count = firehose_result["hits"]["total"]["value"]
                    
                    # Check for Serverless Forwarder data
                    forwarder_query = {
                        "query": {
                            "bool": {
                                "should": [
                                    {"exists": {"field": "aws.lambda"}},
                                    {"term": {"tags": "elastic-serverless-forwarder"}}
                                ]
                            }
                        },
                        "size": 1,
                        "sort": [{"@timestamp": {"order": "desc"}}]
                    }
                    
                    forwarder_result = es.search(index=index_name, body=forwarder_query)
                    forwarder_count = forwarder_result["hits"]["total"]["value"]
                    
                    # Get last ingestion timestamp
                    last_doc_query = {
                        "query": {"match_all": {}},
                        "size": 1,
                        "sort": [{"@timestamp": {"order": "desc"}}]
                    }
                    
                    last_doc_result = es.search(index=index_name, body=last_doc_query)
                    
                    if last_doc_result["hits"]["hits"]:
                        last_timestamp_str = last_doc_result["hits"]["hits"][0]["_source"].get("@timestamp")
                        if last_timestamp_str:
                            last_timestamp = datetime.fromisoformat(last_timestamp_str.replace('Z', '+00:00'))
                            is_stale = last_timestamp < cutoff_time
                        else:
                            last_timestamp = None
                            is_stale = True
                    else:
                        last_timestamp = None
                        is_stale = True

                    # Store results if AWS source detected
                    if firehose_count > 0 or forwarder_count > 0:
                        source_type = []
                        if firehose_count > 0:
                            source_type.append("Firehose")
                        if forwarder_count > 0:
                            source_type.append("Serverless Forwarder")

                        aws_sources.append({
                            "index": index_name,
                            "source_type": ", ".join(source_type),
                            "firehose_docs": firehose_count,
                            "forwarder_docs": forwarder_count,
                            "total_docs": idx_info["doc_count"],
                            "last_timestamp": last_timestamp,
                            "is_stale": is_stale
                        })

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not analyze {index_name}: {e}[/yellow]")

                progress.advance(task)

        if not aws_sources:
            console.print("\n[yellow]🟡 No AWS-sourced data streams found.[/yellow]\n")
            return

        # Display results
        console.print(f"\n[green]✅ Found {len(aws_sources)} AWS-sourced data streams[/green]\n")

        # Create health table
        health_table = Table(
            title="AWS Ingestion Health Status",
            box=box.ROUNDED,
            title_style="bold cyan"
        )

        health_table.add_column("Index/Data Stream", style="cyan", no_wrap=False)
        health_table.add_column("Source Type", style="yellow")
        health_table.add_column("AWS Docs", style="white", justify="right")
        health_table.add_column("Total Docs", style="white", justify="right")
        health_table.add_column("Last Ingestion", style="white")
        health_table.add_column("Status", style="bold")

        stale_count = 0
        for source in aws_sources:
            # Format last timestamp
            if source["last_timestamp"]:
                time_ago = datetime.now(timezone.utc) - source["last_timestamp"]
                if time_ago.total_seconds() < 60:
                    last_ingestion = f"{int(time_ago.total_seconds())}s ago"
                elif time_ago.total_seconds() < 3600:
                    last_ingestion = f"{int(time_ago.total_seconds() / 60)}m ago"
                elif time_ago.total_seconds() < 86400:
                    last_ingestion = f"{int(time_ago.total_seconds() / 3600)}h ago"
                else:
                    last_ingestion = f"{int(time_ago.total_seconds() / 86400)}d ago"
            else:
                last_ingestion = "Unknown"

            # Status
            if source["is_stale"]:
                status = "[red]⚠️  STALE[/red]"
                stale_count += 1
            else:
                status = "[green]✅ Active[/green]"

            aws_docs = source["firehose_docs"] + source["forwarder_docs"]

            health_table.add_row(
                source["index"],
                source["source_type"],
                f"{aws_docs:,}",
                f"{source['total_docs']:,}",
                last_ingestion,
                status
            )

        console.print(health_table)
        console.print()

        # Summary
        if stale_count > 0:
            console.print(Panel(
                f"[bold red]⚠️  WARNING: {stale_count} stale stream(s) detected![/bold red]\n\n"
                f"These streams have not received data in the last {staleness_minutes} minutes.\n"
                f"Check your AWS Firehose/Lambda configuration and network connectivity.",
                title="[bold red]Stale Streams Alert[/bold red]",
                box=box.ROUNDED,
                border_style="red"
            ))
        else:
            console.print(Panel(
                f"[bold green]✅ All AWS ingestion streams are active[/bold green]\n\n"
                f"All {len(aws_sources)} stream(s) have received data within the last {staleness_minutes} minutes.",
                title="[bold green]Health Check Passed[/bold green]",
                box=box.ROUNDED,
                border_style="green"
            ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not perform health check: {e}[/red]\n")


def option_common_issue_detection(es):
    """
    Detect common AWS ingestion issues.

    - Find logs with ingest_pipeline_failed tag
    - Detect CloudWatch wrapper parsing issues
    - Identify logs stuck in message arrays
    - Find logs with missing log.original
    - Detect nested JSON parsing failures
    - Identify duplicate data (both aws.cloudwatch.message and message)
    """
    show_breadcrumb(["Main Menu", "AWS Ingestion Management", "Common Issue Detection"])

    console.print("\n[bold cyan]🔍 AWS Ingestion Common Issue Detection[/bold cyan]\n")
    console.print("[dim]Scanning for common AWS ingestion problems...[/dim]\n")

    # Get index pattern
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Ask about timeout for slow queries
    use_fast_mode = confirm_action(
        "Use fast mode? (Skips slow wildcard queries like nested JSON check)"
    )

    if use_fast_mode:
        console.print("[yellow]ℹ️  Fast mode enabled - nested JSON check will be skipped[/yellow]\n")

    try:
        # Get matching indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching indices..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(index=index_pattern, format="json", h="index,docs.count")

        indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if is_system(index_name):
                continue
            doc_count = int(idx.get("docs.count", "0") or 0)
            if doc_count > 0:
                indices.append(index_name)

        if not indices:
            console.print("\n[yellow]🟡 No matching indices found.[/yellow]\n")
            return

        console.print(f"\n[cyan]Scanning {len(indices)} indices for common issues...[/cyan]\n")

        # Define issue queries
        issues = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Detecting issues...", total=12)

            # Issue 1: Pipeline failures
            progress.update(task, description="[cyan]Checking for pipeline failures...")
            try:
                pipeline_failed_query = {
                    "query": {"term": {"tags": "ingest_pipeline_failed"}},
                    "size": 0
                }
                result = es.search(index=index_pattern, body=pipeline_failed_query)
                failed_count = result["hits"]["total"]["value"]
                if failed_count > 0:
                    issues.append({
                        "type": "Pipeline Failures",
                        "severity": "High",
                        "count": failed_count,
                        "description": "Documents with 'ingest_pipeline_failed' tag",
                        "impact": "Data not properly parsed or enriched"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check pipeline failures: {e}[/yellow]")
            progress.advance(task)

            # Issue 2: CloudWatch wrapper parsing issues
            progress.update(task, description="[cyan]Checking CloudWatch parsing...")
            try:
                cw_wrapper_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "aws.cloudwatch.message"}},
                                {"wildcard": {"aws.cloudwatch.message": "*{*"}}
                            ],
                            "must_not": [
                                {"exists": {"field": "message"}}
                            ]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=cw_wrapper_query)
                wrapper_count = result["hits"]["total"]["value"]
                if wrapper_count > 0:
                    issues.append({
                        "type": "CloudWatch Wrapper Issues",
                        "severity": "Medium",
                        "count": wrapper_count,
                        "description": "JSON in aws.cloudwatch.message not extracted to message field",
                        "impact": "Nested JSON not properly parsed"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check CloudWatch parsing: {e}[/yellow]")
            progress.advance(task)

            # Issue 3: Message arrays (Firehose format issues)
            progress.update(task, description="[cyan]Checking for message arrays...")
            try:
                message_array_query = {
                    "query": {
                        "script": {
                            "script": "doc['message.keyword'].size() > 1"
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=message_array_query)
                array_count = result["hits"]["total"]["value"]
                if array_count > 0:
                    issues.append({
                        "type": "Message Arrays",
                        "severity": "Medium",
                        "count": array_count,
                        "description": "Documents with message field as array instead of string",
                        "impact": "Logs stuck in array format, not searchable"
                    })
            except Exception:
                # Script queries might not be enabled, skip silently
                pass
            progress.advance(task)

            # Issue 4: Missing log.original
            progress.update(task, description="[cyan]Checking for missing log.original...")
            try:
                missing_original_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "aws.cloudwatch"}}
                            ],
                            "must_not": [
                                {"exists": {"field": "log.original"}}
                            ]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=missing_original_query)
                missing_count = result["hits"]["total"]["value"]
                if missing_count > 0:
                    issues.append({
                        "type": "Missing log.original",
                        "severity": "Low",
                        "count": missing_count,
                        "description": "CloudWatch logs without log.original fallback field",
                        "impact": "Cannot recover original message if parsing fails"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check log.original: {e}[/yellow]")
            progress.advance(task)

            # Issue 5: Nested JSON parsing failures
            progress.update(task, description="[cyan]Checking for nested JSON issues...")
            if use_fast_mode:
                console.print(f"[dim]⏭️  Skipping nested JSON check (fast mode enabled)[/dim]")
            else:
                try:
                    # Use a more efficient sampling approach instead of wildcard queries
                    # Sample recent documents and check for nested JSON patterns
                    sample_query = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"exists": {"field": "message"}},
                                    {"exists": {"field": "aws"}}
                                ]
                            }
                        },
                        "size": 1000,  # Sample 1000 recent documents
                        "sort": [{"@timestamp": {"order": "desc"}}],
                        "_source": ["message"],
                        "timeout": f"{DEFAULT_QUERY_TIMEOUT}s"
                    }

                    sample_result = es.search(
                        index=index_pattern,
                        body=sample_query,
                        request_timeout=REQUEST_TIMEOUT
                    )

                    # Analyze samples for nested JSON patterns
                    nested_count = 0
                    sample_docs = sample_result["hits"]["hits"]

                    for doc in sample_docs:
                        message = doc.get("_source", {}).get("message", "")
                        if isinstance(message, str):
                            # Check for common nested JSON patterns
                            if ("msg.msg" in message or
                                "{\\\"msg\\\"" in message or
                                "\\\"message\\\":\\\"" in message):
                                nested_count += 1

                    # Extrapolate to total if we found issues in sample
                    if nested_count > 0:
                        total_docs = sample_result["hits"]["total"]["value"]
                        sample_size = len(sample_docs)

                        if sample_size > 0:
                            # Estimate total nested JSON documents
                            estimated_total = int((nested_count / sample_size) * total_docs)

                            issues.append({
                                "type": "Nested JSON Parsing",
                                "severity": "Medium",
                                "count": estimated_total,
                                "description": f"Estimated {estimated_total:,} documents with nested JSON (sampled {nested_count}/{sample_size})",
                                "impact": "Nested JSON not properly flattened"
                            })

                    # Check if query timed out
                    if sample_result.get("timed_out", False):
                        console.print(f"[yellow]⚠️  Nested JSON check timed out - results may be incomplete[/yellow]")

                except Exception as e:
                    console.print(f"[yellow]⚠️  Could not check nested JSON: {e}[/yellow]")
            progress.advance(task)

            # Issue 6: Duplicate data
            progress.update(task, description="[cyan]Checking for duplicate fields...")
            try:
                duplicate_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "aws.cloudwatch.message"}},
                                {"exists": {"field": "message"}}
                            ]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=duplicate_query)
                duplicate_count = result["hits"]["total"]["value"]
                if duplicate_count > 0:
                    issues.append({
                        "type": "Duplicate Data",
                        "severity": "Low",
                        "count": duplicate_count,
                        "description": "Documents with both aws.cloudwatch.message and message fields",
                        "impact": "Wasted storage, potential confusion"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check duplicates: {e}[/yellow]")
            progress.advance(task)

            # Issue 7: Missing @timestamp
            progress.update(task, description="[cyan]Checking for missing @timestamp...")
            try:
                missing_timestamp_query = {
                    "query": {
                        "bool": {
                            "must": [{"exists": {"field": "aws"}}],
                            "must_not": [{"exists": {"field": "@timestamp"}}]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=missing_timestamp_query)
                missing_ts_count = result["hits"]["total"]["value"]
                if missing_ts_count > 0:
                    issues.append({
                        "type": "Missing @timestamp",
                        "severity": "High",
                        "count": missing_ts_count,
                        "description": "Documents without @timestamp field",
                        "impact": "Cannot be queried by time, breaks time-series functionality"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check @timestamp: {e}[/yellow]")
            progress.advance(task)

            # Issue 8: Base64 Encoded Messages
            progress.update(task, description="[cyan]Checking for base64 encoded messages...")
            try:
                # Sample approach for base64 detection (regex can be slow)
                base64_sample_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "message"}},
                                {"exists": {"field": "aws"}}
                            ]
                        }
                    },
                    "size": 500,
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "_source": ["message"],
                    "timeout": f"{DEFAULT_QUERY_TIMEOUT}s"
                }

                sample_result = es.search(
                    index=index_pattern,
                    body=base64_sample_query,
                    request_timeout=REQUEST_TIMEOUT
                )

                # Check samples for base64 pattern
                import re
                base64_pattern = re.compile(r'^[A-Za-z0-9+/]{50,}={0,2}$')
                base64_count = 0
                sample_docs = sample_result["hits"]["hits"]

                for doc in sample_docs:
                    message = doc.get("_source", {}).get("message", "")
                    if isinstance(message, str) and base64_pattern.match(message.strip()):
                        base64_count += 1

                # Extrapolate if found
                if base64_count > 0:
                    total_docs = sample_result["hits"]["total"]["value"]
                    sample_size = len(sample_docs)
                    if sample_size > 0:
                        estimated_total = int((base64_count / sample_size) * total_docs)
                        issues.append({
                            "type": "Base64 Encoded Messages",
                            "severity": "Medium",
                            "count": estimated_total,
                            "description": f"Estimated {estimated_total:,} messages with base64 encoding (sampled {base64_count}/{sample_size})",
                            "impact": "Data not readable, needs decoding"
                        })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check base64 encoding: {e}[/yellow]")
            progress.advance(task)

            # Issue 9: Missing AWS Metadata
            progress.update(task, description="[cyan]Checking for missing AWS metadata...")
            try:
                missing_metadata_query = {
                    "query": {
                        "bool": {
                            "must": [{"exists": {"field": "aws"}}],
                            "must_not": [{"exists": {"field": "aws.cloudwatch.log_group"}}]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=missing_metadata_query)
                missing_meta_count = result["hits"]["total"]["value"]
                if missing_meta_count > 0:
                    issues.append({
                        "type": "Missing AWS Metadata",
                        "severity": "Medium",
                        "count": missing_meta_count,
                        "description": "CloudWatch logs missing log_group or log_stream metadata",
                        "impact": "Cannot filter by log source, troubleshooting difficult"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check AWS metadata: {e}[/yellow]")
            progress.advance(task)

            # Issue 10: Ingestion Lag
            progress.update(task, description="[cyan]Checking for ingestion lag...")
            try:
                # Sample recent documents to check lag
                lag_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "event.ingested"}},
                                {"exists": {"field": "@timestamp"}}
                            ]
                        }
                    },
                    "size": 100,
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "_source": ["@timestamp", "event.ingested"]
                }
                result = es.search(index=index_pattern, body=lag_query)

                lagged_count = 0
                for doc in result["hits"]["hits"]:
                    timestamp = doc["_source"].get("@timestamp")
                    ingested = doc["_source"].get("event.ingested")
                    if timestamp and ingested:
                        from datetime import datetime
                        try:
                            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            ing = datetime.fromisoformat(ingested.replace('Z', '+00:00'))
                            lag_seconds = (ing - ts).total_seconds()
                            if lag_seconds > 300:  # 5 minutes lag
                                lagged_count += 1
                        except:
                            pass

                # If more than 10% of sample has lag
                if lagged_count > 10:
                    issues.append({
                        "type": "Ingestion Lag",
                        "severity": "High",
                        "count": lagged_count,
                        "description": f"Significant delay between log generation and indexing (>5 min) in {lagged_count}% of sampled docs",
                        "impact": "Real-time monitoring delayed, alerts may be late"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check ingestion lag: {e}[/yellow]")
            progress.advance(task)

            # Issue 11: Duplicate Documents
            progress.update(task, description="[cyan]Checking for duplicate documents...")
            try:
                # Use aggregation to find potential duplicates
                # Sample approach: check for docs with same message and timestamp
                duplicate_agg_query = {
                    "size": 0,
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "message.keyword"}},
                                {"exists": {"field": "@timestamp"}}
                            ]
                        }
                    },
                    "aggs": {
                        "duplicate_check": {
                            "composite": {
                                "size": 100,
                                "sources": [
                                    {"message_hash": {"terms": {"field": "message.keyword"}}},
                                    {"timestamp": {"terms": {"field": "@timestamp"}}}
                                ]
                            },
                            "aggs": {
                                "duplicate_count": {
                                    "value_count": {"field": "_id"}
                                }
                            }
                        }
                    }
                }
                result = es.search(index=index_pattern, body=duplicate_agg_query, request_timeout=SLOW_QUERY_TIMEOUT)
                duplicate_buckets = result.get("aggregations", {}).get("duplicate_check", {}).get("buckets", [])

                # Count buckets with more than 1 document
                total_duplicates = sum(bucket["doc_count"] - 1 for bucket in duplicate_buckets if bucket["doc_count"] > 1)

                if total_duplicates > 0:
                    issues.append({
                        "type": "Duplicate Documents",
                        "severity": "Medium",
                        "count": total_duplicates,
                        "description": f"Found {total_duplicates:,} duplicate documents (same message + timestamp)",
                        "impact": "Wasted storage, skewed metrics and counts"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check duplicates: {e}[/yellow]")
            progress.advance(task)

            # Issue 12: CloudWatch Extracted Fields Enabled
            progress.update(task, description="[cyan]Checking for extracted fields...")
            try:
                extracted_fields_query = {
                    "query": {"exists": {"field": "extracted_fields"}},
                    "size": 0
                }
                result = es.search(index=index_pattern, body=extracted_fields_query)
                extracted_count = result["hits"]["total"]["value"]
                if extracted_count > 0:
                    issues.append({
                        "type": "CloudWatch Extracted Fields",
                        "severity": "Low",
                        "count": extracted_count,
                        "description": "Documents with extracted_fields (should be disabled)",
                        "impact": "Wasted storage, duplicate data"
                    })
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not check extracted fields: {e}[/yellow]")
            progress.advance(task)

        if not issues:
            console.print("\n[green]✅ No common issues detected![/green]\n")
            console.print(Panel(
                "[bold green]All checks passed[/bold green]\n\n"
                "No common AWS ingestion issues were found in the selected indices.",
                title="[bold green]Issue Detection Complete[/bold green]",
                box=box.ROUNDED,
                border_style="green"
            ))
            console.print()
            return

        # Create issues table
        console.print(f"\n[yellow]⚠️  Found {len(issues)} issue type(s)[/yellow]\n")

        issues_table = Table(
            title="Common AWS Ingestion Issues",
            box=box.ROUNDED,
            title_style="bold yellow"
        )

        issues_table.add_column("Issue Type", style="cyan", no_wrap=False)
        issues_table.add_column("Severity", style="bold")
        issues_table.add_column("Affected Docs", style="white", justify="right")
        issues_table.add_column("Description", style="white", no_wrap=False)
        issues_table.add_column("Impact", style="dim", no_wrap=False)

        for issue in sorted(issues, key=lambda x: {"High": 0, "Medium": 1, "Low": 2}[x["severity"]]):
            severity_color = {
                "High": "red",
                "Medium": "yellow",
                "Low": "blue"
            }[issue["severity"]]

            issues_table.add_row(
                issue["type"],
                f"[{severity_color}]{issue['severity']}[/{severity_color}]",
                f"{issue['count']:,}",
                issue["description"],
                issue["impact"]
            )

        console.print(issues_table)
        console.print()

        # Summary panel with actionable recommendations
        high_severity = sum(1 for i in issues if i["severity"] == "High")
        medium_severity = sum(1 for i in issues if i["severity"] == "Medium")
        total_affected = sum(i["count"] for i in issues)

        # Determine which specific issues were found
        has_pipeline_failures = any(i["type"] == "Pipeline Failures" for i in issues)
        has_missing_log_original = any(i["type"] == "Missing log.original" for i in issues)
        has_nested_json = any(i["type"] == "Nested JSON Parsing" for i in issues)
        has_missing_timestamp = any(i["type"] == "Missing @timestamp" for i in issues)
        has_base64_encoded = any(i["type"] == "Base64 Encoded Messages" for i in issues)
        has_missing_metadata = any(i["type"] == "Missing AWS Metadata" for i in issues)
        has_ingestion_lag = any(i["type"] == "Ingestion Lag" for i in issues)
        has_duplicates = any(i["type"] == "Duplicate Documents" for i in issues)
        has_extracted_fields = any(i["type"] == "CloudWatch Extracted Fields" for i in issues)

        if high_severity > 0:
            # Build specific action recommendations based on detected issues
            actions = []

            if has_pipeline_failures:
                actions.append(
                    "[bold cyan]For Pipeline Failures:[/bold cyan]\n"
                    "  1. Go to: [yellow]Pipeline Troubleshooting[/yellow] → View failing processors\n"
                    "  2. Go to: [yellow]Template & Policy Management → Edit Pipeline[/yellow] → Fix processors\n"
                    "  3. Go to: [yellow]Quick Fixes & Actions → 🔄 Bulk Reindex Failed Documents[/yellow] → Reprocess"
                )

            if has_missing_log_original:
                actions.append(
                    "[bold cyan]For Missing log.original:[/bold cyan]\n"
                    "  1. Go to: [yellow]Template & Policy Management → Edit Pipeline[/yellow]\n"
                    "  2. Add 'set' processor to copy message to log.original\n"
                    "  3. See: [yellow]example_pipeline_with_log_original.json[/yellow] for reference\n"
                    "  4. Go to: [yellow]Quick Fixes & Actions → 🔄 Bulk Reindex[/yellow] → Reprocess existing docs"
                )

            if has_nested_json:
                actions.append(
                    "[bold cyan]For Nested JSON Issues:[/bold cyan]\n"
                    "  1. Go to: [yellow]Quick Fixes & Actions → Export Failed Logs[/yellow] → Examine structure\n"
                    "  2. Add JSON processor with 'target_field' to flatten nested structures\n"
                    "  3. Go to: [yellow]Quick Fixes & Actions → 🔄 Bulk Reindex[/yellow] → Reprocess"
                )

            if has_missing_timestamp:
                actions.append(
                    "[bold cyan]For Missing @timestamp:[/bold cyan]\n"
                    "  1. Go to: [yellow]Template & Policy Management → Edit Pipeline[/yellow]\n"
                    "  2. Add date processor with fallback to event.ingested\n"
                    "  3. [red]Critical:[/red] Fix immediately as time-series queries will fail\n"
                    "  4. Go to: [yellow]Quick Fixes & Actions → 🔄 Bulk Reindex[/yellow] → Reprocess"
                )

            if has_ingestion_lag:
                actions.append(
                    "[bold cyan]For Ingestion Lag:[/bold cyan]\n"
                    "  1. Check Firehose buffer settings (reduce interval from 300s to 60s)\n"
                    "  2. Go to: [yellow]Cluster Health & Monitoring[/yellow] → Check resource usage\n"
                    "  3. Monitor CloudWatch metrics for throttling\n"
                    "  4. Consider scaling cluster if CPU/memory is high"
                )

            action_text = "\n\n".join(actions) if actions else (
                "• Review pipeline configurations\n"
                "• Check CloudWatch field extraction settings\n"
                "• Use Pipeline Troubleshooting to identify specific processor failures"
            )

            console.print(Panel(
                f"[bold red]⚠️  {high_severity} HIGH SEVERITY issue(s) detected![/bold red]\n\n"
                f"Total affected documents: {total_affected:,}\n\n"
                f"[bold white]📋 Step-by-Step Fix Guide:[/bold white]\n\n"
                f"{action_text}\n\n"
                f"[dim]💡 Tip: See AWS_INGESTION_FIXES_GUIDE.md for detailed instructions[/dim]",
                title="[bold red]Action Required[/bold red]",
                box=box.ROUNDED,
                border_style="red"
            ))
        else:
            # Build recommendations for medium/low severity issues
            medium_actions = []

            if has_duplicates:
                medium_actions.append(
                    "[bold cyan]For Duplicate Documents:[/bold cyan]\n"
                    "  1. Go to: [yellow]Template & Policy Management → Edit Pipeline[/yellow]\n"
                    "  2. Add fingerprint processor to generate unique document IDs\n"
                    "  3. Use message + @timestamp for fingerprint source"
                )

            if has_base64_encoded:
                medium_actions.append(
                    "[bold cyan]For Base64 Encoded Messages:[/bold cyan]\n"
                    "  1. Go to: [yellow]Template & Policy Management → Edit Pipeline[/yellow]\n"
                    "  2. Add decode processor before other processors\n"
                    "  3. Set ignore_failure: true to handle non-base64 messages"
                )

            if has_missing_metadata:
                medium_actions.append(
                    "[bold cyan]For Missing AWS Metadata:[/bold cyan]\n"
                    "  1. Check Firehose/ESF configuration\n"
                    "  2. Ensure metadata inclusion is enabled\n"
                    "  3. Verify CloudWatch log subscription filter settings"
                )

            if has_extracted_fields:
                medium_actions.append(
                    "[bold cyan]For CloudWatch Extracted Fields:[/bold cyan]\n"
                    "  1. Update Firehose configuration\n"
                    "  2. Set include_cw_extracted_fields: false\n"
                    "  3. Redeploy Firehose delivery stream"
                )

            medium_text = "\n\n".join(medium_actions) if medium_actions else (
                "These are low to medium severity issues that may impact data quality."
            )

            console.print(Panel(
                f"[bold yellow]Found {len(issues)} issue type(s)[/bold yellow]\n\n"
                f"Total affected documents: {total_affected:,}\n\n"
                f"{medium_text}\n\n"
                f"[dim]💡 Tip: See AWS_FIREHOSE_ESF_ALL_ISSUES.md for complete issue catalog[/dim]",
                title="[bold yellow]Issues Detected[/bold yellow]",
                box=box.ROUNDED,
                border_style="yellow"
            ))
        console.print()

        # Offer quick actions
        if (has_pipeline_failures or has_missing_log_original or has_missing_timestamp or
            has_ingestion_lag or has_duplicates or has_base64_encoded or has_missing_metadata):
            console.print("[bold cyan]What would you like to do next?[/bold cyan]\n")

            action_choices = []

            if has_pipeline_failures:
                action_choices.append(
                    questionary.Choice("🔍 View Pipeline Troubleshooting (identify failing processors)", value="pipeline_troubleshooting")
                )
                action_choices.append(
                    questionary.Choice("🔄 Go to Bulk Reindex (fix failed documents)", value="bulk_reindex")
                )

            if (has_missing_log_original or has_pipeline_failures or has_missing_timestamp or
                has_duplicates or has_base64_encoded):
                action_choices.append(
                    questionary.Choice("✏️  Edit Pipeline Configuration", value="edit_pipeline")
                )

            if has_ingestion_lag:
                action_choices.append(
                    questionary.Choice("📊 Check Cluster Health & Performance", value="cluster_health")
                )

            if has_missing_metadata:
                action_choices.append(
                    questionary.Choice("⚙️  View Firehose/ESF Configuration Guide", value="config_guide")
                )

            action_choices.extend([
                questionary.Choice("📤 Export Failed Logs for Analysis", value="export_logs"),
                questionary.Separator(),
                questionary.Choice("📖 View Complete Fix Guide (AWS_INGESTION_FIXES_GUIDE.md)", value="view_guide"),
                questionary.Choice("← Return to AWS Ingestion Menu", value="back")
            ])

            try:
                next_action = questionary.select(
                    "Select action:",
                    choices=action_choices
                ).ask()

                if next_action == "pipeline_troubleshooting":
                    console.print("\n[cyan]→ Navigating to Pipeline Troubleshooting...[/cyan]\n")
                    option_pipeline_troubleshooting(es)

                elif next_action == "bulk_reindex":
                    console.print("\n[cyan]→ Navigating to Bulk Reindex...[/cyan]\n")
                    _bulk_reindex_failed_documents(es)

                elif next_action == "edit_pipeline":
                    console.print("\n[yellow]ℹ️  To edit pipelines:[/yellow]")
                    console.print("   Go to: [cyan]Main Menu → Template & Policy Management → Edit Pipeline[/cyan]\n")

                elif next_action == "export_logs":
                    console.print("\n[cyan]→ Navigating to Export Failed Logs...[/cyan]\n")
                    # This will be handled by the Quick Fixes menu
                    console.print("[yellow]ℹ️  To export logs:[/yellow]")
                    console.print("   Go to: [cyan]Quick Fixes & Actions → Export Failed Logs to File[/cyan]\n")

                elif next_action == "cluster_health":
                    console.print("\n[yellow]ℹ️  To check cluster health:[/yellow]")
                    console.print("   Go to: [cyan]Main Menu → Cluster Health & Monitoring[/cyan]")
                    console.print("   Check: CPU usage, memory pressure, indexing rate, search latency\n")

                elif next_action == "config_guide":
                    console.print("\n[cyan]📖 Opening Configuration Guide...[/cyan]\n")
                    try:
                        import os
                        guide_path = os.path.join(os.path.dirname(__file__), "..", "..", "AWS_FIREHOSE_ESF_ALL_ISSUES.md")
                        if os.path.exists(guide_path):
                            console.print(Panel(
                                "[bold white]AWS Firehose/ESF Configuration Tips:[/bold white]\n\n"
                                "1. [cyan]Enable Metadata Inclusion:[/cyan]\n"
                                "   - Firehose: Set ProcessingConfiguration.Enabled = true\n"
                                "   - ESF: Configure metadata enrichment in Lambda\n\n"
                                "2. [cyan]Disable Extracted Fields:[/cyan]\n"
                                "   - Set include_cw_extracted_fields: false\n\n"
                                "3. [cyan]Optimize Buffer Settings:[/cyan]\n"
                                "   - Buffer size: 1-5 MB\n"
                                "   - Buffer interval: 60-300 seconds\n\n"
                                f"[dim]Full guide: {guide_path}[/dim]",
                                title="[bold cyan]Configuration Guide[/bold cyan]",
                                border_style="cyan"
                            ))
                        else:
                            console.print("[yellow]Guide file not found. See AWS_FIREHOSE_ESF_ALL_ISSUES.md in project root.[/yellow]\n")
                    except Exception as e:
                        console.print(f"[yellow]Could not open guide: {e}[/yellow]\n")

                elif next_action == "view_guide":
                    console.print("\n[cyan]📖 Opening Fix Guide...[/cyan]\n")
                    try:
                        import os
                        guide_path = os.path.join(os.path.dirname(__file__), "..", "..", "AWS_INGESTION_FIXES_GUIDE.md")
                        if os.path.exists(guide_path):
                            with open(guide_path, 'r') as f:
                                guide_content = f.read()
                            console.print(Panel(
                                guide_content[:2000] + "\n\n[dim]... (file continues)[/dim]",
                                title="[bold cyan]AWS Ingestion Fixes Guide (Preview)[/bold cyan]",
                                border_style="cyan"
                            ))
                            console.print(f"\n[green]Full guide available at: {guide_path}[/green]\n")
                        else:
                            console.print("[yellow]Guide file not found. See AWS_INGESTION_FIXES_GUIDE.md in project root.[/yellow]\n")
                    except Exception as e:
                        console.print(f"[yellow]Could not open guide: {e}[/yellow]\n")

            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not detect issues: {e}[/red]\n")


def option_field_structure_analysis(es):
    """
    Validate AWS metadata structure.

    - Check aws.cloudwatch.log_group, log_stream, aws.firehose.arn
    - Verify include_cw_extracted_fields: false is respected
    - Check for missing Kubernetes metadata
    - Validate @timestamp parsing
    """
    show_breadcrumb(["Main Menu", "AWS Ingestion Management", "Field Structure Analysis"])

    console.print("\n[bold cyan]📊 AWS Field Structure Analysis[/bold cyan]\n")
    console.print("[dim]Validating AWS metadata field structures...[/dim]\n")

    # Get index pattern
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    try:
        console.print(f"\n[cyan]Analyzing field structures in {index_pattern}...[/cyan]\n")

        # Get index status information to filter out closed/frozen/partial indices
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching index information..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(
                index=index_pattern,
                format="json",
                h="index,status,docs.count,dt"  # dt = data tier
            )

        # Filter indices - skip closed, frozen, and partial indices
        queryable_indices = []
        skipped_indices = []

        for idx in indices_response:
            index_name = idx.get("index")
            status = idx.get("status", "").lower()
            tier = idx.get("dt", "").lower()
            doc_count = int(idx.get("docs.count", "0") or 0)

            # Skip system indices
            if is_system(index_name):
                continue

            # Skip closed indices
            if status == "close":
                skipped_indices.append((index_name, "closed"))
                continue

            # Skip frozen tier indices (searchable snapshots with limited query capabilities)
            if tier == "frozen":
                skipped_indices.append((index_name, "frozen tier"))
                continue

            # Skip partial indices (searchable snapshots)
            # Partial indices have "partial-" prefix or are in frozen tier
            if index_name.startswith("partial-") or "partial" in index_name.lower():
                skipped_indices.append((index_name, "partial/searchable snapshot"))
                continue

            # Only include indices with documents
            if doc_count > 0:
                queryable_indices.append(index_name)

        if not queryable_indices:
            console.print("\n[yellow]🟡 No queryable indices found matching pattern.[/yellow]")
            if skipped_indices:
                console.print(f"\n[dim]Skipped {len(skipped_indices)} indices:[/dim]")
                for idx_name, reason in skipped_indices[:10]:
                    console.print(f"  [dim]• {idx_name} ({reason})[/dim]")
                if len(skipped_indices) > 10:
                    console.print(f"  [dim]... and {len(skipped_indices) - 10} more[/dim]")
            console.print()
            return

        # Build query pattern for queryable indices only
        queryable_pattern = ",".join(queryable_indices)

        console.print(f"[cyan]Analyzing {len(queryable_indices)} queryable indices...[/cyan]")
        if skipped_indices:
            console.print(f"[dim]Skipped {len(skipped_indices)} indices (closed/frozen/partial)[/dim]\n")
        else:
            console.print()

        validation_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Validating fields...", total=5)

            # Check 1: CloudWatch metadata completeness
            progress.update(task, description="[cyan]Checking CloudWatch metadata...")
            try:
                # Docs with aws.cloudwatch but missing log_group
                missing_log_group_query = {
                    "query": {
                        "bool": {
                            "must": [{"exists": {"field": "aws.cloudwatch"}}],
                            "must_not": [{"exists": {"field": "aws.cloudwatch.log_group"}}]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=queryable_pattern, body=missing_log_group_query)
                missing_log_group = result["hits"]["total"]["value"]

                # Docs with aws.cloudwatch but missing log_stream
                missing_log_stream_query = {
                    "query": {
                        "bool": {
                            "must": [{"exists": {"field": "aws.cloudwatch"}}],
                            "must_not": [{"exists": {"field": "aws.cloudwatch.log_stream"}}]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=queryable_pattern, body=missing_log_stream_query)
                missing_log_stream = result["hits"]["total"]["value"]

                if missing_log_group > 0 or missing_log_stream > 0:
                    validation_results.append({
                        "check": "CloudWatch Metadata",
                        "status": "Warning",
                        "details": f"Missing log_group: {missing_log_group:,}, Missing log_stream: {missing_log_stream:,}",
                        "recommendation": "Ensure CloudWatch logs include complete metadata"
                    })
                else:
                    validation_results.append({
                        "check": "CloudWatch Metadata",
                        "status": "Pass",
                        "details": "All CloudWatch logs have complete metadata",
                        "recommendation": "N/A"
                    })
            except Exception as e:
                validation_results.append({
                    "check": "CloudWatch Metadata",
                    "status": "Error",
                    "details": str(e),
                    "recommendation": "Check index mappings"
                })
            progress.advance(task)

            # Check 2: Firehose ARN presence
            progress.update(task, description="[cyan]Checking Firehose metadata...")
            try:
                firehose_no_arn_query = {
                    "query": {
                        "bool": {
                            "must": [{"exists": {"field": "aws.firehose"}}],
                            "must_not": [{"exists": {"field": "aws.firehose.arn"}}]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=queryable_pattern, body=firehose_no_arn_query)
                missing_arn = result["hits"]["total"]["value"]

                if missing_arn > 0:
                    validation_results.append({
                        "check": "Firehose ARN",
                        "status": "Warning",
                        "details": f"{missing_arn:,} Firehose documents missing ARN",
                        "recommendation": "Verify Firehose configuration includes ARN metadata"
                    })
                else:
                    validation_results.append({
                        "check": "Firehose ARN",
                        "status": "Pass",
                        "details": "All Firehose documents have ARN",
                        "recommendation": "N/A"
                    })
            except Exception as e:
                validation_results.append({
                    "check": "Firehose ARN",
                    "status": "Error",
                    "details": str(e),
                    "recommendation": "Check if Firehose data exists"
                })
            progress.advance(task)

            # Check 3: CloudWatch extracted fields (should be false)
            progress.update(task, description="[cyan]Checking CloudWatch field extraction...")
            try:
                # Look for unwanted extracted fields
                extracted_fields_query = {
                    "query": {
                        "bool": {
                            "must": [{"exists": {"field": "aws.cloudwatch"}}],
                            "should": [
                                {"exists": {"field": "aws.cloudwatch.extracted_fields"}},
                                {"exists": {"field": "extractedFields"}}
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "size": 0
                }
                result = es.search(index=queryable_pattern, body=extracted_fields_query)
                has_extracted = result["hits"]["total"]["value"]

                if has_extracted > 0:
                    validation_results.append({
                        "check": "CloudWatch Field Extraction",
                        "status": "Warning",
                        "details": f"{has_extracted:,} documents have extracted_fields (should be disabled)",
                        "recommendation": "Set include_cw_extracted_fields: false in Firehose config"
                    })
                else:
                    validation_results.append({
                        "check": "CloudWatch Field Extraction",
                        "status": "Pass",
                        "details": "CloudWatch extracted fields properly disabled",
                        "recommendation": "N/A"
                    })
            except Exception as e:
                validation_results.append({
                    "check": "CloudWatch Field Extraction",
                    "status": "Error",
                    "details": str(e),
                    "recommendation": "Check index mappings"
                })
            progress.advance(task)

            # Check 4: Kubernetes metadata for containerized sources
            progress.update(task, description="[cyan]Checking Kubernetes metadata...")
            try:
                # Docs that look like k8s logs but missing metadata
                k8s_pattern_query = {
                    "query": {
                        "bool": {
                            "should": [
                                {"wildcard": {"aws.cloudwatch.log_group": "*/eks/*"}},
                                {"wildcard": {"aws.cloudwatch.log_group": "*/kubernetes/*"}},
                                {"wildcard": {"aws.cloudwatch.log_stream": "*pod*"}}
                            ],
                            "must_not": [
                                {"exists": {"field": "kubernetes"}}
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "size": 0
                }
                result = es.search(index=queryable_pattern, body=k8s_pattern_query)
                missing_k8s = result["hits"]["total"]["value"]

                if missing_k8s > 0:
                    validation_results.append({
                        "check": "Kubernetes Metadata",
                        "status": "Warning",
                        "details": f"{missing_k8s:,} containerized logs missing kubernetes metadata",
                        "recommendation": "Ensure Fluent Bit/Fluentd includes kubernetes enrichment"
                    })
                else:
                    validation_results.append({
                        "check": "Kubernetes Metadata",
                        "status": "Pass",
                        "details": "Kubernetes metadata present where expected",
                        "recommendation": "N/A"
                    })
            except Exception as e:
                validation_results.append({
                    "check": "Kubernetes Metadata",
                    "status": "Info",
                    "details": "No containerized sources detected or check not applicable",
                    "recommendation": "N/A"
                })
            progress.advance(task)

            # Check 5: Timestamp parsing
            progress.update(task, description="[cyan]Checking timestamp parsing...")
            try:
                # Docs missing @timestamp
                missing_timestamp_query = {
                    "query": {
                        "bool": {
                            "must": [{"exists": {"field": "aws"}}],
                            "must_not": [{"exists": {"field": "@timestamp"}}]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=queryable_pattern, body=missing_timestamp_query)
                missing_ts = result["hits"]["total"]["value"]

                if missing_ts > 0:
                    validation_results.append({
                        "check": "Timestamp Parsing",
                        "status": "Fail",
                        "details": f"{missing_ts:,} documents missing @timestamp field",
                        "recommendation": "Critical: Fix timestamp parsing in ingest pipeline"
                    })
                else:
                    validation_results.append({
                        "check": "Timestamp Parsing",
                        "status": "Pass",
                        "details": "All documents have @timestamp field",
                        "recommendation": "N/A"
                    })
            except Exception as e:
                validation_results.append({
                    "check": "Timestamp Parsing",
                    "status": "Error",
                    "details": str(e),
                    "recommendation": "Check index mappings"
                })
            progress.advance(task)

        # Display results with pagination
        console.print("\n[cyan]Field Structure Validation Results:[/cyan]\n")

        # Build rows and count failures/warnings
        columns = [
            {"name": "Check", "style": "cyan", "no_wrap": False},
            {"name": "Status", "style": "bold"},
            {"name": "Details", "style": "white", "no_wrap": False},
            {"name": "Recommendation", "style": "dim", "no_wrap": False}
        ]

        rows = []
        fail_count = 0
        warn_count = 0

        for result in validation_results:
            status = result["status"]
            if status == "Pass":
                status_display = "[green]✅ Pass[/green]"
            elif status == "Warning":
                status_display = "[yellow]⚠️  Warning[/yellow]"
                warn_count += 1
            elif status == "Fail":
                status_display = "[red]❌ Fail[/red]"
                fail_count += 1
            elif status == "Info":
                status_display = "[blue]ℹ️  Info[/blue]"
            else:
                status_display = "[dim]⚠️  Error[/dim]"

            rows.append((
                result["check"],
                status_display,
                result["details"],
                result["recommendation"]
            ))

        paginate_table(rows, columns, page_size=20, title="AWS Field Structure Validation")

        # Determine which specific validation failures were detected
        has_timestamp_failure = any(r["check"] == "Timestamp Parsing" and r["status"] == "Fail" for r in validation_results)
        has_metadata_missing = any(r["check"] == "CloudWatch Metadata" and r["status"] == "Warning" for r in validation_results)
        has_firehose_arn_missing = any(r["check"] == "Firehose ARN" and r["status"] == "Warning" for r in validation_results)
        has_extracted_fields = any(r["check"] == "CloudWatch Field Extraction" and r["status"] == "Warning" for r in validation_results)
        has_k8s_metadata_missing = any(r["check"] == "Kubernetes Metadata" and r["status"] == "Warning" for r in validation_results)

        # Build issue-specific action recommendations
        if fail_count > 0 or warn_count > 0:
            actions = []

            if has_timestamp_failure:
                actions.append(
                    "[bold red]For Missing @timestamp:[/bold red]\n"
                    "  1. Go to: [yellow]Template & Policy Management → Edit Pipeline[/yellow]\n"
                    "  2. Add date processor with fallback to event.ingested:\n"
                    "     [dim]{\n"
                    "       \"date\": {\n"
                    "         \"field\": \"@timestamp\",\n"
                    "         \"target_field\": \"@timestamp\",\n"
                    "         \"formats\": [\"ISO8601\"],\n"
                    "         \"on_failure\": [\n"
                    "           {\"set\": {\"field\": \"@timestamp\", \"value\": \"{{event.ingested}}\"}}\n"
                    "         ]\n"
                    "       }\n"
                    "     }[/dim]\n"
                    "  3. [red]Critical:[/red] Fix immediately as time-series queries will fail\n"
                    "  4. Go to: [yellow]Quick Fixes & Actions → 🔄 Bulk Reindex[/yellow] → Reprocess"
                )

            if has_metadata_missing or has_firehose_arn_missing:
                actions.append(
                    "[bold yellow]For Missing CloudWatch/Firehose Metadata:[/bold yellow]\n"
                    "  1. Check AWS Firehose/ESF configuration:\n"
                    "     [dim]• Firehose: Set ProcessingConfiguration.Enabled = true\n"
                    "     • ESF: Configure metadata enrichment in Lambda\n"
                    "     • Verify CloudWatch log subscription filter settings[/dim]\n"
                    "  2. Ensure metadata fields are included in delivery stream\n"
                    "  3. Example Firehose configuration:\n"
                    "     [dim]ProcessingConfiguration:\n"
                    "       Enabled: true\n"
                    "       Processors:\n"
                    "         - Type: MetadataExtraction\n"
                    "           Parameters:\n"
                    "             - ParameterName: JsonParsingEngine\n"
                    "               ParameterValue: JQ-1.6[/dim]\n"
                    "  4. See: [yellow]AWS_FIREHOSE_ESF_ALL_ISSUES.md[/yellow] for detailed configuration"
                )

            if has_extracted_fields:
                actions.append(
                    "[bold yellow]For CloudWatch Field Extraction:[/bold yellow]\n"
                    "  1. Update Firehose configuration to disable extracted fields:\n"
                    "     [dim]{\n"
                    "       \"cloudwatch_logs\": {\n"
                    "         \"include_cw_extracted_fields\": false\n"
                    "       }\n"
                    "     }[/dim]\n"
                    "  2. Redeploy Firehose delivery stream with updated config\n"
                    "  3. [yellow]Warning:[/yellow] Extracted fields waste storage and duplicate data\n"
                    "  4. See: [yellow]AWS_FIREHOSE_ESF_ALL_ISSUES.md[/yellow] → CloudWatch Extracted Fields section"
                )

            if has_k8s_metadata_missing:
                actions.append(
                    "[bold yellow]For Missing Kubernetes Metadata:[/bold yellow]\n"
                    "  1. Ensure Fluent Bit/Fluentd includes kubernetes enrichment:\n"
                    "     [dim]# Fluent Bit configuration\n"
                    "     [FILTER]\n"
                    "         Name                kubernetes\n"
                    "         Match               kube.*\n"
                    "         Kube_URL            https://kubernetes.default.svc:443\n"
                    "         Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt\n"
                    "         Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token\n"
                    "         Merge_Log           On\n"
                    "         K8S-Logging.Parser  On\n"
                    "         K8S-Logging.Exclude On[/dim]\n"
                    "  2. Verify RBAC permissions for Fluent Bit/Fluentd\n"
                    "  3. Check pod logs for kubernetes filter errors"
                )

            action_text = "\n\n".join(actions) if actions else ""

        # Summary panel with actionable recommendations
        if fail_count > 0:
            console.print(Panel(
                f"[bold red]❌ {fail_count} critical validation failure(s)[/bold red]\n\n"
                f"Warnings: {warn_count}\n\n"
                f"[bold white]📋 Step-by-Step Fix Guide:[/bold white]\n\n"
                f"{action_text}\n\n"
                f"[dim]💡 Tip: See AWS_INGESTION_FIXES_GUIDE.md for detailed instructions[/dim]",
                title="[bold red]Validation Failed - Action Required[/bold red]",
                box=box.ROUNDED,
                border_style="red"
            ))
        elif warn_count > 0:
            console.print(Panel(
                f"[bold yellow]⚠️  {warn_count} warning(s) detected[/bold yellow]\n\n"
                f"Field structures are mostly correct but some improvements recommended.\n\n"
                f"[bold white]📋 Recommended Actions:[/bold white]\n\n"
                f"{action_text}\n\n"
                f"[dim]💡 Tip: See AWS_FIREHOSE_ESF_ALL_ISSUES.md for configuration examples[/dim]",
                title="[bold yellow]Validation Warnings[/bold yellow]",
                box=box.ROUNDED,
                border_style="yellow"
            ))
        else:
            console.print(Panel(
                "[bold green]✅ All validation checks passed[/bold green]\n\n"
                "AWS field structures are properly configured.",
                title="[bold green]Validation Passed[/bold green]",
                box=box.ROUNDED,
                border_style="green"
            ))
        console.print()

        # Offer interactive quick actions menu if there are issues
        if fail_count > 0 or warn_count > 0:
            console.print("[bold cyan]What would you like to do next?[/bold cyan]\n")

            action_choices = []

            if has_timestamp_failure:
                action_choices.append(
                    questionary.Choice("🔍 View Pipeline Troubleshooting (check date processors)", value="pipeline_troubleshooting")
                )
                action_choices.append(
                    questionary.Choice("🔄 Go to Bulk Reindex (reprocess with fixed pipeline)", value="bulk_reindex")
                )

            if has_timestamp_failure or has_metadata_missing or has_extracted_fields:
                action_choices.append(
                    questionary.Choice("✏️  Edit Pipeline Configuration", value="edit_pipeline")
                )

            if has_metadata_missing or has_firehose_arn_missing or has_extracted_fields:
                action_choices.append(
                    questionary.Choice("📖 View Firehose/ESF Configuration Guide", value="config_guide")
                )

            if has_k8s_metadata_missing:
                action_choices.append(
                    questionary.Choice("🐳 View Kubernetes Enrichment Guide", value="k8s_guide")
                )

            action_choices.extend([
                questionary.Choice("📤 Export Affected Documents", value="export_docs"),
                questionary.Separator(),
                questionary.Choice("📚 View AWS Ingestion Fixes Guide", value="view_guide"),
                questionary.Choice("← Return to AWS Ingestion Menu", value="back")
            ])

            try:
                next_action = questionary.select(
                    "Select action:",
                    choices=action_choices
                ).ask()

                if next_action == "pipeline_troubleshooting":
                    console.print("\n[cyan]→ Navigating to Pipeline Troubleshooting...[/cyan]\n")
                    option_pipeline_troubleshooting(es)

                elif next_action == "bulk_reindex":
                    console.print("\n[cyan]→ Navigating to Bulk Reindex...[/cyan]\n")
                    _bulk_reindex_failed_documents(es)

                elif next_action == "edit_pipeline":
                    console.print("\n[yellow]ℹ️  To edit pipelines:[/yellow]")
                    console.print("   Go to: [cyan]Main Menu → Template & Policy Management → Edit Pipeline[/cyan]\n")

                elif next_action == "config_guide":
                    console.print("\n[cyan]📖 Opening Firehose/ESF Configuration Guide...[/cyan]\n")
                    try:
                        import os
                        guide_path = os.path.join(os.path.dirname(__file__), "..", "..", "AWS_FIREHOSE_ESF_ALL_ISSUES.md")
                        if os.path.exists(guide_path):
                            console.print(Panel(
                                "[bold white]AWS Firehose/ESF Configuration Tips:[/bold white]\n\n"
                                "1. [cyan]Enable Metadata Inclusion:[/cyan]\n"
                                "   - Firehose: Set ProcessingConfiguration.Enabled = true\n"
                                "   - ESF: Configure metadata enrichment in Lambda\n\n"
                                "2. [cyan]Disable Extracted Fields:[/cyan]\n"
                                "   - Set include_cw_extracted_fields: false\n"
                                "   - Prevents duplicate data and wasted storage\n\n"
                                "3. [cyan]Optimize Buffer Settings:[/cyan]\n"
                                "   - Buffer size: 1-5 MB\n"
                                "   - Buffer interval: 60-300 seconds\n\n"
                                "4. [cyan]Ensure Complete Metadata:[/cyan]\n"
                                "   - CloudWatch: log_group, log_stream\n"
                                "   - Firehose: arn, request_id\n\n"
                                f"[dim]Full guide: {guide_path}[/dim]",
                                title="[bold cyan]Configuration Guide[/bold cyan]",
                                border_style="cyan"
                            ))
                        else:
                            console.print("[yellow]Guide file not found. See AWS_FIREHOSE_ESF_ALL_ISSUES.md in project root.[/yellow]\n")
                    except Exception as e:
                        console.print(f"[yellow]Could not open guide: {e}[/yellow]\n")

                elif next_action == "k8s_guide":
                    console.print("\n[cyan]📖 Kubernetes Enrichment Guide[/cyan]\n")
                    console.print(Panel(
                        "[bold white]Kubernetes Metadata Enrichment:[/bold white]\n\n"
                        "1. [cyan]Fluent Bit Configuration:[/cyan]\n"
                        "   - Add kubernetes filter to enrich logs\n"
                        "   - Ensure proper RBAC permissions\n"
                        "   - Set Merge_Log: On to parse JSON logs\n\n"
                        "2. [cyan]Required Fields:[/cyan]\n"
                        "   - kubernetes.pod.name\n"
                        "   - kubernetes.namespace\n"
                        "   - kubernetes.container.name\n"
                        "   - kubernetes.labels.*\n\n"
                        "3. [cyan]Troubleshooting:[/cyan]\n"
                        "   - Check Fluent Bit pod logs for errors\n"
                        "   - Verify ServiceAccount has list/get permissions\n"
                        "   - Ensure Kube_URL is accessible from pod\n\n"
                        "[dim]See Fluent Bit documentation for complete configuration[/dim]",
                        title="[bold cyan]Kubernetes Enrichment[/bold cyan]",
                        border_style="cyan"
                    ))
                    console.print()

                elif next_action == "export_docs":
                    console.print("\n[yellow]ℹ️  To export affected documents:[/yellow]")
                    console.print("   Go to: [cyan]Quick Fixes & Actions → Export Failed Logs to File[/cyan]")
                    console.print("   [dim]Note: Modify the query to match specific validation failures[/dim]\n")

                elif next_action == "view_guide":
                    console.print("\n[cyan]📖 Opening AWS Ingestion Fixes Guide...[/cyan]\n")
                    try:
                        import os
                        guide_path = os.path.join(os.path.dirname(__file__), "..", "..", "AWS_INGESTION_FIXES_GUIDE.md")
                        if os.path.exists(guide_path):
                            with open(guide_path, 'r') as f:
                                guide_content = f.read()
                            console.print(Panel(
                                guide_content[:2000] + "\n\n[dim]... (file continues)[/dim]",
                                title="[bold cyan]AWS Ingestion Fixes Guide (Preview)[/bold cyan]",
                                border_style="cyan"
                            ))
                            console.print(f"\n[green]Full guide available at: {guide_path}[/green]\n")
                        else:
                            console.print("[yellow]Guide file not found. See AWS_INGESTION_FIXES_GUIDE.md in project root.[/yellow]\n")
                    except Exception as e:
                        console.print(f"[yellow]Could not open guide: {e}[/yellow]\n")

            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not analyze field structures: {e}[/red]\n")


def option_pipeline_troubleshooting(es):
    """
    Troubleshoot ingest pipeline issues.

    - Show configured pipeline for each data stream
    - Test pipeline with sample documents
    - Identify which processor failed
    - Compare successful vs failed structures
    """
    show_breadcrumb(["Main Menu", "AWS Ingestion Management", "Pipeline Troubleshooting"])

    console.print("\n[bold cyan]🔧 Pipeline Troubleshooting[/bold cyan]\n")
    console.print("[dim]Analyzing ingest pipelines for AWS data streams...[/dim]\n")

    # Get index pattern
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    try:
        # Get data streams and their pipelines
        console.print(f"\n[cyan]Fetching data stream configurations...[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Loading data streams..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)

            try:
                # Get data streams
                data_streams_response = es.indices.get_data_stream(name=index_pattern)
                data_streams = data_streams_response.get("data_streams", [])
            except Exception:
                # If not data streams, try regular indices
                data_streams = []
                indices_response = es.cat.indices(index=index_pattern, format="json", h="index")
                for idx in indices_response:
                    index_name = idx.get("index")
                    if not is_system(index_name):
                        data_streams.append({"name": index_name})

        if not data_streams:
            console.print("\n[yellow]🟡 No matching data streams or indices found.[/yellow]\n")
            return

        # Analyze pipelines
        pipeline_info = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Analyzing pipelines...", total=len(data_streams))

            for ds in data_streams:
                ds_name = ds.get("name")
                progress.update(task, description=f"[cyan]Checking: {ds_name[:50]}...")

                try:
                    # Get index settings to find pipeline
                    settings = es.indices.get_settings(index=ds_name)

                    pipeline_name = None
                    for index_name, index_data in settings.items():
                        default_pipeline = index_data.get("settings", {}).get("index", {}).get("default_pipeline")
                        final_pipeline = index_data.get("settings", {}).get("index", {}).get("final_pipeline")

                        if default_pipeline:
                            pipeline_name = default_pipeline
                        elif final_pipeline:
                            pipeline_name = final_pipeline
                        break

                    if pipeline_name:
                        # Get pipeline details
                        try:
                            pipeline_response = es.ingest.get_pipeline(id=pipeline_name)
                            pipeline_def = pipeline_response.get(pipeline_name, {})
                            processors = pipeline_def.get("processors", [])

                            pipeline_info.append({
                                "data_stream": ds_name,
                                "pipeline": pipeline_name,
                                "processor_count": len(processors),
                                "processors": processors,
                                "status": "Configured"
                            })
                        except Exception as e:
                            pipeline_info.append({
                                "data_stream": ds_name,
                                "pipeline": pipeline_name,
                                "processor_count": 0,
                                "processors": [],
                                "status": f"Error: {str(e)[:50]}"
                            })
                    else:
                        pipeline_info.append({
                            "data_stream": ds_name,
                            "pipeline": "None",
                            "processor_count": 0,
                            "processors": [],
                            "status": "No pipeline"
                        })

                except Exception as e:
                    pipeline_info.append({
                        "data_stream": ds_name,
                        "pipeline": "Unknown",
                        "processor_count": 0,
                        "processors": [],
                        "status": f"Error: {str(e)[:50]}"
                    })

                progress.advance(task)

        # Display pipeline summary with pagination
        console.print("\n[cyan]Pipeline Configuration Summary:[/cyan]\n")

        # Define columns for pagination
        columns = [
            {"name": "Data Stream", "style": "cyan", "no_wrap": False},
            {"name": "Pipeline", "style": "yellow"},
            {"name": "Processors", "style": "white", "justify": "right"},
            {"name": "Status", "style": "bold"}
        ]

        # Build rows from pipeline_info
        rows = []
        for info in pipeline_info:
            status_display = info["status"]
            if "Error" in status_display:
                status_display = f"[red]{status_display}[/red]"
            elif status_display == "Configured":
                status_display = f"[green]✅ {status_display}[/green]"
            else:
                status_display = f"[yellow]⚠️  {status_display}[/yellow]"

            rows.append((
                info["data_stream"],
                info["pipeline"],
                str(info["processor_count"]),
                status_display
            ))

        paginate_table(rows, columns, page_size=20, title="Data Stream Pipeline Configuration")

        # Offer to view pipeline details
        if any(p["processor_count"] > 0 for p in pipeline_info):
            view_details = confirm_action("Would you like to view detailed processor information for a pipeline?")

            if view_details:
                # Select pipeline to view
                pipeline_choices = [
                    questionary.Choice(
                        f"{p['data_stream']} ({p['pipeline']})",
                        value=p
                    )
                    for p in pipeline_info if p["processor_count"] > 0
                ]

                if pipeline_choices:
                    selected = questionary.select(
                        "Select pipeline to view:",
                        choices=pipeline_choices
                    ).ask()

                    if selected:
                        console.print(f"\n[bold cyan]Pipeline: {selected['pipeline']}[/bold cyan]\n")

                        # Build processor panels for pagination
                        processor_panels = []
                        for idx, processor in enumerate(selected["processors"], 1):
                            processor_json = json.dumps(processor, indent=2)
                            syntax = Syntax(processor_json, "json", theme="monokai", line_numbers=True)
                            processor_panels.append(Panel(
                                syntax,
                                title=f"[bold]Processor {idx}[/bold]",
                                box=box.ROUNDED
                            ))

                        paginate_renderables(processor_panels, page_size=5, title=f"Processors: {selected['pipeline']}")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not troubleshoot pipelines: {e}[/red]\n")


def option_data_quality_metrics(es):
    """
    Calculate data quality metrics for AWS sources.

    - Success/failure rates
    - Parsing error percentages by source
    - High-failure log patterns
    - Volume trend analysis
    """
    show_breadcrumb(["Main Menu", "AWS Ingestion Management", "Data Quality Metrics"])

    console.print("\n[bold cyan]📈 AWS Data Quality Metrics[/bold cyan]\n")
    console.print("[dim]Calculating quality metrics for AWS-sourced logs...[/dim]\n")

    # Get index pattern
    index_pattern = get_index_pattern_selection(es)

    if not index_pattern:
        return

    # Get time range
    hours_back = get_number_input(
        "Analyze logs from last X hours:",
        default=24,
        min_val=1
    )

    if hours_back is None:
        return

    try:
        console.print(f"\n[cyan]Calculating metrics for last {hours_back} hours...[/cyan]\n")

        # Calculate time range
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours_back)

        metrics = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Calculating metrics...", total=5)

            # Metric 1: Total AWS documents
            progress.update(task, description="[cyan]Counting AWS documents...")
            try:
                total_aws_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "aws"}},
                                {"range": {"@timestamp": {"gte": start_time.isoformat(), "lte": now.isoformat()}}}
                            ]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=total_aws_query)
                metrics["total_aws_docs"] = result["hits"]["total"]["value"]
            except Exception as e:
                metrics["total_aws_docs"] = 0
                console.print(f"[yellow]⚠️  Could not count AWS docs: {e}[/yellow]")
            progress.advance(task)

            # Metric 2: Failed documents
            progress.update(task, description="[cyan]Counting failures...")
            try:
                failed_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"tags": "ingest_pipeline_failed"}},
                                {"range": {"@timestamp": {"gte": start_time.isoformat(), "lte": now.isoformat()}}}
                            ]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=failed_query)
                metrics["failed_docs"] = result["hits"]["total"]["value"]
            except Exception as e:
                metrics["failed_docs"] = 0
                console.print(f"[yellow]⚠️  Could not count failures: {e}[/yellow]")
            progress.advance(task)

            # Metric 3: Success rate by log group
            progress.update(task, description="[cyan]Analyzing by log group...")
            try:
                log_group_agg_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "aws.cloudwatch.log_group"}},
                                {"range": {"@timestamp": {"gte": start_time.isoformat(), "lte": now.isoformat()}}}
                            ]
                        }
                    },
                    "size": 0,
                    "aggs": {
                        "log_groups": {
                            "terms": {"field": "aws.cloudwatch.log_group.keyword", "size": 20},
                            "aggs": {
                                "failed": {
                                    "filter": {"term": {"tags": "ingest_pipeline_failed"}}
                                }
                            }
                        }
                    }
                }
                result = es.search(index=index_pattern, body=log_group_agg_query)
                log_group_buckets = result.get("aggregations", {}).get("log_groups", {}).get("buckets", [])

                metrics["log_groups"] = []
                for bucket in log_group_buckets:
                    total = bucket["doc_count"]
                    failed = bucket["failed"]["doc_count"]
                    success_rate = ((total - failed) / total * 100) if total > 0 else 0

                    metrics["log_groups"].append({
                        "name": bucket["key"],
                        "total": total,
                        "failed": failed,
                        "success_rate": success_rate
                    })
            except Exception as e:
                metrics["log_groups"] = []
                console.print(f"[yellow]⚠️  Could not analyze log groups: {e}[/yellow]")
            progress.advance(task)

            # Metric 4: Volume trend (hourly)
            progress.update(task, description="[cyan]Analyzing volume trends...")
            try:
                volume_trend_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "aws"}},
                                {"range": {"@timestamp": {"gte": start_time.isoformat(), "lte": now.isoformat()}}}
                            ]
                        }
                    },
                    "size": 0,
                    "aggs": {
                        "volume_over_time": {
                            "date_histogram": {
                                "field": "@timestamp",
                                "fixed_interval": "1h"
                            }
                        }
                    }
                }
                result = es.search(index=index_pattern, body=volume_trend_query)
                time_buckets = result.get("aggregations", {}).get("volume_over_time", {}).get("buckets", [])

                metrics["hourly_volumes"] = [bucket["doc_count"] for bucket in time_buckets]
                if metrics["hourly_volumes"]:
                    metrics["avg_hourly_volume"] = sum(metrics["hourly_volumes"]) / len(metrics["hourly_volumes"])
                    metrics["max_hourly_volume"] = max(metrics["hourly_volumes"])
                    metrics["min_hourly_volume"] = min(metrics["hourly_volumes"])
                else:
                    metrics["avg_hourly_volume"] = 0
                    metrics["max_hourly_volume"] = 0
                    metrics["min_hourly_volume"] = 0
            except Exception as e:
                metrics["hourly_volumes"] = []
                metrics["avg_hourly_volume"] = 0
                console.print(f"[yellow]⚠️  Could not analyze volume trends: {e}[/yellow]")
            progress.advance(task)

            # Metric 5: Parsing error types
            progress.update(task, description="[cyan]Categorizing errors...")
            try:
                # Count different error types
                error_types = {}

                # CloudWatch parsing errors
                cw_error_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "aws.cloudwatch.message"}},
                                {"wildcard": {"aws.cloudwatch.message": "*{*"}},
                                {"range": {"@timestamp": {"gte": start_time.isoformat(), "lte": now.isoformat()}}}
                            ],
                            "must_not": [{"exists": {"field": "message"}}]
                        }
                    },
                    "size": 0
                }
                result = es.search(index=index_pattern, body=cw_error_query)
                error_types["CloudWatch JSON not parsed"] = result["hits"]["total"]["value"]

                metrics["error_types"] = error_types
            except Exception as e:
                metrics["error_types"] = {}
                console.print(f"[yellow]⚠️  Could not categorize errors: {e}[/yellow]")
            progress.advance(task)

        # Display metrics
        console.print("\n[bold cyan]Data Quality Metrics Summary:[/bold cyan]\n")

        # Overall metrics
        if metrics["total_aws_docs"] > 0:
            success_rate = ((metrics["total_aws_docs"] - metrics["failed_docs"]) / metrics["total_aws_docs"] * 100)
            failure_rate = (metrics["failed_docs"] / metrics["total_aws_docs"] * 100)
        else:
            success_rate = 0
            failure_rate = 0

        overall_panel = Panel(
            f"[bold]Total AWS Documents:[/bold] {metrics['total_aws_docs']:,}\n"
            f"[bold]Failed Documents:[/bold] {metrics['failed_docs']:,}\n"
            f"[bold green]Success Rate:[/bold green] {success_rate:.2f}%\n"
            f"[bold {'red' if failure_rate > 5 else 'yellow' if failure_rate > 1 else 'green'}]Failure Rate:[/bold {'red' if failure_rate > 5 else 'yellow' if failure_rate > 1 else 'green'}] {failure_rate:.2f}%",
            title="[bold cyan]Overall Metrics[/bold cyan]",
            box=box.ROUNDED
        )
        console.print(overall_panel)
        console.print()

        # Log group metrics
        if metrics["log_groups"]:
            console.print("[bold cyan]Success Rate by Log Group:[/bold cyan]\n")

            log_group_table = Table(
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            log_group_table.add_column("Log Group", style="cyan", no_wrap=False)
            log_group_table.add_column("Total Docs", style="white", justify="right")
            log_group_table.add_column("Failed", style="red", justify="right")
            log_group_table.add_column("Success Rate", style="bold", justify="right")

            for lg in sorted(metrics["log_groups"], key=lambda x: x["success_rate"]):
                rate_color = "green" if lg["success_rate"] >= 95 else "yellow" if lg["success_rate"] >= 90 else "red"

                log_group_table.add_row(
                    lg["name"],
                    f"{lg['total']:,}",
                    f"{lg['failed']:,}",
                    f"[{rate_color}]{lg['success_rate']:.2f}%[/{rate_color}]"
                )

            console.print(log_group_table)
            console.print()

        # Volume trends
        if metrics["hourly_volumes"]:
            volume_panel = Panel(
                f"[bold]Average Hourly Volume:[/bold] {metrics['avg_hourly_volume']:.0f} docs/hour\n"
                f"[bold]Peak Hourly Volume:[/bold] {metrics['max_hourly_volume']:,} docs\n"
                f"[bold]Minimum Hourly Volume:[/bold] {metrics['min_hourly_volume']:,} docs",
                title="[bold cyan]Volume Trends[/bold cyan]",
                box=box.ROUNDED
            )
            console.print(volume_panel)
            console.print()

        # Error types
        if metrics["error_types"]:
            console.print("[bold cyan]Error Types:[/bold cyan]\n")

            error_table = Table(
                box=box.ROUNDED,
                title_style="bold cyan"
            )

            error_table.add_column("Error Type", style="cyan")
            error_table.add_column("Count", style="red", justify="right")

            for error_type, count in metrics["error_types"].items():
                if count > 0:
                    error_table.add_row(error_type, f"{count:,}")

            console.print(error_table)
            console.print()

        # Summary recommendation
        if failure_rate > 5:
            console.print(Panel(
                "[bold red]⚠️  HIGH FAILURE RATE DETECTED[/bold red]\n\n"
                f"Failure rate of {failure_rate:.2f}% exceeds acceptable threshold (5%).\n\n"
                "Recommended actions:\n"
                "• Review pipeline configurations\n"
                "• Check log groups with low success rates\n"
                "• Use Pipeline Troubleshooting to identify specific issues",
                title="[bold red]Action Required[/bold red]",
                box=box.ROUNDED,
                border_style="red"
            ))
        elif failure_rate > 1:
            console.print(Panel(
                f"[bold yellow]Failure rate: {failure_rate:.2f}%[/bold yellow]\n\n"
                "Some failures detected but within acceptable range.\n"
                "Monitor trends and investigate high-failure log groups.",
                title="[bold yellow]Monitor[/bold yellow]",
                box=box.ROUNDED,
                border_style="yellow"
            ))
        else:
            console.print(Panel(
                f"[bold green]✅ Excellent data quality ({success_rate:.2f}% success rate)[/bold green]\n\n"
                "AWS ingestion is performing well.",
                title="[bold green]Quality Check Passed[/bold green]",
                box=box.ROUNDED,
                border_style="green"
            ))
        console.print()

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not calculate metrics: {e}[/red]\n")


def option_quick_fixes_actions(es):
    """
    Provide quick fix actions.

    - Bulk reindex failed logs through corrected pipeline
    - Generate sample test documents
    - Export failed logs
    - Clear/tag problematic documents
    """
    show_breadcrumb(["Main Menu", "AWS Ingestion Management", "Quick Fixes & Actions"])

    console.print("\n[bold cyan]🔧 Quick Fixes & Actions[/bold cyan]\n")
    console.print("[dim]Quick actions for AWS ingestion issues...[/dim]\n")

    try:
        # Present action menu
        action = questionary.select(
            "Select action:",
            choices=[
                questionary.Choice("🔄 Bulk Reindex Failed Documents", value="bulk_reindex"),
                questionary.Separator(),
                questionary.Choice("Generate Sample Firehose Test Document", value="sample_firehose"),
                questionary.Choice("Generate Sample Serverless Forwarder Test Document", value="sample_forwarder"),
                questionary.Choice("Export Failed Logs to File", value="export_failed"),
                questionary.Choice("Tag Problematic Documents", value="tag_docs"),
                questionary.Separator(),
                questionary.Choice("← Back", value="back")
            ]
        ).ask()

        if not action or action == "back":
            return

        if action == "bulk_reindex":
            # Bulk reindex failed documents through corrected pipeline
            _bulk_reindex_failed_documents(es)

        elif action == "sample_firehose":
            # Generate sample Firehose document
            console.print("\n[cyan]Sample AWS Firehose Document:[/cyan]\n")

            sample_doc = {
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "aws": {
                    "firehose": {
                        "arn": "arn:aws:firehose:us-east-1:123456789012:deliverystream/my-stream",
                        "request_id": "sample-request-id"
                    },
                    "cloudwatch": {
                        "log_group": "/aws/eks/my-cluster/cluster",
                        "log_stream": "kube-apiserver-abc123",
                        "message": json.dumps({
                            "level": "info",
                            "msg": "Sample log message",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    }
                },
                "cloud": {
                    "provider": "aws",
                    "region": "us-east-1"
                }
            }

            sample_json = json.dumps(sample_doc, indent=2)
            syntax = Syntax(sample_json, "json", theme="monokai", line_numbers=True)
            console.print(Panel(
                syntax,
                title="[bold]Sample Firehose Document[/bold]",
                box=box.ROUNDED
            ))
            console.print("\n[dim]You can use this document to test your ingest pipeline.[/dim]\n")

        elif action == "sample_forwarder":
            # Generate sample Serverless Forwarder document
            console.print("\n[cyan]Sample Elastic Serverless Forwarder Document:[/cyan]\n")

            sample_doc = {
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "aws": {
                    "lambda": {
                        "function_name": "elastic-serverless-forwarder",
                        "function_version": "$LATEST",
                        "request_id": "sample-request-id"
                    },
                    "cloudwatch": {
                        "log_group": "/aws/lambda/my-function",
                        "log_stream": "2024/01/01/[$LATEST]abc123",
                        "message": "Sample Lambda log message"
                    }
                },
                "tags": ["elastic-serverless-forwarder"],
                "cloud": {
                    "provider": "aws",
                    "region": "us-east-1"
                }
            }

            sample_json = json.dumps(sample_doc, indent=2)
            syntax = Syntax(sample_json, "json", theme="monokai", line_numbers=True)
            console.print(Panel(
                syntax,
                title="[bold]Sample Serverless Forwarder Document[/bold]",
                box=box.ROUNDED
            ))
            console.print("\n[dim]You can use this document to test your ingest pipeline.[/dim]\n")

        elif action == "export_failed":
            # Export failed logs
            console.print("\n[cyan]Export Failed Logs[/cyan]\n")

            index_pattern = get_index_pattern_selection(es)
            if not index_pattern:
                return

            max_docs = get_number_input(
                "Maximum number of failed documents to export:",
                default=100,
                min_val=1,
                max_val=10000
            )

            if max_docs is None:
                return

            try:
                failed_query = {
                    "query": {"term": {"tags": "ingest_pipeline_failed"}},
                    "size": max_docs,
                    "sort": [{"@timestamp": {"order": "desc"}}]
                }

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[cyan]Fetching failed documents..."),
                    transient=True,
                ) as progress:
                    progress.add_task("fetch", total=None)
                    result = es.search(index=index_pattern, body=failed_query)

                failed_docs = result["hits"]["hits"]

                if not failed_docs:
                    console.print("\n[yellow]🟡 No failed documents found.[/yellow]\n")
                    return

                # Export to file
                filename = f"failed_aws_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                with open(filename, 'w') as f:
                    json.dump(failed_docs, f, indent=2, default=str)

                console.print(f"\n[green]✅ Exported {len(failed_docs)} failed documents to: {filename}[/green]\n")

            except Exception as e:
                console.print(f"\n[red]❌ ERROR: Could not export failed logs: {e}[/red]\n")

        elif action == "tag_docs":
            # Tag problematic documents
            console.print("\n[cyan]Tag Problematic Documents[/cyan]\n")
            console.print("[yellow]⚠️  This feature requires update_by_query API access.[/yellow]\n")

            if not GOD_MODE:
                console.print("[yellow]🔒 SAFE MODE: No changes will be made.[/yellow]\n")

            index_pattern = get_index_pattern_selection(es)
            if not index_pattern:
                return

            tag_name = get_text_input("Tag name to add (e.g., 'needs-review'):")
            if not tag_name:
                return

            if not confirm_action(f"Add tag '{tag_name}' to all failed documents in {index_pattern}?"):
                return

            try:
                update_query = {
                    "query": {"term": {"tags": "ingest_pipeline_failed"}},
                    "script": {
                        "source": "if (ctx._source.tags == null) { ctx._source.tags = [] } if (!ctx._source.tags.contains(params.tag)) { ctx._source.tags.add(params.tag) }",
                        "params": {"tag": tag_name}
                    }
                }

                if not GOD_MODE:
                    # Just count
                    count_query = {"query": {"term": {"tags": "ingest_pipeline_failed"}}, "size": 0}
                    result = es.search(index=index_pattern, body=count_query)
                    count = result["hits"]["total"]["value"]
                    console.print(f"\n[yellow]🔒 DRY-RUN: Would tag {count:,} documents with '{tag_name}'[/yellow]\n")
                else:
                    result = es.update_by_query(index=index_pattern, body=update_query)
                    updated = result.get("updated", 0)
                    console.print(f"\n[green]✅ Tagged {updated:,} documents with '{tag_name}'[/green]\n")

            except Exception as e:
                console.print(f"\n[red]❌ ERROR: Could not tag documents: {e}[/red]\n")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: {e}[/red]\n")


def _bulk_reindex_failed_documents(es):
    """
    Bulk reindex failed documents through a corrected pipeline.

    This function:
    1. Counts failed documents
    2. Prompts for pipeline name
    3. Reindexes documents through the corrected pipeline
    4. Removes the 'ingest_pipeline_failed' tag
    5. Cleans up error fields
    """
    console.print("\n[bold cyan]🔄 Bulk Reindex Failed Documents[/bold cyan]\n")
    console.print("[dim]Reprocess failed documents through a corrected pipeline...[/dim]\n")

    # Step 1: Get index pattern
    index_pattern = get_index_pattern_selection(es)
    if not index_pattern:
        return

    # Step 2: Count failed documents
    console.print("\n[cyan]Counting failed documents...[/cyan]")

    try:
        count_query = {
            "query": {"term": {"tags": "ingest_pipeline_failed"}},
            "size": 0
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing failed documents..."),
            transient=True,
        ) as progress:
            progress.add_task("count", total=None)
            result = es.search(index=index_pattern, body=count_query)

        total_failed = result["hits"]["total"]["value"]

        if total_failed == 0:
            console.print("\n[green]✅ No failed documents found![/green]\n")
            return

        console.print(f"\n[yellow]Found {total_failed:,} failed documents[/yellow]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error counting documents: {e}[/red]\n")
        return

    # Step 3: Get pipeline name
    console.print("[cyan]Enter the corrected pipeline name:[/cyan]")
    console.print("[dim]This should be the pipeline you've already fixed to handle the data correctly.[/dim]\n")

    pipeline_name = get_text_input("Pipeline name:")
    if not pipeline_name:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Step 4: Verify pipeline exists
    try:
        pipeline_response = es.ingest.get_pipeline(id=pipeline_name)
        if pipeline_name not in pipeline_response:
            console.print(f"\n[red]❌ Pipeline '{pipeline_name}' not found[/red]\n")
            return

        console.print(f"[green]✅ Pipeline '{pipeline_name}' found[/green]\n")

    except Exception as e:
        console.print(f"\n[red]❌ Error verifying pipeline: {e}[/red]\n")
        return

    # Step 5: Ask about target index
    console.print("[cyan]Reindex destination:[/cyan]")
    use_same_index = confirm_action(
        f"Reindex to the same index pattern ({index_pattern})?",
        default=True
    )

    if use_same_index:
        target_index = index_pattern
    else:
        target_index = get_text_input("Target index pattern:", default=index_pattern)
        if not target_index:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

    # Step 6: Show configuration summary
    console.print()
    console.print(Panel(
        f"[bold]Reindex Configuration:[/bold]\n\n"
        f"Source Index: {index_pattern}\n"
        f"Target Index: {target_index}\n"
        f"Pipeline: {pipeline_name}\n"
        f"Documents: {total_failed:,}\n"
        f"Timeout: {REINDEX_TIMEOUT}s\n\n"
        f"[yellow]This will:[/yellow]\n"
        f"• Reprocess documents through the corrected pipeline\n"
        f"• Remove 'ingest_pipeline_failed' tag\n"
        f"• Clean up error fields\n"
        f"• Overwrite existing documents with corrected versions",
        title="[bold yellow]⚠️  Confirm Reindex Operation[/bold yellow]",
        border_style="yellow"
    ))

    if not GOD_MODE:
        console.print("\n[yellow]🔒 SAFE MODE: No changes will be made.[/yellow]\n")

    if not confirm_action(f"Proceed with reindexing {total_failed:,} documents?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Step 7: Perform reindex
    console.print("\n[cyan]Starting reindex operation...[/cyan]\n")

    reindex_body = {
        "source": {
            "index": index_pattern,
            "query": {"term": {"tags": "ingest_pipeline_failed"}}
        },
        "dest": {
            "index": target_index,
            "pipeline": pipeline_name,
            "op_type": "index"  # Overwrite existing documents
        },
        "script": {
            "source": """
                // Remove the failed tag
                if (ctx._source.tags != null) {
                    ctx._source.tags.removeIf(tag -> tag == 'ingest_pipeline_failed');
                    if (ctx._source.tags.isEmpty()) {
                        ctx._source.remove('tags');
                    }
                }
                // Remove error field if it exists
                ctx._source.remove('error');
            """,
            "lang": "painless"
        }
    }

    try:
        if not GOD_MODE:
            console.print(f"[yellow]🔍 DRY-RUN: Would reindex {total_failed:,} documents[/yellow]")
            console.print(f"[blue]Source: {index_pattern}[/blue]")
            console.print(f"[blue]Target: {target_index}[/blue]")
            console.print(f"[blue]Pipeline: {pipeline_name}[/blue]\n")
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Reindexing documents..."),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("reindex", total=total_failed)

                # Execute reindex with timeout
                response = es.reindex(
                    body=reindex_body,
                    wait_for_completion=True,
                    request_timeout=REINDEX_TIMEOUT,
                    refresh=True
                )

                progress.update(task, completed=total_failed)

            # Display results
            console.print("\n[green]✅ Reindex completed![/green]\n")

            # Create results table
            results_table = Table(
                title="Reindex Results",
                box=box.ROUNDED,
                title_style="bold green"
            )

            results_table.add_column("Metric", style="cyan")
            results_table.add_column("Count", style="white", justify="right")

            results_table.add_row("Total Processed", f"{response.get('total', 0):,}")
            results_table.add_row("Created", f"[green]{response.get('created', 0):,}[/green]")
            results_table.add_row("Updated", f"[yellow]{response.get('updated', 0):,}[/yellow]")
            results_table.add_row("Deleted", f"{response.get('deleted', 0):,}")
            results_table.add_row("Failures", f"[red]{len(response.get('failures', [])):,}[/red]")

            console.print(results_table)
            console.print()

            # Show failures if any
            if response.get('failures'):
                console.print("[red]❌ Failures detected:[/red]\n")

                failure_table = Table(
                    title="First 10 Failures",
                    box=box.ROUNDED,
                    title_style="bold red"
                )

                failure_table.add_column("Index", style="cyan")
                failure_table.add_column("ID", style="yellow")
                failure_table.add_column("Error", style="red")

                for failure in response['failures'][:10]:
                    failure_table.add_row(
                        failure.get('index', 'N/A'),
                        failure.get('id', 'N/A')[:20],
                        str(failure.get('cause', {}).get('reason', 'Unknown'))[:50]
                    )

                console.print(failure_table)
                console.print()

                # Suggest next steps
                console.print(Panel(
                    "[bold yellow]Next Steps:[/bold yellow]\n\n"
                    "• Review the failure errors above\n"
                    "• Check if the pipeline needs further adjustments\n"
                    "• Export failed documents for detailed analysis\n"
                    "• Consider running Pipeline Troubleshooting",
                    title="[bold yellow]⚠️  Some Documents Failed[/bold yellow]",
                    border_style="yellow"
                ))
            else:
                console.print(Panel(
                    "[bold green]✅ All documents reindexed successfully![/bold green]\n\n"
                    "• Failed documents have been reprocessed\n"
                    "• 'ingest_pipeline_failed' tags removed\n"
                    "• Error fields cleaned up\n\n"
                    "Run Common Issue Detection again to verify the fix.",
                    title="[bold green]Success[/bold green]",
                    border_style="green"
                ))

    except Exception as e:
        console.print(f"\n[red]❌ Reindex failed: {e}[/red]\n")
        console.print("[yellow]Possible causes:[/yellow]")
        console.print("  • Pipeline configuration errors")
        console.print("  • Timeout (try smaller batches)")
        console.print("  • Insufficient permissions")
        console.print("  • Cluster resource constraints\n")

