"""
Submenus for Elastic Janitor.
"""
import questionary
from questionary import Choice, Separator
from ..config import custom_style, console
from ..utils import show_breadcrumb
from ..operations import (
    option_index_health_dashboard,
    option_shard_analysis,
    option_index_settings_viewer,
    option_duplicate_index_detector,
    option_index_alias_management,
    option_index_rollover_status,
    option_cold_frozen_migration,
    option_index_merge_optimization,
    option_list_largest_indices,
    option_clean_data_streams,
    option_clean_standalone_indices,
    option_preview_data_streams,
    option_data_stream_statistics,
    option_data_stream_lifecycle_viewer,
    option_backing_index_reindexing,
    option_data_stream_cloning,
    option_write_index_rotation,
    option_list_templates,
    option_delete_templates,
    option_list_component_templates,
    option_delete_component_templates,
    option_list_ilm,
    option_delete_ilm,
    option_list_pipelines,
    option_delete_pipelines,
    option_template_conflict_detector,
    option_ilm_policy_simulator,
    option_bulk_policy_assignment,
    option_policy_effectiveness_report,
    option_template_inheritance_viewer,
    option_unused_template_detector,
    option_list_snapshot_repos,
    option_list_snapshots,
    option_delete_old_snapshots,
    option_list_slm,
    option_delete_slm,
    option_verify_snapshot_repository,
    option_snapshot_size_analysis,
    option_automated_snapshot_cleanup,
    option_cross_repository_copy,
    option_snapshot_restore_wizard,
    option_snapshot_comparison,
    option_cluster_health_overview,
    option_node_information,
    option_cluster_stats,
    option_dashboard_stats_view,
    toggle_dry_run_mode,
    option_storage_forecast,
    option_tier_distribution,
    option_compression_analysis,
    option_empty_index_cleanup,
    option_sparse_index_detector,
    option_cost_estimator,
    option_slow_query_analyzer,
    option_indexing_performance_monitor,
    option_search_performance_dashboard,
    option_cluster_health_timeline,
    option_node_resource_usage,
    option_hot_spot_detector,
    option_batch_index_operations,
    option_scheduled_cleanup_jobs,
    option_dry_run_mode,
    option_operation_history_log,
    option_rollback_capability,
    option_export_import_configurations,
    option_orphaned_document_cleanup,
    option_field_level_cleanup,
    option_mapping_cleanup,
    option_wildcard_index_deletion,
    option_timeseries_gap_detector,
    option_duplicate_document_detector,
)


