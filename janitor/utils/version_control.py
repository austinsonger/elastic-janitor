"""
Generic Version Control System for Elastic Janitor.
Manages versioning and rollback of Elasticsearch resources (pipelines, templates, etc.) using SQLite.
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from ..config import console


# Database path - store in user's home directory
DB_DIR = Path.home() / ".elastic-janitor"
DB_PATH = DB_DIR / "elastic_versions.db"
MAX_VERSIONS_PER_RESOURCE = 10

# Resource type constants
RESOURCE_TYPE_PIPELINE = "ingest_pipeline"
RESOURCE_TYPE_INDEX_TEMPLATE = "index_template"
RESOURCE_TYPE_COMPONENT_TEMPLATE = "component_template"


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
        CREATE TABLE IF NOT EXISTS resource_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_type TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            configuration TEXT NOT NULL,
            comment TEXT,
            is_known_good BOOLEAN DEFAULT 0,
            UNIQUE(resource_type, resource_name, version_number)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_resource_type_name
        ON resource_versions(resource_type, resource_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON resource_versions(timestamp DESC)
    """)

    # Create dependency tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_resource_type TEXT NOT NULL,
            parent_resource_name TEXT NOT NULL,
            parent_version_number INTEGER NOT NULL,
            dependency_resource_type TEXT NOT NULL,
            dependency_resource_name TEXT NOT NULL,
            dependency_version_number INTEGER,
            dependency_configuration TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            FOREIGN KEY (parent_resource_type, parent_resource_name, parent_version_number)
                REFERENCES resource_versions(resource_type, resource_name, version_number)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_parent_resource
        ON resource_dependencies(parent_resource_type, parent_resource_name, parent_version_number)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dependency_resource
        ON resource_dependencies(dependency_resource_type, dependency_resource_name)
    """)

    conn.commit()
    conn.close()


def _migrate_from_pipeline_versions():
    """
    Migrate data from old pipeline_versions.db to new schema.
    This is a one-time migration for backward compatibility.
    """
    old_db_path = DB_DIR / "pipeline_versions.db"

    # Check if old database exists
    if not old_db_path.exists():
        return

    # Check if migration already done
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM resource_versions WHERE resource_type = ?",
                   (RESOURCE_TYPE_PIPELINE,))
    if cursor.fetchone()["count"] > 0:
        conn.close()
        return  # Already migrated

    conn.close()

    # Perform migration
    try:
        old_conn = sqlite3.connect(old_db_path)
        old_conn.row_factory = sqlite3.Row
        old_cursor = old_conn.cursor()

        # Check if old table exists
        old_cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='pipeline_versions'
        """)

        if not old_cursor.fetchone():
            old_conn.close()
            return

        # Fetch all old data
        old_cursor.execute("""
            SELECT pipeline_name, version_number, timestamp, configuration, comment, is_known_good
            FROM pipeline_versions
            ORDER BY pipeline_name, version_number
        """)

        old_data = old_cursor.fetchall()
        old_conn.close()

        if not old_data:
            return

        # Insert into new database
        conn = _get_db_connection()
        cursor = conn.cursor()

        for row in old_data:
            cursor.execute("""
                INSERT OR IGNORE INTO resource_versions
                (resource_type, resource_name, version_number, timestamp, configuration, comment, is_known_good)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (RESOURCE_TYPE_PIPELINE, row["pipeline_name"], row["version_number"],
                  row["timestamp"], row["configuration"], row["comment"], row["is_known_good"]))

        conn.commit()
        conn.close()

        console.print(f"[green]✓ Migrated {len(old_data)} pipeline versions to new database[/green]")

    except Exception as e:
        console.print(f"[yellow]⚠️  Migration warning: {str(e)}[/yellow]")


def save_resource_version(resource_type, resource_name, configuration, comment=None, is_known_good=False):
    """
    Save a new version of a resource.

    Args:
        resource_type: Type of resource (RESOURCE_TYPE_PIPELINE, RESOURCE_TYPE_INDEX_TEMPLATE, etc.)
        resource_name: Name of the resource
        configuration: Full resource configuration (dict)
        comment: Optional user comment
        is_known_good: Whether this is marked as a known-good version

    Returns:
        int: Version number of the saved version
    """
    _init_database()
    _migrate_from_pipeline_versions()

    conn = _get_db_connection()
    cursor = conn.cursor()

    # Get next version number
    cursor.execute("""
        SELECT COALESCE(MAX(version_number), 0) + 1 as next_version
        FROM resource_versions
        WHERE resource_type = ? AND resource_name = ?
    """, (resource_type, resource_name))

    version_number = cursor.fetchone()["next_version"]

    # Save new version
    timestamp = datetime.now().isoformat()
    config_json = json.dumps(configuration, indent=2)

    cursor.execute("""
        INSERT INTO resource_versions
        (resource_type, resource_name, version_number, timestamp, configuration, comment, is_known_good)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (resource_type, resource_name, version_number, timestamp, config_json, comment, is_known_good))

    conn.commit()

    # Clean up old versions (keep only MAX_VERSIONS_PER_RESOURCE)
    cursor.execute("""
        DELETE FROM resource_versions
        WHERE resource_type = ? AND resource_name = ?
        AND version_number NOT IN (
            SELECT version_number
            FROM resource_versions
            WHERE resource_type = ? AND resource_name = ?
            ORDER BY version_number DESC
            LIMIT ?
        )
    """, (resource_type, resource_name, resource_type, resource_name, MAX_VERSIONS_PER_RESOURCE))

    conn.commit()
    conn.close()

    return version_number


