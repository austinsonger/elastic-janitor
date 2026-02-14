"""
Configuration Versioning for Elastic Janitor.
Full versioning system for cluster-wide settings with snapshot, version management, and restore functionality.
"""
import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
from ..config import console, DRY_RUN_MODE
from ..utils import confirm_action, safe_input, show_breadcrumb, select_from_list
from ..utils.history_logger import log_operation


# Database path - store in user's home directory
DB_DIR = Path.home() / ".elastic-janitor"
CONFIG_DB_PATH = DB_DIR / "config_versions.db"


def _get_config_db_connection():
    """Get database connection for config versions, creating database if needed."""
    # Ensure directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(CONFIG_DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def _init_config_database():
    """Initialize config versioning database schema if not exists."""
    conn = _get_config_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_number INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            cluster_settings TEXT NOT NULL,
            node_settings TEXT,
            allocation_settings TEXT,
            shard_settings TEXT,
            metadata TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_version_number
        ON config_versions(version_number DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON config_versions(timestamp DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tags
        ON config_versions(tags)
    """)
    
    conn.commit()
    conn.close()


def capture_cluster_configuration(es, description=None, tags=None):
    """
    Capture current cluster-wide configuration as a snapshot.
    
    Args:
        es: Elasticsearch client
        description: User-provided description for this version
        tags: Comma-separated tags for categorization
        
    Returns:
        int: Version number of the saved configuration
    """
    _init_config_database()
    
    console.print("\n[cyan]Capturing cluster configuration...[/cyan]\n")
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Fetching cluster settings..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            
            # Get cluster settings
            cluster_settings = es.cluster.get_settings(include_defaults=False, flat_settings=True)
            
            # Get allocation settings
            allocation_settings = {}
            try:
                allocation_resp = es.cluster.get_settings(include_defaults=False)
                if "persistent" in allocation_resp:
                    allocation_settings["persistent"] = allocation_resp.get("persistent", {})
                if "transient" in allocation_resp:
                    allocation_settings["transient"] = allocation_resp.get("transient", {})
            except Exception:
                pass
            
            # Get node settings (sample from one node)
            node_settings = {}
            try:
                nodes_info = es.nodes.info()
                if "nodes" in nodes_info and nodes_info["nodes"]:
                    first_node = list(nodes_info["nodes"].values())[0]
                    node_settings = first_node.get("settings", {})
            except Exception:
                pass
            
            # Get shard allocation settings
            shard_settings = {}
            try:
                shard_allocation = es.cluster.get_settings(include_defaults=False)
                if "persistent" in shard_allocation:
                    persistent = shard_allocation["persistent"]
                    if "cluster" in persistent and "routing" in persistent["cluster"]:
                        shard_settings = persistent["cluster"]["routing"]
            except Exception:
                pass
        
        # Save to database
        conn = _get_config_db_connection()
        cursor = conn.cursor()
        
        # Get next version number
        cursor.execute("SELECT COALESCE(MAX(version_number), 0) + 1 as next_version FROM config_versions")
        version_number = cursor.fetchone()["next_version"]
        
        timestamp = datetime.now().isoformat()
        
        # Prepare metadata
        metadata = {
            "captured_at": timestamp,
            "elasticsearch_version": None,
            "cluster_name": None
        }
        
        try:
            cluster_info = es.info()
            metadata["elasticsearch_version"] = cluster_info.get("version", {}).get("number")
            metadata["cluster_name"] = cluster_info.get("cluster_name")
        except Exception:
            pass
        
        cursor.execute("""
            INSERT INTO config_versions
            (version_number, timestamp, description, tags, cluster_settings, 
             node_settings, allocation_settings, shard_settings, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            version_number,
            timestamp,
            description,
            tags,
            json.dumps(cluster_settings, indent=2),
            json.dumps(node_settings, indent=2) if node_settings else None,
            json.dumps(allocation_settings, indent=2) if allocation_settings else None,
            json.dumps(shard_settings, indent=2) if shard_settings else None,
            json.dumps(metadata, indent=2)
        ))
        
        conn.commit()
        conn.close()
        
        console.print(f"[green]✅ Configuration snapshot saved as version {version_number}[/green]\n")
        
        return version_number
    
    except Exception as e:
        console.print(f"[red]❌ Error capturing configuration: {e}[/red]\n")
        return None


def get_config_versions(limit=50):
    """
    Get all saved configuration versions.

    Args:
        limit: Maximum number of versions to retrieve

    Returns:
        list: List of version dictionaries
    """
    _init_config_database()

    conn = _get_config_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, version_number, timestamp, description, tags, metadata
        FROM config_versions
        ORDER BY version_number DESC
        LIMIT ?
    """, (limit,))

    versions = []
    for row in cursor.fetchall():
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        versions.append({
            "id": row["id"],
            "version_number": row["version_number"],
            "timestamp": row["timestamp"],
            "description": row["description"],
            "tags": row["tags"],
            "metadata": metadata
        })

    conn.close()
    return versions


def get_config_version(version_number):
    """
    Get a specific configuration version.

    Args:
        version_number: Version number to retrieve

    Returns:
        dict: Version data or None if not found
    """
    _init_config_database()

    conn = _get_config_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM config_versions
        WHERE version_number = ?
    """, (version_number,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "version_number": row["version_number"],
        "timestamp": row["timestamp"],
        "description": row["description"],
        "tags": row["tags"],
        "cluster_settings": json.loads(row["cluster_settings"]),
        "node_settings": json.loads(row["node_settings"]) if row["node_settings"] else None,
        "allocation_settings": json.loads(row["allocation_settings"]) if row["allocation_settings"] else None,
        "shard_settings": json.loads(row["shard_settings"]) if row["shard_settings"] else None,
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
    }


def delete_config_version(version_number):
    """Delete a configuration version."""
    _init_config_database()

    conn = _get_config_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM config_versions WHERE version_number = ?", (version_number,))
    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    return deleted > 0


def compare_config_versions(version1, version2):
    """
    Compare two configuration versions.

    Args:
        version1: First version data (dict)
        version2: Second version data (dict)

    Returns:
        dict: Comparison results with differences
    """
    differences = {
        "cluster_settings": {},
        "allocation_settings": {},
        "shard_settings": {}
    }

    # Compare cluster settings
    settings1 = version1.get("cluster_settings", {})
    settings2 = version2.get("cluster_settings", {})

    all_keys = set(list(settings1.keys()) + list(settings2.keys()))

    for key in all_keys:
        val1 = settings1.get(key)
        val2 = settings2.get(key)

        if val1 != val2:
            differences["cluster_settings"][key] = {
                "version1": val1,
                "version2": val2
            }

    # Compare allocation settings
    alloc1 = version1.get("allocation_settings", {})
    alloc2 = version2.get("allocation_settings", {})

    if alloc1 != alloc2:
        differences["allocation_settings"] = {
            "version1": alloc1,
            "version2": alloc2
        }

    # Compare shard settings
    shard1 = version1.get("shard_settings", {})
    shard2 = version2.get("shard_settings", {})

    if shard1 != shard2:
        differences["shard_settings"] = {
            "version1": shard1,
            "version2": shard2
        }

    return differences


def restore_config_version(es, version_number, dry_run=False):
    """
    Restore a configuration version.

    Args:
        es: Elasticsearch client
        version_number: Version number to restore
        dry_run: If True, only preview changes

    Returns:
        dict: Result with success status and messages
    """
    version = get_config_version(version_number)

    if not version:
        return {"success": False, "message": "Version not found"}

    is_dry_run = DRY_RUN_MODE or dry_run

    console.print(f"\n[cyan]Restoring configuration version {version_number}...[/cyan]\n")

    if is_dry_run:
        console.print("[yellow]DRY RUN MODE: No changes will be applied[/yellow]\n")

    try:
        # Get current settings for comparison
        current_settings = es.cluster.get_settings(include_defaults=False, flat_settings=True)

        # Restore cluster settings
        cluster_settings = version.get("cluster_settings", {})

        if cluster_settings:
            console.print("[cyan]Applying cluster settings...[/cyan]")

            if not is_dry_run:
                # Apply persistent settings
                persistent = {}
                transient = {}

                for key, value in cluster_settings.get("persistent", {}).items():
                    persistent[key] = value

                for key, value in cluster_settings.get("transient", {}).items():
                    transient[key] = value

                if persistent or transient:
                    body = {}
                    if persistent:
                        body["persistent"] = persistent
                    if transient:
                        body["transient"] = transient

                    es.cluster.put_settings(body=body)
                    console.print("[green]✓ Cluster settings applied[/green]")
            else:
                console.print("[yellow]Would apply cluster settings[/yellow]")

        # Restore allocation settings
        allocation_settings = version.get("allocation_settings", {})

        if allocation_settings:
            console.print("[cyan]Applying allocation settings...[/cyan]")

            if not is_dry_run:
                es.cluster.put_settings(body=allocation_settings)
                console.print("[green]✓ Allocation settings applied[/green]")
            else:
                console.print("[yellow]Would apply allocation settings[/yellow]")

        console.print()

        if is_dry_run:
            return {"success": True, "message": "DRY RUN: Configuration would be restored"}
        else:
            return {"success": True, "message": f"Configuration version {version_number} restored successfully"}

    except Exception as e:
        return {"success": False, "message": f"Failed to restore configuration: {str(e)}"}


def export_config_version_to_file(version_number, filename):
    """Export a configuration version to JSON file."""
    version = get_config_version(version_number)

    if not version:
        return False

    try:
        with open(filename, "w") as f:
            json.dump(version, f, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]❌ Error exporting: {e}[/red]")
        return False


def import_config_version_from_file(filename):
    """Import a configuration version from JSON file."""
    try:
        with open(filename, "r") as f:
            version_data = json.load(f)

        # Validate required fields
        if "cluster_settings" not in version_data:
            console.print("[red]❌ Invalid configuration file: missing cluster_settings[/red]")
            return None

        _init_config_database()

        conn = _get_config_db_connection()
        cursor = conn.cursor()

        # Get next version number
        cursor.execute("SELECT COALESCE(MAX(version_number), 0) + 1 as next_version FROM config_versions")
        version_number = cursor.fetchone()["next_version"]

        timestamp = datetime.now().isoformat()

        # Add import metadata
        metadata = version_data.get("metadata", {})
        metadata["imported_at"] = timestamp
        metadata["imported_from"] = filename

        cursor.execute("""
            INSERT INTO config_versions
            (version_number, timestamp, description, tags, cluster_settings,
             node_settings, allocation_settings, shard_settings, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            version_number,
            timestamp,
            f"Imported from {filename}: {version_data.get('description', '')}",
            version_data.get("tags"),
            json.dumps(version_data.get("cluster_settings"), indent=2),
            json.dumps(version_data.get("node_settings"), indent=2) if version_data.get("node_settings") else None,
            json.dumps(version_data.get("allocation_settings"), indent=2) if version_data.get("allocation_settings") else None,
            json.dumps(version_data.get("shard_settings"), indent=2) if version_data.get("shard_settings") else None,
            json.dumps(metadata, indent=2)
        ))

        conn.commit()
        conn.close()

        return version_number

    except Exception as e:
        console.print(f"[red]❌ Error importing: {e}[/red]")
        return None


def display_config_versions():
    """Display all configuration versions in a table."""
    versions = get_config_versions(limit=100)

    if not versions:
        console.print("\n[yellow]🟡 No configuration versions found.[/yellow]\n")
        return

    table = Table(title="Configuration Versions", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Version", style="cyan", width=10)
    table.add_column("Timestamp", style="yellow", width=20)
    table.add_column("Description", style="white", width=40)
    table.add_column("Tags", style="dim", width=20)

    for v in versions:
        timestamp = v["timestamp"][:19]  # Truncate to datetime
        description = v["description"] or "[dim]No description[/dim]"
        tags = v["tags"] or ""

        table.add_row(
            str(v["version_number"]),
            timestamp,
            description,
            tags
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total versions: {len(versions)}[/dim]\n")


def configuration_versioning_menu(es):
    """Main menu for configuration versioning."""
    console.print("\n[cyan]Configuration Versioning[/cyan]\n")

    while True:
        console.print("[bold]Select action:[/bold]")
        console.print("1) Capture current configuration")
        console.print("2) List all versions")
        console.print("3) View version details")
        console.print("4) Compare two versions")
        console.print("5) Restore a version")
        console.print("6) Delete a version")
        console.print("7) Export version to file")
        console.print("8) Import version from file")
        console.print("q) Back to menu\n")

        choice = safe_input("Select option: ").strip().lower()

        if choice in ("q", "quit", "back"):
            break

        if choice == "1":
            # Capture configuration
            description = safe_input("Enter description for this snapshot: ").strip()
            tags = safe_input("Enter tags (comma-separated, optional): ").strip()

            version_num = capture_cluster_configuration(es, description, tags)

            if version_num:
                log_operation("CONFIG_SNAPSHOT", [f"v{version_num}"], f"Captured configuration snapshot: {description}")

        elif choice == "2":
            # List versions
            display_config_versions()

        elif choice == "3":
            # View version details
            version_num = safe_input("Enter version number: ").strip()

            if not version_num.isdigit():
                console.print("\n[red]❌ Invalid version number[/red]\n")
                continue

            version = get_config_version(int(version_num))

            if not version:
                console.print("\n[red]❌ Version not found[/red]\n")
                continue

            # Display version info
            console.print(f"\n[bold cyan]Configuration Version {version_num}[/bold cyan]\n")
            console.print(f"Timestamp: {version['timestamp']}")
            console.print(f"Description: {version['description'] or 'N/A'}")
            console.print(f"Tags: {version['tags'] or 'N/A'}\n")

            # Show cluster settings
            if confirm_action("View cluster settings?"):
                syntax = Syntax(
                    json.dumps(version["cluster_settings"], indent=2),
                    "json",
                    theme="monokai",
                    line_numbers=True
                )
                console.print(Panel(syntax, title="Cluster Settings", border_style="cyan"))
                console.print()

        elif choice == "4":
            # Compare versions
            v1 = safe_input("Enter first version number: ").strip()
            v2 = safe_input("Enter second version number: ").strip()

            if not v1.isdigit() or not v2.isdigit():
                console.print("\n[red]❌ Invalid version numbers[/red]\n")
                continue

            version1 = get_config_version(int(v1))
            version2 = get_config_version(int(v2))

            if not version1 or not version2:
                console.print("\n[red]❌ One or both versions not found[/red]\n")
                continue

            differences = compare_config_versions(version1, version2)

            console.print(f"\n[bold cyan]Comparing v{v1} vs v{v2}[/bold cyan]\n")

            if differences["cluster_settings"]:
                console.print(f"[yellow]Cluster settings differences: {len(differences['cluster_settings'])}[/yellow]")

                if confirm_action("View detailed diff?"):
                    syntax = Syntax(
                        json.dumps(differences["cluster_settings"], indent=2),
                        "json",
                        theme="monokai",
                        line_numbers=True
                    )
                    console.print(Panel(syntax, title="Cluster Settings Diff", border_style="yellow"))
                    console.print()
            else:
                console.print("[green]No differences in cluster settings[/green]\n")

        elif choice == "5":
            # Restore version
            version_num = safe_input("Enter version number to restore: ").strip()

            if not version_num.isdigit():
                console.print("\n[red]❌ Invalid version number[/red]\n")
                continue

            version = get_config_version(int(version_num))

            if not version:
                console.print("\n[red]❌ Version not found[/red]\n")
                continue

            # Show preview
            console.print(f"\n[bold yellow]⚠️  You are about to restore configuration version {version_num}[/bold yellow]\n")
            console.print(f"Description: {version['description'] or 'N/A'}")
            console.print(f"Captured: {version['timestamp']}\n")

            if confirm_action("Preview changes before applying?"):
                result = restore_config_version(es, int(version_num), dry_run=True)
                console.print(f"\n{result['message']}\n")

            if confirm_action(f"Restore configuration version {version_num}?"):
                result = restore_config_version(es, int(version_num))

                if result["success"]:
                    console.print(f"\n[green]✅ {result['message']}[/green]\n")
                    log_operation("CONFIG_RESTORE", [f"v{version_num}"], f"Restored configuration version {version_num}")
                else:
                    console.print(f"\n[red]❌ {result['message']}[/red]\n")

        elif choice == "6":
            # Delete version
            version_num = safe_input("Enter version number to delete: ").strip()

            if not version_num.isdigit():
                console.print("\n[red]❌ Invalid version number[/red]\n")
                continue

            if confirm_action(f"Delete configuration version {version_num}?"):
                if delete_config_version(int(version_num)):
                    console.print(f"\n[green]✅ Version {version_num} deleted[/green]\n")
                    log_operation("CONFIG_DELETE", [f"v{version_num}"], f"Deleted configuration version {version_num}")
                else:
                    console.print("\n[red]❌ Version not found[/red]\n")

        elif choice == "7":
            # Export version
            version_num = safe_input("Enter version number to export: ").strip()

            if not version_num.isdigit():
                console.print("\n[red]❌ Invalid version number[/red]\n")
                continue

            filename = safe_input(f"Enter filename (default: config_v{version_num}.json): ").strip()
            if not filename:
                filename = f"config_v{version_num}.json"

            if export_config_version_to_file(int(version_num), filename):
                console.print(f"\n[green]✅ Exported version {version_num} to {filename}[/green]\n")
            else:
                console.print("\n[red]❌ Export failed[/red]\n")

        elif choice == "8":
            # Import version
            filename = safe_input("Enter filename to import: ").strip()

            if not filename:
                console.print("\n[yellow]⚠️  No filename provided[/yellow]\n")
                continue

            if not os.path.exists(filename):
                console.print(f"\n[red]❌ File not found: {filename}[/red]\n")
                continue

            version_num = import_config_version_from_file(filename)

            if version_num:
                console.print(f"\n[green]✅ Imported as version {version_num}[/green]\n")
                log_operation("CONFIG_IMPORT", [f"v{version_num}"], f"Imported configuration from {filename}")
            else:
                console.print("\n[red]❌ Import failed[/red]\n")

        else:
            console.print("\n[red]❌ Invalid option[/red]\n")

