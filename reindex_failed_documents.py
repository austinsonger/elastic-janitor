#!/usr/bin/env python3
"""
Helper script to reindex failed documents through a corrected pipeline.

Usage:
    python reindex_failed_documents.py

This script will:
1. Find all documents with 'ingest_pipeline_failed' tag
2. Reindex them through the corrected pipeline
3. Remove the failed tag after successful reprocessing
"""

import sys
from elasticsearch import Elasticsearch
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from janitor.config import ELASTIC_URL, ELASTIC_API_KEY

console = Console()


def reindex_failed_documents(es, source_index, target_index, pipeline_name, batch_size=100):
    """
    Reindex failed documents through a corrected pipeline.
    
    Args:
        es: Elasticsearch client
        source_index: Source index pattern (e.g., 'logs-aws.cloudwatch-*')
        target_index: Target index (can be same as source)
        pipeline_name: Name of the corrected pipeline
        batch_size: Number of documents to process per batch
    """
    
    console.print("\n[bold cyan]🔄 Reindexing Failed Documents[/bold cyan]\n")
    
    # Step 1: Count failed documents
    console.print("[cyan]Counting failed documents...[/cyan]")
    count_query = {
        "query": {"term": {"tags": "ingest_pipeline_failed"}},
        "size": 0
    }
    
    try:
        result = es.search(index=source_index, body=count_query)
        total_failed = result["hits"]["total"]["value"]
        
        if total_failed == 0:
            console.print("[green]✅ No failed documents found![/green]\n")
            return
        
        console.print(f"[yellow]Found {total_failed:,} failed documents[/yellow]\n")
        
    except Exception as e:
        console.print(f"[red]❌ Error counting documents: {e}[/red]\n")
        return
    
    # Step 2: Confirm reindex
    console.print(Panel(
        f"[bold]Reindex Configuration:[/bold]\n\n"
        f"Source Index: {source_index}\n"
        f"Target Index: {target_index}\n"
        f"Pipeline: {pipeline_name}\n"
        f"Documents: {total_failed:,}\n"
        f"Batch Size: {batch_size}",
        title="[bold yellow]⚠️  Confirm Reindex[/bold yellow]",
        border_style="yellow"
    ))
    
    confirm = input("\nProceed with reindex? (yes/no): ").strip().lower()
    if confirm != "yes":
        console.print("[yellow]⚠️  Cancelled.[/yellow]\n")
        return
    
    # Step 3: Perform reindex using _reindex API
    console.print("\n[cyan]Starting reindex operation...[/cyan]\n")
    
    reindex_body = {
        "source": {
            "index": source_index,
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
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Reindexing..."),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("reindex", total=total_failed)
            
            # Execute reindex
            response = es.reindex(
                body=reindex_body,
                wait_for_completion=True,
                request_timeout=300  # 5 minute timeout
            )
            
            progress.update(task, completed=total_failed)
        
        # Display results
        console.print("\n[green]✅ Reindex completed![/green]\n")
        console.print(f"[cyan]Total: {response.get('total', 0):,}[/cyan]")
        console.print(f"[green]Created: {response.get('created', 0):,}[/green]")
        console.print(f"[yellow]Updated: {response.get('updated', 0):,}[/yellow]")
        console.print(f"[red]Failures: {response.get('failures', []) or 0}[/red]\n")
        
        if response.get('failures'):
            console.print("[red]Failures:[/red]")
            for failure in response['failures'][:10]:  # Show first 10 failures
                console.print(f"  • {failure}")
        
    except Exception as e:
        console.print(f"\n[red]❌ Reindex failed: {e}[/red]\n")


def main():
    """Main entry point."""
    console.print("\n[bold cyan]Failed Document Reindexing Tool[/bold cyan]\n")
    
    # Connect to Elasticsearch
    try:
        es = Elasticsearch(hosts=[ELASTIC_URL], api_key=ELASTIC_API_KEY)
        info = es.info()
        cluster_name = info.get("cluster_name", "UNKNOWN")
        console.print(f"[green]✅ Connected to cluster: {cluster_name}[/green]\n")
    except Exception as e:
        console.print(f"[red]❌ Connection failed: {e}[/red]\n")
        sys.exit(1)
    
    # Get user input
    source_index = input("Source index pattern (e.g., 'logs-aws.cloudwatch-*'): ").strip()
    if not source_index:
        console.print("[red]❌ Source index is required[/red]\n")
        sys.exit(1)
    
    target_index = input(f"Target index (press Enter to use '{source_index}'): ").strip()
    if not target_index:
        target_index = source_index
    
    pipeline_name = input("Pipeline name: ").strip()
    if not pipeline_name:
        console.print("[red]❌ Pipeline name is required[/red]\n")
        sys.exit(1)
    
    # Execute reindex
    reindex_failed_documents(es, source_index, target_index, pipeline_name)


if __name__ == "__main__":
    main()

