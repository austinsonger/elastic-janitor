"""
FastAPI application for the Elastic Janitor web dashboard.
Provides JSON API endpoints mirroring the terminal dashboard metrics.
"""
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ..utils.formatters import size_to_bytes, bytes_to_human

# Module-level ES client, set by WebServerManager before server starts
es = None

app = FastAPI(title="Elastic Janitor Dashboard", docs_url=None, redoc_url=None)


@app.get("/api/cluster/health")
def cluster_health():
    """Return cluster health metrics."""
    if es is None:
        raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")
    try:
        health = es.cluster.health()
        return {
            "status": health.get("status", "unknown"),
            "cluster_name": health.get("cluster_name", ""),
            "number_of_nodes": health.get("number_of_nodes", 0),
            "number_of_data_nodes": health.get("number_of_data_nodes", 0),
            "active_shards": health.get("active_shards", 0),
            "active_primary_shards": health.get("active_primary_shards", 0),
            "relocating_shards": health.get("relocating_shards", 0),
            "initializing_shards": health.get("initializing_shards", 0),
            "unassigned_shards": health.get("unassigned_shards", 0),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch cluster health: {exc}")


@app.get("/api/cluster/storage")
def cluster_storage():
    """Return storage usage aggregated by data tier."""
    if es is None:
        raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")
    try:
        rows = es.cat.indices(format="json", h="index,store.size,dt")
        tier_bytes = {}
        for row in rows:
            tier = row.get("dt") or "unknown"
            size_str = row.get("store.size", "0b")
            tier_bytes[tier] = tier_bytes.get(tier, 0) + size_to_bytes(size_str)

        tiers = []
        for name in ["hot", "warm", "cold", "frozen", "unknown"]:
            size = tier_bytes.get(name, 0)
            if size > 0:
                tiers.append({
                    "name": name,
                    "size_bytes": size,
                    "size_human": bytes_to_human(size),
                })
        return {"tiers": tiers}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch storage data: {exc}")


@app.get("/api/cluster/nodes")
def cluster_nodes():
    """Return per-node resource metrics."""
    if es is None:
        raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")
    try:
        stats = es.nodes.stats(metric=["os", "jvm", "indices"])
        nodes = []
        for node_id, node_data in stats.get("nodes", {}).items():
            cpu = node_data.get("os", {}).get("cpu", {}).get("percent", 0)
            jvm_mem = node_data.get("jvm", {}).get("mem", {})
            heap_used = jvm_mem.get("heap_used_in_bytes", 0)
            heap_max = jvm_mem.get("heap_max_in_bytes", 1)
            heap_pct = (heap_used / heap_max * 100) if heap_max > 0 else 0

            indices = node_data.get("indices", {})
            docs_indexed = indices.get("indexing", {}).get("index_total", 0)
            queries = indices.get("search", {}).get("query_total", 0)

            nodes.append({
                "name": node_data.get("name", node_id),
                "cpu_percent": cpu,
                "heap_used_bytes": heap_used,
                "heap_max_bytes": heap_max,
                "heap_percent": round(heap_pct, 1),
                "heap_used_human": bytes_to_human(heap_used),
                "heap_max_human": bytes_to_human(heap_max),
                "docs_indexed": docs_indexed,
                "queries": queries,
            })
        return {"nodes": nodes}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch node stats: {exc}")


@app.get("/api/dashboard")
def combined_dashboard():
    """Combined endpoint returning health, nodes, and performance totals."""
    if es is None:
        raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")
    try:
        health = es.cluster.health()
        stats = es.nodes.stats(metric=["os", "jvm", "indices"])

        nodes = []
        total_docs = 0
        total_queries = 0

        for node_id, node_data in stats.get("nodes", {}).items():
            cpu = node_data.get("os", {}).get("cpu", {}).get("percent", 0)
            jvm_mem = node_data.get("jvm", {}).get("mem", {})
            heap_used = jvm_mem.get("heap_used_in_bytes", 0)
            heap_max = jvm_mem.get("heap_max_in_bytes", 1)
            heap_pct = (heap_used / heap_max * 100) if heap_max > 0 else 0

            indices = node_data.get("indices", {})
            docs = indices.get("indexing", {}).get("index_total", 0)
            qry = indices.get("search", {}).get("query_total", 0)
            total_docs += docs
            total_queries += qry

            nodes.append({
                "name": node_data.get("name", node_id),
                "cpu_percent": cpu,
                "heap_used_bytes": heap_used,
                "heap_max_bytes": heap_max,
                "heap_percent": round(heap_pct, 1),
                "heap_used_human": bytes_to_human(heap_used),
                "heap_max_human": bytes_to_human(heap_max),
            })

        return {
            "health": {
                "status": health.get("status", "unknown"),
                "cluster_name": health.get("cluster_name", ""),
                "number_of_nodes": health.get("number_of_nodes", 0),
                "active_shards": health.get("active_shards", 0),
                "unassigned_shards": health.get("unassigned_shards", 0),
            },
            "nodes": nodes,
            "performance": {
                "total_docs_indexed": total_docs,
                "total_queries": total_queries,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard data: {exc}")


# Mount static files last so API routes take priority.
# Resolved at import-time relative to the project root.
_frontend_dist = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "dist"
)

if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def index_fallback():
        return {
            "message": "Frontend not built. Run: cd frontend && npm install && npm run build"
        }