def submenu_index_management(es):
    """Index Management sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Index Management"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("Index Health Dashboard", value="1"),
                    questionary.Choice("Shard Analysis", value="2"),
                    questionary.Choice("Index Settings Viewer", value="3"),
                    questionary.Choice("Duplicate Index Detector", value="4"),
                    questionary.Choice("Index Alias Management", value="5"),
                    questionary.Choice("Index Rollover Status", value="6"),
                    questionary.Choice("Cold/Frozen Tier Migration", value="7"),
                    questionary.Choice("Index Merge Optimization", value="8"),
                    questionary.Choice("List Largest Indices", value="9"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_index_health_dashboard(es)
        elif choice == "2":
            option_shard_analysis(es)
        elif choice == "3":
            option_index_settings_viewer(es)
        elif choice == "4":
            option_duplicate_index_detector(es)
        elif choice == "5":
            option_index_alias_management(es)
        elif choice == "6":
            option_index_rollover_status(es)
        elif choice == "7":
            option_cold_frozen_migration(es)
        elif choice == "8":
            option_index_merge_optimization(es)
        elif choice == "9":
            option_list_largest_indices(es)




def submenu_data_streams(es):
    """Data Stream Management sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Data Stream Management"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("Clean data streams (delete backing indices older than X days)", value="1"),
                    questionary.Choice("Preview data streams eligible for deletion (view only)", value="2"),
                    questionary.Choice("Clean standalone indices older than X days", value="3"),
                    questionary.Choice("Data Stream Statistics", value="4"),
                    questionary.Choice("Data Stream Lifecycle Viewer", value="5"),
                    questionary.Choice("Backing Index Reindexing", value="6"),
                    questionary.Choice("Data Stream Cloning", value="7"),
                    questionary.Choice("Write Index Rotation", value="8"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_clean_data_streams(es)
        elif choice == "2":
            option_preview_data_streams(es)
        elif choice == "3":
            option_clean_standalone_indices(es)
        elif choice == "4":
            option_data_stream_statistics(es)
        elif choice == "5":
            option_data_stream_lifecycle_viewer(es)
        elif choice == "6":
            option_backing_index_reindexing(es)
        elif choice == "7":
            option_data_stream_cloning(es)
        elif choice == "8":
            option_write_index_rotation(es)




def submenu_templates_policies(es):
    """Template & Policy Management sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Template & Policy Management"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("List index templates", value="1"),
                    questionary.Choice("Delete index templates by name match", value="2"),
                    questionary.Choice("List component templates", value="3"),
                    questionary.Choice("Delete component templates by name match", value="4"),
                    questionary.Choice("List ILM policies", value="5"),
                    questionary.Choice("Delete ILM policies by name match", value="6"),
                    questionary.Choice("List ingest pipelines", value="7"),
                    questionary.Choice("Delete ingest pipelines by name match", value="8"),
                    questionary.Separator(),
                    questionary.Choice("Template Conflict Detector", value="9"),
                    questionary.Choice("ILM Policy Simulator", value="10"),
                    questionary.Choice("Bulk Policy Assignment", value="11"),
                    questionary.Choice("Policy Effectiveness Report", value="12"),
                    questionary.Choice("Template Inheritance Viewer", value="13"),
                    questionary.Choice("Unused Template Detector", value="14"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_list_templates(es)
        elif choice == "2":
            option_delete_templates(es)
        elif choice == "3":
            option_list_component_templates(es)
        elif choice == "4":
            option_delete_component_templates(es)
        elif choice == "5":
            option_list_ilm(es)
        elif choice == "6":
            option_delete_ilm(es)
        elif choice == "7":
            option_list_pipelines(es)
        elif choice == "8":
            option_delete_pipelines(es)
        elif choice == "9":
            option_template_conflict_detector(es)
        elif choice == "10":
            option_ilm_policy_simulator(es)
        elif choice == "11":
            option_bulk_policy_assignment(es)
        elif choice == "12":
            option_policy_effectiveness_report(es)
        elif choice == "13":
            option_template_inheritance_viewer(es)
        elif choice == "14":
            option_unused_template_detector(es)




def submenu_snapshots(es):
    """Snapshot & Backup Management sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Snapshot & Backup Management"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("List snapshot repositories", value="1"),
                    questionary.Choice("List snapshots in a repository", value="2"),
                    questionary.Choice("Delete snapshots older than X days", value="3"),
                    questionary.Choice("List SLM policies", value="4"),
                    questionary.Choice("Delete SLM policies by name match", value="5"),
                    questionary.Separator(),
                    questionary.Choice("Verify snapshot repository", value="6"),
                    questionary.Choice("Snapshot size analysis", value="7"),
                    questionary.Choice("Automated snapshot cleanup", value="8"),
                    questionary.Choice("Cross-repository snapshot copy", value="9"),
                    questionary.Choice("Snapshot restore wizard", value="10"),
                    questionary.Choice("Snapshot comparison", value="11"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_list_snapshot_repos(es)
        elif choice == "2":
            option_list_snapshots(es)
        elif choice == "3":
            option_delete_old_snapshots(es)
        elif choice == "4":
            option_list_slm(es)
        elif choice == "5":
            option_delete_slm(es)
        elif choice == "6":
            option_verify_snapshot_repository(es)
        elif choice == "7":
            option_snapshot_size_analysis(es)
        elif choice == "8":
            option_automated_snapshot_cleanup(es)
        elif choice == "9":
            option_cross_repository_copy(es)
        elif choice == "10":
            option_snapshot_restore_wizard(es)
        elif choice == "11":
            option_snapshot_comparison(es)




def submenu_cluster_health(es):
    """Cluster Health & Diagnostics sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Cluster Health & Diagnostics"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("Cluster Health Overview", value="1"),
                    questionary.Choice("Node Information", value="2"),
                    questionary.Choice("Cluster Stats", value="3"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_cluster_health_overview(es)
        elif choice == "2":
            option_node_information(es)
        elif choice == "3":
            option_cluster_stats(es)


def submenu_storage_optimization(es):
    """Storage & Cost Optimization sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Storage & Cost Optimization"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("Storage Forecast", value="1"),
                    questionary.Choice("Tier Distribution Report", value="2"),
                    questionary.Choice("Compression Analysis", value="3"),
                    questionary.Choice("Empty Index Cleanup", value="4"),
                    questionary.Choice("Sparse Index Detector", value="5"),
                    questionary.Choice("Cost Estimator", value="6"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_storage_forecast(es)
        elif choice == "2":
            option_tier_distribution(es)
        elif choice == "3":
            option_compression_analysis(es)
        elif choice == "4":
            option_empty_index_cleanup(es)
        elif choice == "5":
            option_sparse_index_detector(es)
        elif choice == "6":
            option_cost_estimator(es)


def submenu_performance_monitoring(es):
    """Performance & Monitoring sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Performance & Monitoring"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("Slow Query Analyzer", value="1"),
                    questionary.Choice("Indexing Performance Monitor", value="2"),
                    questionary.Choice("Search Performance Dashboard", value="3"),
                    questionary.Choice("Cluster Health Timeline", value="4"),
                    questionary.Choice("Node Resource Usage", value="5"),
                    questionary.Choice("Hot Spot Detector", value="6"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_slow_query_analyzer(es)
        elif choice == "2":
            option_indexing_performance_monitor(es)
        elif choice == "3":
            option_search_performance_dashboard(es)
        elif choice == "4":
            option_cluster_health_timeline(es)
        elif choice == "5":
            option_node_resource_usage(es)
        elif choice == "6":
            option_hot_spot_detector(es)


def submenu_bulk_automation(es):
    """Bulk Operations & Automation sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Bulk Operations & Automation"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("Batch Index Operations", value="1"),
                    questionary.Choice("Scheduled Cleanup Jobs (Coming Soon)", value="2"),
                    questionary.Choice("Dry-Run Mode Toggle", value="3"),
                    questionary.Choice("Operation History Log", value="4"),
                    questionary.Choice("Rollback Capability (Coming Soon)", value="5"),
                    questionary.Choice("Export/Import Configurations", value="6"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_batch_index_operations(es)
        elif choice == "2":
            option_scheduled_cleanup_jobs(es)
        elif choice == "3":
            option_dry_run_mode(es)
        elif choice == "4":
            option_operation_history_log(es)
        elif choice == "5":
            option_rollback_capability(es)
        elif choice == "6":
            option_export_import_configurations(es)





def submenu_advanced_cleanup(es):
    """Advanced Cleanup Features sub-menu."""
    while True:
        show_breadcrumb(["Main Menu", "Advanced Cleanup Features"])
        console.print()

        try:
            choice = questionary.select(
                "Select option:",
                choices=[
                    questionary.Choice("Orphaned Document Cleanup", value="1"),
                    questionary.Choice("Field-Level Cleanup", value="2"),
                    questionary.Choice("Mapping Cleanup", value="3"),
                    questionary.Choice("Wildcard Index Deletion", value="4"),
                    questionary.Choice("Time-Series Gap Detector", value="5"),
                    questionary.Choice("Duplicate Document Detector", value="6"),
                    questionary.Separator(),
                    questionary.Choice("← Back to Main Menu", value="b"),
                ],
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if choice is None or choice in ("b", "back"):
            return

        if choice == "1":
            option_orphaned_document_cleanup(es)
        elif choice == "2":
            option_field_level_cleanup(es)
        elif choice == "3":
            option_mapping_cleanup(es)
        elif choice == "4":
            option_wildcard_index_deletion(es)
        elif choice == "5":
            option_timeseries_gap_detector(es)
        elif choice == "6":
            option_duplicate_document_detector(es)
