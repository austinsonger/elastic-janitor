"""
Rollback Capabilities for Elastic Janitor.
Track and rollback destructive operations including index deletions, bulk setting changes, and data stream deletions.
"""
import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box
from ..config import console, PROTECT_SYSTEM, GOD_MODE
from ..utils import confirm_action, safe_input, show_breadcrumb, select_from_list
from ..utils.history_logger import log_operation


# Database path - store in user's home directory
DB_DIR = Path.home() / ".elastic-janitor"
ROLLBACK_DB_PATH = DB_DIR / "rollback_operations.db"


def _get_rollback_db_connection():
    """Get database connection for rollback operations, creating database if needed."""
    # Ensure directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(ROLLBACK_DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def _init_rollback_database():
    """Initialize rollback database schema if not exists."""
    conn = _get_rollback_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rollback_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id TEXT UNIQUE NOT NULL,
            operation_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            target_resources TEXT NOT NULL,
            previous_state TEXT,
            operation_params TEXT,
            user_confirmed BOOLEAN DEFAULT 1,
            rollback_available BOOLEAN DEFAULT 1,
            rollback_reason TEXT,
            rolled_back BOOLEAN DEFAULT 0,
            rollback_timestamp TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_operation_type
        ON rollback_operations(operation_type)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON rollback_operations(timestamp DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rollback_available
        ON rollback_operations(rollback_available, rolled_back)
    """)
    
    conn.commit()
    conn.close()


def track_destructive_operation(operation_type, target_resources, previous_state=None, 
                                operation_params=None, user_confirmed=True):
    """
    Track a destructive operation for potential rollback.
    
    Args:
        operation_type: Type of operation (DELETE_INDEX, BULK_SETTINGS_CHANGE, DELETE_DATA_STREAM, etc.)
        target_resources: List of affected resource names
        previous_state: Previous configuration/state before the change (dict or None)
        operation_params: Parameters used for the operation (dict or None)
        user_confirmed: Whether user confirmed the operation
        
    Returns:
        str: Operation ID for tracking
    """
    _init_rollback_database()
    
    conn = _get_rollback_db_connection()
    cursor = conn.cursor()
    
    # Generate operation ID
    operation_id = f"{operation_type}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    timestamp = datetime.now().isoformat()
    
    # Convert to JSON
    resources_json = json.dumps(target_resources if isinstance(target_resources, list) else [target_resources])
    previous_state_json = json.dumps(previous_state) if previous_state else None
    params_json = json.dumps(operation_params) if operation_params else None
    
    # Determine rollback availability
    rollback_available = True
    rollback_reason = None
    
    if operation_type == "DELETE_INDEX" and not previous_state:
        rollback_available = False
        rollback_reason = "No snapshot information available"
    
    cursor.execute("""
        INSERT INTO rollback_operations
        (operation_id, operation_type, timestamp, target_resources, previous_state, 
         operation_params, user_confirmed, rollback_available, rollback_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (operation_id, operation_type, timestamp, resources_json, previous_state_json,
          params_json, user_confirmed, rollback_available, rollback_reason))
    
    conn.commit()
    conn.close()
    
    return operation_id


def get_rollback_operations(limit=50, operation_type=None, rollback_available_only=False):
    """
    Get tracked rollback operations.
    
    Args:
        limit: Maximum number of operations to retrieve
        operation_type: Filter by operation type (optional)
        rollback_available_only: Only show operations that can be rolled back
        
    Returns:
        list: List of operation dictionaries
    """
    _init_rollback_database()
    
    conn = _get_rollback_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM rollback_operations WHERE 1=1"
    params = []
    
    if operation_type:
        query += " AND operation_type = ?"
        params.append(operation_type)
    
    if rollback_available_only:
        query += " AND rollback_available = 1 AND rolled_back = 0"
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)

    operations = []
    for row in cursor.fetchall():
        operations.append({
            "id": row["id"],
            "operation_id": row["operation_id"],
            "operation_type": row["operation_type"],
            "timestamp": row["timestamp"],
            "target_resources": json.loads(row["target_resources"]),
            "previous_state": json.loads(row["previous_state"]) if row["previous_state"] else None,
            "operation_params": json.loads(row["operation_params"]) if row["operation_params"] else None,
            "user_confirmed": bool(row["user_confirmed"]),
            "rollback_available": bool(row["rollback_available"]),
            "rollback_reason": row["rollback_reason"],
            "rolled_back": bool(row["rolled_back"]),
            "rollback_timestamp": row["rollback_timestamp"]
        })

    conn.close()
    return operations


