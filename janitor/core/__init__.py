"""
Core functionality for Elastic Janitor.
"""
from .connection import connect, get_index_creation, get_all_indices_info

__all__ = [
    'connect',
    'get_index_creation',
    'get_all_indices_info',
]