def get_resource_versions(resource_type, resource_name):
    """
    Get all versions for a resource.

    Args:
        resource_type: Type of resource
        resource_name: Name of the resource

    Returns:
        list: List of version dictionaries
    """
    _init_database()
    _migrate_from_pipeline_versions()

    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, resource_type, resource_name, version_number, timestamp, configuration, comment, is_known_good
        FROM resource_versions
        WHERE resource_type = ? AND resource_name = ?
        ORDER BY version_number DESC
    """, (resource_type, resource_name))

    versions = []
    for row in cursor.fetchall():
        versions.append({
            "id": row["id"],
            "resource_type": row["resource_type"],
            "resource_name": row["resource_name"],
            "version_number": row["version_number"],
            "timestamp": row["timestamp"],
            "configuration": json.loads(row["configuration"]),
            "comment": row["comment"],
            "is_known_good": bool(row["is_known_good"])
        })

    conn.close()
    return versions


def get_resource_version(resource_type, resource_name, version_number):
    """
    Get a specific version of a resource.

    Args:
        resource_type: Type of resource
        resource_name: Name of the resource
        version_number: Version number to retrieve

    Returns:
        dict: Version dictionary or None if not found
    """
    _init_database()
    _migrate_from_pipeline_versions()

    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, resource_type, resource_name, version_number, timestamp, configuration, comment, is_known_good
        FROM resource_versions
        WHERE resource_type = ? AND resource_name = ? AND version_number = ?
    """, (resource_type, resource_name, version_number))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "resource_type": row["resource_type"],
            "resource_name": row["resource_name"],
            "version_number": row["version_number"],
            "timestamp": row["timestamp"],
            "configuration": json.loads(row["configuration"]),
            "comment": row["comment"],
            "is_known_good": bool(row["is_known_good"])
        }
    return None