def mark_operation_rolled_back(operation_id):
    """Mark an operation as rolled back."""
    _init_rollback_database()

    conn = _get_rollback_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rollback_operations
        SET rolled_back = 1, rollback_timestamp = ?
        WHERE operation_id = ?
    """, (datetime.now().isoformat(), operation_id))

    conn.commit()
    conn.close()


def rollback_operation(es, operation_id):
    """
    Rollback a specific operation.

    Args:
        es: Elasticsearch client
        operation_id: ID of the operation to rollback

    Returns:
        dict: Result with success status and messages
    """
    _init_rollback_database()

    conn = _get_rollback_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM rollback_operations WHERE operation_id = ?", (operation_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"success": False, "message": "Operation not found"}

    if row["rolled_back"]:
        return {"success": False, "message": "Operation already rolled back"}

    if not row["rollback_available"]:
        return {"success": False, "message": f"Rollback not available: {row['rollback_reason']}"}

    operation_type = row["operation_type"]
    target_resources = json.loads(row["target_resources"])
    previous_state = json.loads(row["previous_state"]) if row["previous_state"] else None

    try:
        if operation_type == "DELETE_INDEX":
            return _rollback_index_deletion(es, target_resources, previous_state)
        elif operation_type == "BULK_SETTINGS_CHANGE":
            return _rollback_settings_change(es, target_resources, previous_state)
        elif operation_type == "DELETE_DATA_STREAM":
            return _rollback_data_stream_deletion(es, target_resources, previous_state)
        elif operation_type in ["CLOSE_INDICES", "OPEN_INDICES"]:
            return _rollback_index_state_change(es, operation_type, target_resources, previous_state)
        else:
            return {"success": False, "message": f"Rollback not implemented for operation type: {operation_type}"}

    except Exception as e:
        return {"success": False, "message": f"Rollback failed: {str(e)}"}


def _rollback_index_deletion(es, target_resources, previous_state):
    """Rollback index deletion by restoring from snapshot."""
    if not previous_state or "snapshot_repo" not in previous_state:
        return {"success": False, "message": "No snapshot information available for restore"}

    snapshot_repo = previous_state["snapshot_repo"]
    snapshot_name = previous_state["snapshot_name"]

    console.print(f"\n[cyan]Attempting to restore {len(target_resources)} index(es) from snapshot...[/cyan]\n")
    console.print(f"Repository: {snapshot_repo}")
    console.print(f"Snapshot: {snapshot_name}\n")

    if not GOD_MODE:
        console.print("[yellow]DRY RUN: Would restore indices from snapshot[/yellow]\n")
        return {"success": True, "message": "DRY RUN: Restore would be performed"}

    try:
        # Restore indices from snapshot
        restore_body = {
            "indices": ",".join(target_resources),
            "ignore_unavailable": True,
            "include_global_state": False
        }

        es.snapshot.restore(repository=snapshot_repo, snapshot=snapshot_name, body=restore_body)

        return {"success": True, "message": f"Successfully restored {len(target_resources)} index(es) from snapshot"}

    except Exception as e:
        return {"success": False, "message": f"Failed to restore from snapshot: {str(e)}"}


def _rollback_settings_change(es, target_resources, previous_state):
    """Rollback bulk settings changes."""
    if not previous_state or "settings" not in previous_state:
        return {"success": False, "message": "No previous settings available"}

    settings = previous_state["settings"]

    console.print(f"\n[cyan]Restoring previous settings for {len(target_resources)} index(es)...[/cyan]\n")

    if not GOD_MODE:
        console.print("[yellow]DRY RUN: Would restore previous settings[/yellow]\n")
        return {"success": True, "message": "DRY RUN: Settings would be restored"}

    success_count = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Restoring settings..."),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("restore", total=len(target_resources))

        for idx in target_resources:
            try:
                es.indices.put_settings(index=idx, body=settings)
                success_count += 1
            except Exception as e:
                errors.append(f"{idx}: {str(e)}")
            progress.update(task, advance=1)

    if errors:
        return {"success": False, "message": f"Restored {success_count}/{len(target_resources)} indices. Errors: {'; '.join(errors[:3])}"}

    return {"success": True, "message": f"Successfully restored settings for {success_count} index(es)"}


def _rollback_data_stream_deletion(es, target_resources, previous_state):
    """Rollback data stream deletion."""
    return {"success": False, "message": "Data stream deletion rollback requires manual recreation with proper template"}


def _rollback_index_state_change(es, operation_type, target_resources, previous_state):
    """Rollback index open/close operations."""
    # Reverse the operation
    reverse_operation = "OPEN_INDICES" if operation_type == "CLOSE_INDICES" else "CLOSE_INDICES"
    action = "Opening" if reverse_operation == "OPEN_INDICES" else "Closing"

    console.print(f"\n[cyan]{action} {len(target_resources)} index(es)...[/cyan]\n")

    if not GOD_MODE:
        console.print(f"[yellow]DRY RUN: Would {action.lower()} indices[/yellow]\n")
        return {"success": True, "message": f"DRY RUN: Indices would be {action.lower()}"}

    success_count = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]{action}..."),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("rollback", total=len(target_resources))

        for idx in target_resources:
            try:
                if reverse_operation == "OPEN_INDICES":
                    es.indices.open(index=idx)
                else:
                    es.indices.close(index=idx)
                success_count += 1
            except Exception as e:
                errors.append(f"{idx}: {str(e)}")
            progress.update(task, advance=1)

    if errors:
        return {"success": False, "message": f"{action} {success_count}/{len(target_resources)} indices. Errors: {'; '.join(errors[:3])}"}

    return {"success": True, "message": f"Successfully {action.lower()} {success_count} index(es)"}


def display_rollback_history(es):
    """Display rollback history in a Rich table."""
    console.print("\n[cyan]Rollback History[/cyan]\n")

    # Get filter options
    console.print("[bold]Filter options:[/bold]")
    console.print("1) Show all operations")
    console.print("2) Show only rollback-available operations")
    console.print("3) Filter by operation type")
    console.print("q) Cancel\n")

    choice = safe_input("Select option: ").strip().lower()

    if choice in ("q", "quit", "cancel"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    operation_type_filter = None
    rollback_available_only = False

    if choice == "2":
        rollback_available_only = True
    elif choice == "3":
        console.print("\n[bold]Operation types:[/bold]")
        console.print("1) DELETE_INDEX")
        console.print("2) BULK_SETTINGS_CHANGE")
        console.print("3) DELETE_DATA_STREAM")
        console.print("4) CLOSE_INDICES")
        console.print("5) OPEN_INDICES\n")

        type_choice = safe_input("Select type: ").strip()
        type_map = {
            "1": "DELETE_INDEX",
            "2": "BULK_SETTINGS_CHANGE",
            "3": "DELETE_DATA_STREAM",
            "4": "CLOSE_INDICES",
            "5": "OPEN_INDICES"
        }
        operation_type_filter = type_map.get(type_choice)

    # Get operations
    operations = get_rollback_operations(
        limit=100,
        operation_type=operation_type_filter,
        rollback_available_only=rollback_available_only
    )

    if not operations:
        console.print("\n[yellow]🟡 No operations found.[/yellow]\n")
        return

    # Display table
    table = Table(title="Rollback Operations", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Timestamp", style="cyan", width=20)
    table.add_column("Operation Type", style="yellow", width=25)
    table.add_column("Resources", style="white", width=15)
    table.add_column("Rollback Status", style="white", width=20)
    table.add_column("Reason", style="dim", width=30)

    for op in operations:
        op_id = str(op["id"])
        timestamp = op["timestamp"][:19]  # Truncate to datetime
        op_type = op["operation_type"]
        resource_count = len(op["target_resources"])

        # Determine rollback status
        if op["rolled_back"]:
            status = "[green]✓ Rolled back[/green]"
            reason = op["rollback_timestamp"][:19] if op["rollback_timestamp"] else ""
        elif op["rollback_available"]:
            status = "[yellow]Available[/yellow]"
            reason = ""
        else:
            status = "[red]Not available[/red]"
            reason = op["rollback_reason"] or ""

        table.add_row(op_id, timestamp, op_type, f"{resource_count} item(s)", status, reason)

    console.print(table)
    console.print()

    # Offer to perform rollback
    if confirm_action("Perform a rollback?"):
        perform_rollback_interactive(es, operations)


def perform_rollback_interactive(es, operations):
    """Interactive rollback selection and execution."""
    # Filter to only rollback-available operations
    available_ops = [op for op in operations if op["rollback_available"] and not op["rolled_back"]]

    if not available_ops:
        console.print("\n[yellow]🟡 No operations available for rollback.[/yellow]\n")
        return

    # Create selection list
    choices = []
    for op in available_ops:
        timestamp = op["timestamp"][:19]
        op_type = op["operation_type"]
        resource_count = len(op["target_resources"])
        choices.append(f"[{op['id']}] {timestamp} - {op_type} ({resource_count} resources)")

    selected = select_from_list(
        "Select operation to rollback:",
        choices,
        multi=False
    )

    if not selected:
        console.print("\n[yellow]⚠️  No operation selected.[/yellow]\n")
        return

    # Extract operation ID from selection
    selected_id = int(selected[0].split("]")[0][1:])
    selected_op = next(op for op in available_ops if op["id"] == selected_id)

    # Display operation details
    console.print(f"\n[bold cyan]Operation Details:[/bold cyan]")
    console.print(f"Type: {selected_op['operation_type']}")
    console.print(f"Timestamp: {selected_op['timestamp']}")
    console.print(f"Resources: {', '.join(selected_op['target_resources'][:5])}")
    if len(selected_op['target_resources']) > 5:
        console.print(f"  ... and {len(selected_op['target_resources']) - 5} more")
    console.print()

    # Confirm rollback
    if not confirm_action(f"Rollback this operation?"):
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return

    # Perform rollback
    result = rollback_operation(es, selected_op["operation_id"])

    if result["success"]:
        console.print(f"\n[green]✅ {result['message']}[/green]\n")

        # Mark as rolled back
        if GOD_MODE:
            mark_operation_rolled_back(selected_op["operation_id"])

        # Log the rollback
        log_operation(
            "ROLLBACK",
            selected_op["target_resources"],
            f"Rolled back {selected_op['operation_type']}"
        )
    else:
        console.print(f"\n[red]❌ {result['message']}[/red]\n")

