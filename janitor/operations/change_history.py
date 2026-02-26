"""
Change History Enhancement for Elastic Janitor.
Enhanced operation history with filtering, search, and export capabilities.
"""
import os
import json
import csv
from datetime import datetime
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from ..config import console
from ..utils import safe_input, confirm_action, select_from_list, paginate_table


def parse_log_entry(line):
    """
    Parse a log entry line into structured data.
    
    Args:
        line: Log line string
        
    Returns:
        dict: Parsed log entry or None if parsing fails
    """
    try:
        parts = line.strip().split(" | ")
        if len(parts) < 3:
            return None
        
        timestamp = parts[0]
        operation_type = parts[1]
        description = parts[2] if len(parts) > 2 else ""
        resources = parts[3] if len(parts) > 3 else ""
        
        # Extract resource info
        resource_info = ""
        if resources.startswith("Resources: "):
            resource_info = resources.replace("Resources: ", "")
        
        # Detect dry-run operations
        is_dry_run = "[DRY-RUN]" in description or "Would " in description
        
        # Detect success/failure
        is_success = "ERROR" not in operation_type and "FAILED" not in operation_type
        
        return {
            "timestamp": timestamp,
            "operation_type": operation_type,
            "description": description,
            "resources": resource_info,
            "is_dry_run": is_dry_run,
            "is_success": is_success,
            "raw_line": line.strip()
        }
    except Exception:
        return None


def filter_log_entries(entries, operation_type=None, date_from=None, date_to=None, 
                       resource_type=None, search_term=None, success_only=None):
    """
    Filter log entries based on criteria.
    
    Args:
        entries: List of parsed log entries
        operation_type: Filter by operation type (e.g., "DELETE", "UPDATE")
        date_from: Filter entries from this date (datetime object)
        date_to: Filter entries to this date (datetime object)
        resource_type: Filter by resource type (e.g., "indices", "templates")
        search_term: Search term for resource names or descriptions
        success_only: Filter by success status (True/False/None)
        
    Returns:
        list: Filtered log entries
    """
    filtered = entries
    
    # Filter by operation type
    if operation_type:
        filtered = [e for e in filtered if operation_type.upper() in e["operation_type"].upper()]
    
    # Filter by date range
    if date_from or date_to:
        date_filtered = []
        for e in filtered:
            try:
                entry_date = datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S")
                if date_from and entry_date < date_from:
                    continue
                if date_to and entry_date > date_to:
                    continue
                date_filtered.append(e)
            except Exception:
                continue
        filtered = date_filtered
    
    # Filter by resource type
    if resource_type:
        filtered = [e for e in filtered if resource_type.lower() in e["operation_type"].lower() or 
                   resource_type.lower() in e["description"].lower()]
    
    # Search by term
    if search_term:
        search_lower = search_term.lower()
        filtered = [e for e in filtered if 
                   search_lower in e["description"].lower() or 
                   search_lower in e["resources"].lower() or
                   search_lower in e["operation_type"].lower()]
    
    # Filter by success status
    if success_only is not None:
        filtered = [e for e in filtered if e["is_success"] == success_only]
    
    return filtered


def display_filtered_history(entries, title="Operation History"):
    """Display filtered history in a Rich table with pagination."""
    if not entries:
        console.print("\n[yellow]No entries found matching the criteria.[/yellow]\n")
        return
    
    # Define columns for the table
    columns = [
        {"name": "Timestamp", "style": "cyan", "width": 20},
        {"name": "Operation", "style": "yellow", "width": 25},
        {"name": "Description", "style": "white", "width": 40},
        {"name": "Status", "style": "white", "width": 15}
    ]
    
    # Build rows from entries
    rows = []
    for entry in entries:
        timestamp = entry["timestamp"]
        operation = entry["operation_type"]
        description = entry["description"][:37] + "..." if len(entry["description"]) > 40 else entry["description"]
        
        # Status column
        status_parts = []
        if entry["is_dry_run"]:
            status_parts.append("[dim][DRY-RUN][/dim]")
        if entry["is_success"]:
            status_parts.append("[green]✓[/green]")
        else:
            status_parts.append("[red]✗[/red]")
        
        status = " ".join(status_parts)
        rows.append((timestamp, operation, description, status))
    
    # Display with pagination
    paginate_table(rows, columns, page_size=20, title=title)


