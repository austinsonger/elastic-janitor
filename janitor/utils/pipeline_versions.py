"""
Pipeline Version Control System for Elastic Janitor.
Manages versioning and rollback of ingest pipelines using SQLite.
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from ..config import console


# Database path - store in user's home directory
DB_DIR = Path.home() / ".elastic-janitor"
DB_PATH = DB_DIR / "pipeline_versions.db"
MAX_VERSIONS_PER_PIPELINE = 10


def _get_db_connection():
    """Get database connection, creating database if needed."""
    # Ensure directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def _init_database():
    """Initialize database schema if not exists."""
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_name TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            configuration TEXT NOT NULL,
            comment TEXT,
            is_known_good BOOLEAN DEFAULT 0,
            UNIQUE(pipeline_name, version_number)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pipeline_name
        ON pipeline_versions(pipeline_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON pipeline_versions(timestamp DESC)
    """)

    conn.commit()
    conn.close()


def save_pipeline_version(pipeline_name, configuration, comment=None, is_known_good=False):
    """
    Save a new version of a pipeline.

    Args:
        pipeline_name: Name of the pipeline
        configuration: Full pipeline configuration (dict)
        comment: Optional user comment
        is_known_good: Whether this is marked as a known-good version

    Returns:
        int: Version number of the saved version
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    # Get next version number
    cursor.execute("""
        SELECT COALESCE(MAX(version_number), 0) + 1 as next_version
        FROM pipeline_versions
        WHERE pipeline_name = ?
    """, (pipeline_name,))

    version_number = cursor.fetchone()["next_version"]

    # Save new version
    timestamp = datetime.now().isoformat()
    config_json = json.dumps(configuration, indent=2)

    cursor.execute("""
        INSERT INTO pipeline_versions
        (pipeline_name, version_number, timestamp, configuration, comment, is_known_good)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (pipeline_name, version_number, timestamp, config_json, comment, is_known_good))

    conn.commit()

    # Clean up old versions (keep only MAX_VERSIONS_PER_PIPELINE)
    cursor.execute("""
        DELETE FROM pipeline_versions
        WHERE pipeline_name = ?
        AND version_number NOT IN (
            SELECT version_number
            FROM pipeline_versions
            WHERE pipeline_name = ?
            ORDER BY version_number DESC
            LIMIT ?
        )
    """, (pipeline_name, pipeline_name, MAX_VERSIONS_PER_PIPELINE))

    conn.commit()
    conn.close()

    return version_number


def get_pipeline_versions(pipeline_name):
    """
    Get all versions for a pipeline.

    Args:
        pipeline_name: Name of the pipeline

    Returns:
        list: List of version dictionaries
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, pipeline_name, version_number, timestamp, configuration, comment, is_known_good
        FROM pipeline_versions
        WHERE pipeline_name = ?
        ORDER BY version_number DESC
    """, (pipeline_name,))

    versions = []
    for row in cursor.fetchall():
        versions.append({
            "id": row["id"],
            "pipeline_name": row["pipeline_name"],
            "version_number": row["version_number"],
            "timestamp": row["timestamp"],
            "configuration": json.loads(row["configuration"]),
            "comment": row["comment"],
            "is_known_good": bool(row["is_known_good"])
        })




def get_pipeline_version(pipeline_name, version_number):
    """
    Get a specific version of a pipeline.

    Args:
        pipeline_name: Name of the pipeline
        version_number: Version number to retrieve

    Returns:
        dict: Version dictionary or None if not found
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, pipeline_name, version_number, timestamp, configuration, comment, is_known_good
        FROM pipeline_versions
        WHERE pipeline_name = ? AND version_number = ?
    """, (pipeline_name, version_number))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "pipeline_name": row["pipeline_name"],
            "version_number": row["version_number"],
            "timestamp": row["timestamp"],
            "configuration": json.loads(row["configuration"]),
            "comment": row["comment"],
            "is_known_good": bool(row["is_known_good"])
        }
    return None


def get_last_known_good_version(pipeline_name):
    """
    Get the most recent known-good version of a pipeline.

    Args:
        pipeline_name: Name of the pipeline

    Returns:
        dict: Version dictionary or None if no known-good version exists
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, pipeline_name, version_number, timestamp, configuration, comment, is_known_good
        FROM pipeline_versions
        WHERE pipeline_name = ? AND is_known_good = 1
        ORDER BY version_number DESC
        LIMIT 1
    """, (pipeline_name,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "pipeline_name": row["pipeline_name"],
            "version_number": row["version_number"],
            "timestamp": row["timestamp"],
            "configuration": json.loads(row["configuration"]),
            "comment": row["comment"],
            "is_known_good": bool(row["is_known_good"])
        }
    return None


def delete_pipeline_versions(pipeline_name):
    """
    Delete all versions for a pipeline.

    Args:
        pipeline_name: Name of the pipeline

    Returns:
        int: Number of versions deleted
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM pipeline_versions
        WHERE pipeline_name = ?
    """, (pipeline_name,))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count


def get_all_versioned_pipelines():
    """
    Get list of all pipelines that have versions stored.

    Returns:
        list: List of pipeline names
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT pipeline_name
        FROM pipeline_versions
        ORDER BY pipeline_name
    """)

    pipelines = [row["pipeline_name"] for row in cursor.fetchall()]
    conn.close()

    return pipelines


def get_version_count(pipeline_name):
    """
    Get the number of versions stored for a pipeline.

    Args:
        pipeline_name: Name of the pipeline

    Returns:
        int: Number of versions
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) as count
        FROM pipeline_versions
        WHERE pipeline_name = ?
    """, (pipeline_name,))

    count = cursor.fetchone()["count"]
    conn.close()

    return count

