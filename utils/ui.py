"""
UI-related utility functions.
"""
from ..config import console


def show_breadcrumb(path):
    """Display breadcrumb navigation."""
    breadcrumb = " > ".join(path)
    console.print(f"\n[dim cyan]{breadcrumb}[/dim cyan]\n")

