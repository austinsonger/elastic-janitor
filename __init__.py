"""
Elastic Janitor - A comprehensive Elasticsearch cluster management tool.

This package provides utilities for managing Elasticsearch indices, data streams,
templates, policies, snapshots, and cluster health.
"""

__version__ = "2.0.0"
__author__ = "Elastic Janitor Team"

from .menus import main

__all__ = ['main']