def get_last_known_good_version(resource_type, resource_name):
    """
    Get the most recent known-good version of a resource.

    Args:
        resource_type: Type of resource
        resource_name: Name of the resource

    Returns:
        dict: Version dictionary or None if no known-good version exists
    """
    _init_database()
    _migrate_from_pipeline_versions()

    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, resource_type, resource_name, version_number, timestamp, configuration, comment, is_known_good
        FROM resource_versions
        WHERE resource_type = ? AND resource_name = ? AND is_known_good = 1
        ORDER BY version_number DESC
        LIMIT 1
    """, (resource_type, resource_name))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "resource_type": row["resource_type"],
            "resource_name": row["resource_name"],
            "version_number": row["version_number"],
            "timestamp": row["timestamp"],
            "configuration": json.loads(row["configuration"]),
            "comment": row["comment"],
            "is_known_good": bool(row["is_known_good"])
        }
    return None



def delete_resource_versions(resource_type, resource_name):
    """
    Delete all versions for a resource.

    Args:
        resource_type: Type of resource
        resource_name: Name of the resource

    Returns:
        int: Number of versions deleted
    """
    _init_database()
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM resource_versions
        WHERE resource_type = ? AND resource_name = ?
    """, (resource_type, resource_name))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count


def get_all_versioned_resources(resource_type):
    """
    Get list of all resources of a specific type that have versions stored.

    Args:
        resource_type: Type of resource

    Returns:
        list: List of resource names
    """
    _init_database()
    _migrate_from_pipeline_versions()

    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT resource_name
        FROM resource_versions
        WHERE resource_type = ?
        ORDER BY resource_name
    """, (resource_type,))

    resources = [row["resource_name"] for row in cursor.fetchall()]
    conn.close()

    return resources


def get_version_count(resource_type, resource_name):
    """
    Get the number of versions stored for a resource.

    Args:
        resource_type: Type of resource
        resource_name: Name of the resource

    Returns:
        int: Number of versions
    """
    _init_database()
    _migrate_from_pipeline_versions()

    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) as count
        FROM resource_versions
        WHERE resource_type = ? AND resource_name = ?
    """, (resource_type, resource_name))

    count = cursor.fetchone()["count"]
    conn.close()

    return count


# ============================================================================
# Dependency Tracking Functions
# ============================================================================

def _discover_dependencies(es, resource_type, resource_name, depth=0, max_depth=2, visited=None):
    """
    Discover dependencies for a resource.

    Args:
        es: Elasticsearch client
        resource_type: Type of the resource
        resource_name: Name of the resource
        depth: Current recursion depth
        max_depth: Maximum recursion depth
        visited: Set of already visited resources (to prevent cycles)

    Returns:
        list: List of dependency dictionaries with keys:
            - dependency_resource_type
            - dependency_resource_name
            - dependency_configuration
            - relationship_type
    """
    from ..config import MAX_DEPENDENCY_DEPTH, ENABLE_DEPENDENCY_TRACKING

    if not ENABLE_DEPENDENCY_TRACKING:
        return []

    if visited is None:
        visited = set()

    # Use configured max depth
    if max_depth is None:
        max_depth = MAX_DEPENDENCY_DEPTH

    if depth >= max_depth:
        return []

    # Prevent cycles
    resource_key = (resource_type, resource_name)
    if resource_key in visited:
        return []

    visited.add(resource_key)
    dependencies = []

    try:
        if resource_type == RESOURCE_TYPE_PIPELINE:
            # Find index templates that reference this pipeline
            deps = _get_index_templates_using_pipeline(es, resource_name)
            dependencies.extend(deps)

            # Recursively get component templates from those index templates
            if depth + 1 < max_depth:
                for dep in deps:
                    if dep["dependency_resource_type"] == RESOURCE_TYPE_INDEX_TEMPLATE:
                        comp_deps = _discover_dependencies(
                            es, RESOURCE_TYPE_INDEX_TEMPLATE,
                            dep["dependency_resource_name"],
                            depth + 1, max_depth, visited
                        )
                        dependencies.extend(comp_deps)

        elif resource_type == RESOURCE_TYPE_INDEX_TEMPLATE:
            # Get component templates used by this index template
            deps = _get_component_templates_from_index_template(es, resource_name)
            dependencies.extend(deps)

            # Get pipelines referenced by this index template
            pipeline_deps = _get_pipelines_from_index_template(es, resource_name)
            dependencies.extend(pipeline_deps)

        elif resource_type == RESOURCE_TYPE_COMPONENT_TEMPLATE:
            # Find index templates that use this component template
            deps = _get_index_templates_using_component(es, resource_name)
            dependencies.extend(deps)

            # Recursively get pipelines from those index templates
            if depth + 1 < max_depth:
                for dep in deps:
                    if dep["dependency_resource_type"] == RESOURCE_TYPE_INDEX_TEMPLATE:
                        pipeline_deps = _discover_dependencies(
                            es, RESOURCE_TYPE_INDEX_TEMPLATE,
                            dep["dependency_resource_name"],
                            depth + 1, max_depth, visited
                        )
                        dependencies.extend(pipeline_deps)

    except Exception as e:
        console.print(f"[yellow]⚠️  Warning: Could not discover all dependencies: {str(e)}[/yellow]")

    return dependencies


