"""
Menu system for Elastic Janitor.
"""
from .main_menu import menu, main
from .submenus import (
    submenu_index_management,
    submenu_data_streams,
    submenu_templates_policies,
    submenu_snapshots,
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
    'submenu_snapshots',
    'submenu_cluster_health',
    'submenu_storage_optimization',
    'submenu_performance_monitoring',
    'submenu_bulk_automation',
]
