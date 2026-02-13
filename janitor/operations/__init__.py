"""
Operations modules for Elastic Janitor.
"""
from .index_basic import (
    option_list_largest_indices,
    option_index_settings_viewer,
    option_duplicate_index_detector,
)
from .index_health import (
    option_index_health_dashboard,
    option_shard_analysis,
)
from .index_advanced import (
    option_index_alias_management,
    option_index_rollover_status,
    option_cold_frozen_migration,
    option_index_merge_optimization,
)
from .data_streams_cleanup import option_clean_data_streams
from .data_streams_standalone import option_clean_standalone_indices
from .data_streams_preview import option_preview_data_streams
from .data_streams_stats import (
    option_data_stream_statistics,
    option_data_stream_lifecycle_viewer,
)
from .data_streams_advanced import (
    option_backing_index_reindexing,
    option_data_stream_cloning,
    option_write_index_rotation,
)
from .templates_index import (
    option_list_templates,
    option_delete_templates,
    option_list_component_templates,
    option_delete_component_templates,
)
from .templates_policies import (
    option_list_ilm,
    option_delete_ilm,
    option_list_pipelines,
    option_delete_pipelines,
)
from .pipeline_management import (
    option_view_pipeline_details,
    option_edit_pipeline,
    option_view_version_history,
    option_rollback_pipeline,
    option_emergency_rollback,
    option_export_pipeline,
    option_import_pipeline,
    option_clone_pipeline,
)
from .template_management import (
    option_view_index_template_details,
    option_view_component_template_details,
    option_edit_index_template,
    option_edit_component_template,
    option_rollback_index_template,
    option_rollback_component_template,
    option_export_index_template,
    option_export_component_template,
    option_import_index_template,
    option_import_component_template,
)
from .template_policy_advanced import (
    option_template_conflict_detector,
    option_ilm_policy_simulator,
    option_bulk_policy_assignment,
    option_policy_effectiveness_report,
    option_template_inheritance_viewer,
    option_unused_template_detector,
)
from .snapshots import (
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
)
from .cluster import (
    option_cluster_health_overview,
    option_node_information,
    option_cluster_stats,
    option_dashboard_stats_view,
    toggle_dry_run_mode,
)
from .storage_optimization import (
    option_storage_forecast,
    option_tier_distribution,
    option_compression_analysis,
    option_empty_index_cleanup,
    option_sparse_index_detector,
    option_cost_estimator,
)
from .performance_monitoring import (
    option_slow_query_analyzer,
    option_indexing_performance_monitor,
    option_search_performance_dashboard,
    option_cluster_health_timeline,
    option_node_resource_usage,
    option_hot_spot_detector,
)
from .bulk_automation import (
    option_batch_index_operations,
    option_scheduled_cleanup_jobs,
    option_dry_run_mode,
    option_operation_history_log,
    option_rollback_capability,
    option_export_import_configurations,
)
from .advanced_cleanup import (
    option_orphaned_document_cleanup,
    option_field_level_cleanup,
    option_mapping_cleanup,
    option_wildcard_index_deletion,
    option_timeseries_gap_detector,
    option_duplicate_document_detector,
)
from .data_quality import (
    option_missing_field_analyzer,
    option_data_type_inconsistency_detector,
    option_null_value_statistics,
    option_cardinality_analysis,
)
from .mapping_conflict_resolver import (
    option_field_mapping_conflict_resolver,
)
from .aws_ingestion_diagnostics import (
    option_firehose_forwarder_health_check,
    option_common_issue_detection,
    option_field_structure_analysis,
    option_pipeline_troubleshooting,
    option_data_quality_metrics,
    option_quick_fixes_actions,
)
from .dependency_viewer import (
    option_view_resource_dependencies,
    option_rollback_with_dependencies,
)