def _get_index_templates_using_pipeline(es, pipeline_name):
    """Find all index templates that reference a specific pipeline."""
    dependencies = []

    try:
        resp = es.indices.get_index_template()

        for template_data in resp.get("index_templates", []):
            template_name = template_data["name"]
            template_config = template_data["index_template"]
            template_def = template_config.get("template", {})
            settings = template_def.get("settings", {})

            # Check for default_pipeline or final_pipeline
            default_pipeline = settings.get("index", {}).get("default_pipeline")
            final_pipeline = settings.get("index", {}).get("final_pipeline")

            if default_pipeline == pipeline_name:
                dependencies.append({
                    "dependency_resource_type": RESOURCE_TYPE_INDEX_TEMPLATE,
                    "dependency_resource_name": template_name,
                    "dependency_configuration": template_config,
                    "relationship_type": "uses_default_pipeline"
                })
            elif final_pipeline == pipeline_name:
                dependencies.append({
                    "dependency_resource_type": RESOURCE_TYPE_INDEX_TEMPLATE,
                    "dependency_resource_name": template_name,
                    "dependency_configuration": template_config,
                    "relationship_type": "uses_final_pipeline"
                })

    except Exception as e:
        console.print(f"[yellow]⚠️  Warning: Could not fetch index templates: {str(e)}[/yellow]")

    return dependencies


def _get_component_templates_from_index_template(es, template_name):
    """Extract component templates from an index template's composed_of field."""
    dependencies = []

    try:
        resp = es.indices.get_index_template(name=template_name)
        template_config = resp["index_templates"][0]["index_template"]
        composed_of = template_config.get("composed_of", [])

        for component_name in composed_of:
            try:
                comp_resp = es.cluster.get_component_template(name=component_name)
                comp_config = comp_resp["component_templates"][0]["component_template"]

                dependencies.append({
                    "dependency_resource_type": RESOURCE_TYPE_COMPONENT_TEMPLATE,
                    "dependency_resource_name": component_name,
                    "dependency_configuration": comp_config,
                    "relationship_type": "composed_of"
                })
            except Exception:
                pass  # Component template might not exist

    except Exception as e:
        console.print(f"[yellow]⚠️  Warning: Could not fetch component templates: {str(e)}[/yellow]")

    return dependencies


# Backward compatibility wrapper functions for pipelines


