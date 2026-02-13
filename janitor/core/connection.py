"""
Elasticsearch connection and index information retrieval.
"""
import sys
from elasticsearch import Elasticsearch
from rich.progress import Progress, SpinnerColumn, TextColumn
from ..config import ELASTIC_URL, ELASTIC_API_KEY, console
from ..utils.formatters import parse_epoch_millis, size_to_bytes


def connect():
    """Connect to Elasticsearch cluster."""
    if not ELASTIC_URL or not ELASTIC_API_KEY:
        console.print("[red]❌ ERROR: Set ELASTIC_URL and ELASTIC_API_KEY at the top of the script.[/red]")
        sys.exit(1)

    es = Elasticsearch(hosts=[ELASTIC_URL], api_key=ELASTIC_API_KEY)

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Connecting to Elasticsearch..."),
        transient=True,
    ) as progress:
        progress.add_task("connect", total=None)
        try:
            info = es.info()
            cluster_name = info.get("cluster_name", "UNKNOWN")
            console.print(f"[green]✅ Connected to cluster: {cluster_name}[/green]\n")
            return es
        except Exception as e:
            console.print(f"[red]❌ ERROR: Could not connect to Elasticsearch: {e}[/red]")
            sys.exit(1)


def get_index_creation(es, index_name):
    """Get index creation date."""
    info = es.indices.get(index=index_name)
    ms = info[index_name]["settings"]["index"]["creation_date"]
    return parse_epoch_millis(ms)


def get_all_indices_info(es):
    """Fetch creation dates, sizes, and tier info for all indices in one API call."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Fetching index information..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        rows = es.cat.indices(format="json", h="index,creation.date,store.size,pri.store.size,dt")

    info_map = {}
    for r in rows:
        index_name = r.get("index")
        creation_ms = r.get("creation.date")
        store_size = r.get("store.size", "0b")
        pri_store_size = r.get("pri.store.size", "0b")
        tier = r.get("dt", "unknown")  # dt = data tier

        if index_name and creation_ms:
            info_map[index_name] = {
                "created": parse_epoch_millis(creation_ms),
                "size": store_size,
                "size_bytes": size_to_bytes(store_size),
                "pri_size": pri_store_size,
                "pri_size_bytes": size_to_bytes(pri_store_size),
                "tier": tier if tier else "unknown"
            }

    return info_map

