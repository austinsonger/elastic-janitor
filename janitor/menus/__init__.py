"""
Menu system for Elastic Janitor.
"""
from .main_menu import menu, main
from .submenus import (
    submenu_index_management,
    submenu_data_streams,
    submenu_templates_policies,
    submenu_index_templates,
    submenu_component_templates,
    submenu_ingest_pipelines,
    submenu_ilm_policies,
    submenu_template_analysis_tools,
    submenu_snapshots,
    submenu_snapshot_management,
    submenu_slm_policies,
    submenu_snapshot_advanced_operations,
    submenu_cluster_health,
    submenu_storage_optimization,
    submenu_performance_monitoring,
    submenu_bulk_automation,
)

__all__ = [
    'menu',
    'main',
    'submenu_index_management',
    'submenu_data_streams',
    'submenu_templates_policies',
    'submenu_index_templates',
    'submenu_component_templates',
    'submenu_ingest_pipelines',
    'submenu_ilm_policies',
    'submenu_template_analysis_tools',
    'submenu_snapshots',
    'submenu_snapshot_management',
    'submenu_slm_policies',
    'submenu_snapshot_advanced_operations',
    'submenu_cluster_health',
    'submenu_storage_optimization',
    'submenu_performance_monitoring',
    'submenu_bulk_automation',
]