def _get_pipelines_from_index_template(es, template_name):
    """Extract pipeline references from an index template's settings."""
    dependencies = []

    try:
        resp = es.indices.get_index_template(name=template_name)
        template_config = resp["index_templates"][0]["index_template"]
        template_def = template_config.get("template", {})
        settings = template_def.get("settings", {})

        # Check for default_pipeline or final_pipeline
        default_pipeline = settings.get("index", {}).get("default_pipeline")
        final_pipeline = settings.get("index", {}).get("final_pipeline")

        for pipeline_name, rel_type in [(default_pipeline, "referenced_as_default"),
                                         (final_pipeline, "referenced_as_final")]:
            if pipeline_name:
                try:
                    pipeline_resp = es.ingest.get_pipeline(id=pipeline_name)
                    pipeline_config = pipeline_resp.get(pipeline_name, {})

                    dependencies.append({
                        "dependency_resource_type": RESOURCE_TYPE_PIPELINE,
                        "dependency_resource_name": pipeline_name,
                        "dependency_configuration": pipeline_config,
                        "relationship_type": rel_type
                    })
                except Exception:
                    pass  # Pipeline might not exist

    except Exception as e:
        console.print(f"[yellow]⚠️  Warning: Could not fetch pipelines: {str(e)}[/yellow]")

    return dependencies


def _get_index_templates_using_component(es, component_name):
    """Find all index templates that use a specific component template."""
    dependencies = []

    try:
        resp = es.indices.get_index_template()

        for template_data in resp.get("index_templates", []):
            template_name = template_data["name"]
            template_config = template_data["index_template"]
            composed_of = template_config.get("composed_of", [])

            if component_name in composed_of:
                dependencies.append({
                    "dependency_resource_type": RESOURCE_TYPE_INDEX_TEMPLATE,
                    "dependency_resource_name": template_name,
                    "dependency_configuration": template_config,
                    "relationship_type": "uses_component"
                })

    except Exception as e:
        console.print(f"[yellow]⚠️  Warning: Could not fetch index templates: {str(e)}[/yellow]")

    return dependencies


def _save_dependencies(parent_resource_type, parent_resource_name, parent_version_number, dependencies):
    """
    Save dependency snapshots to the database.

    Args:
        parent_resource_type: Type of the parent resource
        parent_resource_name: Name of the parent resource
        parent_version_number: Version number of the parent resource
        dependencies: List of dependency dictionaries
    """
    if not dependencies:
        return

    conn = _get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.utcnow().isoformat()

    for dep in dependencies:
        cursor.execute("""
            INSERT INTO resource_dependencies
            (parent_resource_type, parent_resource_name, parent_version_number,
             dependency_resource_type, dependency_resource_name, dependency_version_number,
             dependency_configuration, timestamp, relationship_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            parent_resource_type,
            parent_resource_name,
            parent_version_number,
            dep["dependency_resource_type"],
            dep["dependency_resource_name"],
            None,  # We don't track dependency version number in this implementation
            json.dumps(dep["dependency_configuration"]),
            timestamp,
            dep["relationship_type"]
        ))

    conn.commit()
    conn.close()


def save_resource_version_with_dependencies(es, resource_type, resource_name, configuration,
                                           comment=None, is_known_good=False):
    """
    Save a resource version and automatically capture all dependencies.

    Args:
        es: Elasticsearch client (required for dependency discovery)
        resource_type: Type of resource
        resource_name: Name of the resource
        configuration: Full resource configuration (dict)
        comment: Optional user comment
        is_known_good: Whether this is marked as a known-good version

    Returns:
        int: Version number of the saved resource
    """
    from ..config import ENABLE_DEPENDENCY_TRACKING

    # Save the main resource version
    version_number = save_resource_version(resource_type, resource_name, configuration, comment, is_known_good)

    # Discover and save dependencies if enabled
    if ENABLE_DEPENDENCY_TRACKING and es is not None:
        try:
            dependencies = _discover_dependencies(es, resource_type, resource_name)
            if dependencies:
                _save_dependencies(resource_type, resource_name, version_number, dependencies)
                console.print(f"[dim]  └─ Captured {len(dependencies)} dependency snapshot(s)[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Warning: Could not capture dependencies: {str(e)}[/yellow]")

    return version_number


def get_resource_dependencies(resource_type, resource_name, version_number):
    """
    Get all dependencies captured for a specific resource version.

    Args:
        resource_type: Type of the resource
        resource_name: Name of the resource
        version_number: Version number

    Returns:
        list: List of dependency dictionaries
    """
    _init_database()

    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT dependency_resource_type, dependency_resource_name,
               dependency_configuration, relationship_type, timestamp
        FROM resource_dependencies
        WHERE parent_resource_type = ? AND parent_resource_name = ? AND parent_version_number = ?
        ORDER BY id
    """, (resource_type, resource_name, version_number))

    dependencies = []
    for row in cursor.fetchall():
        dependencies.append({
            "dependency_resource_type": row["dependency_resource_type"],
            "dependency_resource_name": row["dependency_resource_name"],
            "dependency_configuration": json.loads(row["dependency_configuration"]),
            "relationship_type": row["relationship_type"],
            "timestamp": row["timestamp"]
        })

    conn.close()
    return dependencies