__all__ = [
    # Index management - basic
    'option_list_largest_indices',
    'option_index_settings_viewer',
    'option_duplicate_index_detector',
    # Index management - health
    'option_index_health_dashboard',
    'option_shard_analysis',
    # Index management - advanced
    'option_index_alias_management',
    'option_index_rollover_status',
    'option_cold_frozen_migration',
    'option_index_merge_optimization',
    # Data streams
    'option_clean_data_streams',
    'option_clean_standalone_indices',
    'option_preview_data_streams',
    'option_data_stream_statistics',
    'option_data_stream_lifecycle_viewer',
    'option_backing_index_reindexing',
    'option_data_stream_cloning',
    'option_write_index_rotation',
    # Templates
    'option_list_templates',
    'option_delete_templates',
    'option_list_component_templates',
    'option_delete_component_templates',
    'option_list_ilm',
    'option_delete_ilm',
    'option_list_pipelines',
    'option_delete_pipelines',
    # Pipeline Management
    'option_view_pipeline_details',
    'option_edit_pipeline',
    'option_view_version_history',
    'option_rollback_pipeline',
    'option_emergency_rollback',
    'option_export_pipeline',
    'option_import_pipeline',
    'option_clone_pipeline',
    # Template Management
    'option_view_index_template_details',
    'option_view_component_template_details',
    'option_edit_index_template',
    'option_edit_component_template',
    'option_rollback_index_template',
    'option_rollback_component_template',
    'option_export_index_template',
    'option_export_component_template',
    'option_import_index_template',
    'option_import_component_template',
    # Template & Policy Advanced
    'option_template_conflict_detector',
    'option_ilm_policy_simulator',
    'option_bulk_policy_assignment',
    'option_policy_effectiveness_report',
    'option_template_inheritance_viewer',
    'option_unused_template_detector',
    # Snapshots
    'option_list_snapshot_repos',
    'option_list_snapshots',
    'option_delete_old_snapshots',
    'option_list_slm',
    'option_delete_slm',
    'option_verify_snapshot_repository',
    'option_snapshot_size_analysis',
    'option_automated_snapshot_cleanup',
    'option_cross_repository_copy',
    'option_snapshot_restore_wizard',
    'option_snapshot_comparison',
    # Cluster
    'option_cluster_health_overview',
    'option_node_information',
    'option_cluster_stats',
    'option_dashboard_stats_view',
    'toggle_dry_run_mode',
    # Storage & Cost Optimization
    'option_storage_forecast',
    'option_tier_distribution',
    'option_compression_analysis',
    'option_empty_index_cleanup',
    'option_sparse_index_detector',
    'option_cost_estimator',
    # Performance & Monitoring
    'option_slow_query_analyzer',
    'option_indexing_performance_monitor',
    'option_search_performance_dashboard',
    'option_cluster_health_timeline',
    'option_node_resource_usage',
    'option_hot_spot_detector',
    # Bulk Operations & Automation
    'option_batch_index_operations',
    'option_scheduled_cleanup_jobs',
    'option_dry_run_mode',
    'option_operation_history_log',
    'option_rollback_capability',
    'option_export_import_configurations',
    # Advanced Cleanup Features
    'option_orphaned_document_cleanup',
    'option_field_level_cleanup',
    'option_mapping_cleanup',
    'option_wildcard_index_deletion',
    'option_timeseries_gap_detector',
    'option_duplicate_document_detector',
    # Data Quality & Validation
    'option_missing_field_analyzer',
    'option_data_type_inconsistency_detector',
    'option_null_value_statistics',
    'option_cardinality_analysis',
    'option_field_mapping_conflict_resolver',
    # AWS Ingestion Management
    'option_firehose_forwarder_health_check',
    'option_common_issue_detection',
    'option_field_structure_analysis',
    'option_pipeline_troubleshooting',
    'option_data_quality_metrics',
    'option_quick_fixes_actions',
    # Dependency Viewer
    'option_view_resource_dependencies',
    'option_rollback_with_dependencies',
]
