#!/usr/bin/env python3
"""
Test script to verify the Indexing Performance Monitor enhancement.
This script demonstrates the new recommendation engine with mock data.
"""

from janitor.operations.performance_monitoring import _display_indexing_recommendations
from janitor.config import console

def test_recommendations_with_critical_bottleneck():
    """Test recommendations with critical bottleneck (>100k rejections)"""
    
    console.print("\n[bold cyan]Test Case 1: Critical Bottleneck (>100k rejections)[/bold cyan]\n")
    
    # Mock bottleneck data
    bottleneck_data = [
        {
            "node": "es-node-1",
            "pool": "write",
            "queue": 50,
            "rejected": 150000,
            "completed": 5850000,
            "rejection_rate": 2.5,
            "queue_size": 1000,
            "threads": 8,
        },
        {
            "node": "es-node-2",
            "pool": "write",
            "queue": 30,
            "rejected": 120000,
            "completed": 4880000,
            "rejection_rate": 2.4,
            "queue_size": 1000,
            "threads": 8,
        }
    ]
    
    # Mock node info
    node_info = {
        "es-node-1": {
            "cpu_percent": 85,
            "heap_used": 25 * 1024**3,  # 25 GB
            "heap_max": 32 * 1024**3,   # 32 GB
            "heap_percent": 78,
        },
        "es-node-2": {
            "cpu_percent": 82,
            "heap_used": 24 * 1024**3,
            "heap_max": 32 * 1024**3,
            "heap_percent": 75,
        }
    }
    
    # Mock indexing data with high-throughput indices
    indexing_data = [
        {"index": "logs-2024.01.15", "docs_indexed": 5000000, "time_ms": 270000, "docs_per_sec": 18518},
        {"index": "metrics-prod", "docs_indexed": 3000000, "time_ms": 136000, "docs_per_sec": 22058},
        {"index": "events-app", "docs_indexed": 1000000, "time_ms": 100000, "docs_per_sec": 10000},
    ]
    
    # Mock nodes (just need count)
    nodes = {"node1": {}, "node2": {}, "node3": {}}
    
    # Call the recommendation function
    _display_indexing_recommendations(bottleneck_data, node_info, indexing_data, nodes)


def test_recommendations_with_important_bottleneck():
    """Test recommendations with important bottleneck (>1k rejections)"""
    
    console.print("\n[bold cyan]Test Case 2: Important Bottleneck (>1k rejections)[/bold cyan]\n")
    
    bottleneck_data = [
        {
            "node": "es-node-1",
            "pool": "bulk",
            "queue": 10,
            "rejected": 5000,
            "completed": 1000000,
            "rejection_rate": 0.5,
            "queue_size": 200,
            "threads": 4,
        }
    ]
    
    node_info = {
        "es-node-1": {
            "cpu_percent": 45,
            "heap_used": 12 * 1024**3,
            "heap_max": 16 * 1024**3,
            "heap_percent": 75,
        }
    }
    
    indexing_data = [
        {"index": "logs-2024.01.15", "docs_indexed": 500000, "time_ms": 50000, "docs_per_sec": 10000},
    ]
    
    nodes = {"node1": {}}
    
    _display_indexing_recommendations(bottleneck_data, node_info, indexing_data, nodes)


def test_recommendations_node_specific():
    """Test recommendations with node-specific bottleneck"""
    
    console.print("\n[bold cyan]Test Case 3: Node-Specific Bottleneck[/bold cyan]\n")
    
    bottleneck_data = [
        {
            "node": "es-node-2",
            "pool": "write",
            "queue": 5,
            "rejected": 500,
            "completed": 500000,
            "rejection_rate": 0.1,
            "queue_size": 200,
            "threads": 4,
        }
    ]
    
    node_info = {
        "es-node-2": {
            "cpu_percent": 35,
            "heap_used": 8 * 1024**3,
            "heap_max": 16 * 1024**3,
            "heap_percent": 50,
        }
    }
    
    indexing_data = [
        {"index": "logs-2024.01.15", "docs_indexed": 300000, "time_ms": 30000, "docs_per_sec": 10000},
    ]
    
    # 5 nodes total, only 1 affected = node-specific issue
    nodes = {"node1": {}, "node2": {}, "node3": {}, "node4": {}, "node5": {}}
    
    _display_indexing_recommendations(bottleneck_data, node_info, indexing_data, nodes)


if __name__ == "__main__":
    console.print("[bold green]Testing Indexing Performance Monitor Enhancement[/bold green]")
    console.print("[dim]This demonstrates the new detailed recommendations feature[/dim]\n")
    
    try:
        test_recommendations_with_critical_bottleneck()
        test_recommendations_with_important_bottleneck()
        test_recommendations_node_specific()
        
        console.print("\n[bold green]✅ All test cases completed successfully![/bold green]\n")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Test failed: {e}[/bold red]\n")
        import traceback
        traceback.print_exc()