def compare_dependency_with_current(es, dependency):
    """
    Compare a dependency snapshot with its current state in Elasticsearch.

    Args:
        es: Elasticsearch client
        dependency: Dependency dictionary from get_resource_dependencies()

    Returns:
        dict: Comparison result with keys:
            - exists: bool - Whether the resource still exists
            - changed: bool - Whether the configuration has changed
            - current_config: dict - Current configuration (if exists)
            - diff_summary: str - Human-readable summary of changes
    """
    dep_type = dependency["dependency_resource_type"]
    dep_name = dependency["dependency_resource_name"]
    snapshot_config = dependency["dependency_configuration"]

    result = {
        "exists": False,
        "changed": False,
        "current_config": None,
        "diff_summary": "Resource does not exist"
    }

    try:
        # Fetch current state based on resource type
        if dep_type == RESOURCE_TYPE_PIPELINE:
            resp = es.ingest.get_pipeline(id=dep_name)
            current_config = resp.get(dep_name, {})
        elif dep_type == RESOURCE_TYPE_INDEX_TEMPLATE:
            resp = es.indices.get_index_template(name=dep_name)
            current_config = resp["index_templates"][0]["index_template"]
        elif dep_type == RESOURCE_TYPE_COMPONENT_TEMPLATE:
            resp = es.cluster.get_component_template(name=dep_name)
            current_config = resp["component_templates"][0]["component_template"]
        else:
            return result

        result["exists"] = True
        result["current_config"] = current_config

        # Compare configurations
        if json.dumps(snapshot_config, sort_keys=True) != json.dumps(current_config, sort_keys=True):
            result["changed"] = True
            result["diff_summary"] = "Configuration has changed since snapshot"
        else:
            result["diff_summary"] = "No changes detected"

    except Exception as e:
        result["diff_summary"] = f"Error checking current state: {str(e)}"

    return result