def export_history_to_json(entries, filename):
    """Export history entries to JSON format."""
    try:
        with open(filename, "w") as f:
            json.dump(entries, f, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]❌ Error exporting to JSON: {e}[/red]")
        return False


def export_history_to_csv(entries, filename):
    """Export history entries to CSV format."""
    try:
        with open(filename, "w", newline="") as f:
            if not entries:
                return True

            fieldnames = ["timestamp", "operation_type", "description", "resources", "is_dry_run", "is_success"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()
            for entry in entries:
                writer.writerow({
                    "timestamp": entry["timestamp"],
                    "operation_type": entry["operation_type"],
                    "description": entry["description"],
                    "resources": entry["resources"],
                    "is_dry_run": entry["is_dry_run"],
                    "is_success": entry["is_success"]
                })
        return True
    except Exception as e:
        console.print(f"[red]❌ Error exporting to CSV: {e}[/red]")
        return False


def enhanced_operation_history():
    """Enhanced operation history with filtering, search, and export."""
    console.print("\n[cyan]Enhanced Operation History[/cyan]\n")

    # Check if log file exists
    log_file = "janitor_history.log"

    if not os.path.exists(log_file):
        console.print("[yellow]🟡 No operation history found. The log file will be created when operations are performed.[/yellow]\n")
        return

    try:
        # Read and parse log file
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Loading operation history..."),
            transient=True,
        ) as progress:
            progress.add_task("load", total=None)

            with open(log_file, "r") as f:
                lines = f.readlines()

        if not lines:
            console.print("[yellow]🟡 Operation history is empty.[/yellow]\n")
            return

        # Parse all entries
        all_entries = []
        for line in lines:
            entry = parse_log_entry(line)
            if entry:
                all_entries.append(entry)

        console.print(f"[dim]Loaded {len(all_entries)} operations[/dim]\n")

        # Main menu loop
        while True:
            console.print("[bold]Select action:[/bold]")
            console.print("1) View all history")
            console.print("2) Filter by operation type")
            console.print("3) Filter by date range")
            console.print("4) Filter by resource type")
            console.print("5) Search by term")
            console.print("6) Filter by success/failure")
            console.print("7) Export to JSON")
            console.print("8) Export to CSV")
            console.print("9) Advanced filtering (combine filters)")
            console.print("q) Back to menu\n")

            choice = safe_input("Select option: ").strip().lower()

            if choice in ("q", "quit", "back"):
                break

            filtered_entries = all_entries

            if choice == "1":
                # View all
                n_input = safe_input("Show last how many entries? (default 50, 'all' for all): ").strip().lower()
                if n_input == "all":
                    filtered_entries = all_entries
                else:
                    n = int(n_input) if n_input and n_input.isdigit() else 50
                    filtered_entries = all_entries[-n:]

                display_filtered_history(filtered_entries)

            elif choice == "2":
                # Filter by operation type
                console.print("\n[bold]Common operation types:[/bold]")
                console.print("DELETE, UPDATE, CREATE, CLOSE, OPEN, BATCH, ROLLBACK\n")

                op_type = safe_input("Enter operation type (or part of it): ").strip()
                if op_type:
                    filtered_entries = filter_log_entries(all_entries, operation_type=op_type)
                    display_filtered_history(filtered_entries, f"Operations: {op_type}")

            elif choice == "3":
                # Filter by date range
                console.print("\n[bold]Date format: YYYY-MM-DD[/bold]\n")

                date_from_str = safe_input("From date (leave empty for no limit): ").strip()
                date_to_str = safe_input("To date (leave empty for no limit): ").strip()

                date_from = None
                date_to = None

                try:
                    if date_from_str:
                        date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
                    if date_to_str:
                        date_to = datetime.strptime(date_to_str, "%Y-%m-%d")

                    filtered_entries = filter_log_entries(all_entries, date_from=date_from, date_to=date_to)
                    display_filtered_history(filtered_entries, f"Date Range: {date_from_str or 'start'} to {date_to_str or 'end'}")
                except ValueError:
                    console.print("\n[red]❌ Invalid date format. Use YYYY-MM-DD[/red]\n")

            elif choice == "4":
                # Filter by resource type
                console.print("\n[bold]Resource types:[/bold]")
                console.print("indices, templates, snapshots, pipelines, data_streams\n")

                resource_type = safe_input("Enter resource type: ").strip()
                if resource_type:
                    filtered_entries = filter_log_entries(all_entries, resource_type=resource_type)
                    display_filtered_history(filtered_entries, f"Resource Type: {resource_type}")

            elif choice == "5":
                # Search by term
                search_term = safe_input("Enter search term: ").strip()
                if search_term:
                    filtered_entries = filter_log_entries(all_entries, search_term=search_term)
                    display_filtered_history(filtered_entries, f"Search: {search_term}")

            elif choice == "6":
                # Filter by success/failure
                console.print("\n[bold]Filter by:[/bold]")
                console.print("1) Success only")
                console.print("2) Failures only")
                console.print("3) All\n")

                status_choice = safe_input("Select: ").strip()

                if status_choice == "1":
                    filtered_entries = filter_log_entries(all_entries, success_only=True)
                    display_filtered_history(filtered_entries, "Successful Operations")
                elif status_choice == "2":
                    filtered_entries = filter_log_entries(all_entries, success_only=False)
                    display_filtered_history(filtered_entries, "Failed Operations")
                else:
                    display_filtered_history(all_entries)

            elif choice == "7":
                # Export to JSON
                filename = safe_input("Enter filename (default: history_export.json): ").strip()
                if not filename:
                    filename = "history_export.json"

                if export_history_to_json(all_entries, filename):
                    console.print(f"\n[green]✅ Exported {len(all_entries)} entries to {filename}[/green]\n")

            elif choice == "8":
                # Export to CSV
                filename = safe_input("Enter filename (default: history_export.csv): ").strip()
                if not filename:
                    filename = "history_export.csv"

                if export_history_to_csv(all_entries, filename):
                    console.print(f"\n[green]✅ Exported {len(all_entries)} entries to {filename}[/green]\n")

            elif choice == "9":
                # Advanced filtering
                console.print("\n[cyan]Advanced Filtering[/cyan]\n")

                op_type = safe_input("Operation type (leave empty to skip): ").strip() or None
                resource_type = safe_input("Resource type (leave empty to skip): ").strip() or None
                search_term = safe_input("Search term (leave empty to skip): ").strip() or None

                filtered_entries = filter_log_entries(
                    all_entries,
                    operation_type=op_type,
                    resource_type=resource_type,
                    search_term=search_term
                )

                display_filtered_history(filtered_entries, "Advanced Filter Results")

                # Offer export
                if filtered_entries and confirm_action("Export these results?"):
                    console.print("\n1) JSON\n2) CSV\n")
                    export_choice = safe_input("Select format: ").strip()

                    if export_choice == "1":
                        filename = safe_input("Filename (default: filtered_history.json): ").strip() or "filtered_history.json"
                        if export_history_to_json(filtered_entries, filename):
                            console.print(f"\n[green]✅ Exported {len(filtered_entries)} entries to {filename}[/green]\n")
                    elif export_choice == "2":
                        filename = safe_input("Filename (default: filtered_history.csv): ").strip() or "filtered_history.csv"
                        if export_history_to_csv(filtered_entries, filename):
                            console.print(f"\n[green]✅ Exported {len(filtered_entries)} entries to {filename}[/green]\n")

            else:
                console.print("\n[red]❌ Invalid option.[/red]\n")

    except Exception as e:
        console.print(f"\n[red]❌ ERROR: Could not read operation history: {e}[/red]\n")

