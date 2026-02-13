"""
Operation history logging utility for Elastic Janitor.
Logs all operations (deletions, modifications) to a local file.
"""
import os
from datetime import datetime


def log_operation(operation_type, affected_resources, description=""):
    """
    Log an operation to the history file.
    
    Args:
        operation_type: Type of operation (e.g., "DELETE_INDEX", "MODIFY_SETTINGS")
        affected_resources: List of affected resources or single resource name
        description: Optional description of the operation
    """
    log_file = "janitor_history.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Convert affected_resources to list if it's a string
    if isinstance(affected_resources, str):
        affected_resources = [affected_resources]
    
    # Format the log entry
    resources_str = ", ".join(affected_resources) if len(affected_resources) <= 5 else f"{len(affected_resources)} items"
    log_entry = f"{timestamp} | {operation_type} | {description} | Resources: {resources_str}\n"
    
    try:
        # Append to log file
        with open(log_file, "a") as f:
            f.write(log_entry)
    except Exception as e:
        # Silently fail if logging fails - don't interrupt the main operation
        pass


def get_recent_operations(n=20):
    """
    Get the most recent N operations from the log.
    
    Args:
        n: Number of recent operations to retrieve
        
    Returns:
        List of log entries
    """
    log_file = "janitor_history.log"
    
    if not os.path.exists(log_file):
        return []
    
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        
        return lines[-n:] if len(lines) > n else lines
    except Exception:
        return []


def clear_history():
    """Clear the operation history log."""
    log_file = "janitor_history.log"
    
    try:
        if os.path.exists(log_file):
            os.remove(log_file)
        return True
    except Exception:
        return False