def rollback_resource_with_dependencies(es, resource_type, resource_name, version_number, dry_run=False):
    """
    Rollback a resource and all its dependencies to a specific snapshot.

    Args:
        es: Elasticsearch client
        resource_type: Type of the resource
        resource_name: Name of the resource
        version_number: Version number to rollback to
        dry_run: If True, only show what would be done without making changes

    Returns:
        dict: Result with keys:
            - success: bool
            - main_resource_restored: bool
            - dependencies_restored: list of restored dependency names
            - warnings: list of warning messages
            - errors: list of error messages
    """
    from ..config import DRY_RUN_MODE

    result = {
        "success": False,
        "main_resource_restored": False,
        "dependencies_restored": [],
        "warnings": [],
        "errors": []
    }

    # Check if dry run mode is enabled globally or locally
    is_dry_run = DRY_RUN_MODE or dry_run

    try:
        # Get the version to restore
        version = get_resource_version(resource_type, resource_name, version_number)
        if not version:
            result["errors"].append(f"Version {version_number} not found")
            return result

        # Get dependencies for this version
        dependencies = get_resource_dependencies(resource_type, resource_name, version_number)

        # Check current state of dependencies
        dependency_changes = []
        for dep in dependencies:
            comparison = compare_dependency_with_current(es, dep)
            if comparison["changed"]:
                dependency_changes.append({
                    "name": dep["dependency_resource_name"],
                    "type": dep["dependency_resource_type"],
                    "relationship": dep["relationship_type"],
                    "comparison": comparison
                })

        # Add warnings for changed dependencies
        if dependency_changes:
            result["warnings"].append(
                f"⚠️  {len(dependency_changes)} dependencies have changed since this snapshot was created"
            )

        # Restore main resource
        main_config = json.loads(version["configuration"])

        if not is_dry_run:
            if resource_type == RESOURCE_TYPE_PIPELINE:
                es.ingest.put_pipeline(id=resource_name, body=main_config)
            elif resource_type == RESOURCE_TYPE_INDEX_TEMPLATE:
                es.indices.put_index_template(name=resource_name, body=main_config)
            elif resource_type == RESOURCE_TYPE_COMPONENT_TEMPLATE:
                es.cluster.put_component_template(name=resource_name, body=main_config)

            result["main_resource_restored"] = True
        else:
            result["warnings"].append("DRY RUN: Main resource would be restored")

        # Restore dependencies
        for dep in dependencies:
            dep_type = dep["dependency_resource_type"]
            dep_name = dep["dependency_resource_name"]
            dep_config = dep["dependency_configuration"]

            try:
                if not is_dry_run:
                    if dep_type == RESOURCE_TYPE_PIPELINE:
                        es.ingest.put_pipeline(id=dep_name, body=dep_config)
                    elif dep_type == RESOURCE_TYPE_INDEX_TEMPLATE:
                        es.indices.put_index_template(name=dep_name, body=dep_config)
                    elif dep_type == RESOURCE_TYPE_COMPONENT_TEMPLATE:
                        es.cluster.put_component_template(name=dep_name, body=dep_config)

                    result["dependencies_restored"].append(dep_name)
                else:
                    result["warnings"].append(f"DRY RUN: Would restore {dep_type}: {dep_name}")

            except Exception as e:
                result["errors"].append(f"Failed to restore {dep_type} '{dep_name}': {str(e)}")

        result["success"] = True if not result["errors"] else False

    except Exception as e:
        result["errors"].append(f"Rollback failed: {str(e)}")

    return result


def save_pipeline_version(pipeline_name, configuration, comment=None, is_known_good=False):
    """Backward compatibility wrapper for pipeline version saving."""
    return save_resource_version(RESOURCE_TYPE_PIPELINE, pipeline_name, configuration, comment, is_known_good)


def get_pipeline_versions(pipeline_name):
    """Backward compatibility wrapper for getting pipeline versions."""
    return get_resource_versions(RESOURCE_TYPE_PIPELINE, pipeline_name)


def get_pipeline_version(pipeline_name, version_number):
    """Backward compatibility wrapper for getting a specific pipeline version."""
    return get_resource_version(RESOURCE_TYPE_PIPELINE, pipeline_name, version_number)


# Note: This function name conflicts with the generic get_last_known_good_version above
# For backward compatibility with pipeline_management.py, we create an alias
def get_last_known_good_version_for_pipeline(pipeline_name):
    """Get last known-good version for a pipeline (backward compatibility)."""
    return get_last_known_good_version(RESOURCE_TYPE_PIPELINE, pipeline_name)


def delete_pipeline_versions(pipeline_name):
    """Backward compatibility wrapper for deleting pipeline versions."""
    return delete_resource_versions(RESOURCE_TYPE_PIPELINE, pipeline_name)


def get_all_versioned_pipelines():
    """Backward compatibility wrapper for getting all versioned pipelines."""
    return get_all_versioned_resources(RESOURCE_TYPE_PIPELINE)


def get_pipeline_version_count(pipeline_name):
    """Backward compatibility wrapper for getting pipeline version count."""
    return get_version_count(RESOURCE_TYPE_PIPELINE, pipeline_name)


