"""
Pagination utilities for Elastic Janitor.
Provides reusable pagination for lists, tables, and Rich renderables.
"""
import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from rich.table import Table
from rich.panel import Panel
from rich.console import RenderableType
from rich import box
from ..config import console
from .helpers import safe_input


def _calculate_pagination_info(total_items: int, page_size: int) -> Tuple[int, bool]:
    """
    Calculate pagination details.
    
    Returns:
        Tuple of (total_pages, needs_pagination)
    """
    if total_items <= 0 or page_size <= 0:
        return 0, False
    total_pages = math.ceil(total_items / page_size)
    needs_pagination = total_pages > 1
    return total_pages, needs_pagination


def _display_page_header(title: str, current_page: int, total_pages: int) -> None:
    """Display the page header with current page info."""
    console.print()
    console.print(Panel(
        f"[bold cyan]{title} - Page {current_page + 1} of {total_pages}[/bold cyan]",
        box=box.DOUBLE
    ))
    console.print()


def _display_navigation_prompt() -> None:
    """Display navigation instructions."""
    console.print()
    console.print("[cyan]" + "─" * 70 + "[/cyan]")
    console.print("[dim]Navigation: [n]ext | [p]revious | [page #] | [q]uit[/dim]")


def _get_page_input(current_page: int, total_pages: int) -> Tuple[str, int]:
    """
    Get user input for pagination navigation.
    
    Returns:
        Tuple of (action, new_page_index)
        action: 'next', 'prev', 'jump', 'quit', or 'stay'
    """
    choice = safe_input("Enter choice: ").strip().lower()
    
    if not choice or choice == 'n':
        # Next page
        if current_page < total_pages - 1:
            return 'next', current_page + 1
        return 'stay', current_page
    
    if choice == 'p':
        # Previous page
        if current_page > 0:
            return 'prev', current_page - 1
        return 'stay', current_page
    
    if choice in ('q', 'quit', 'exit'):
        return 'quit', current_page
    
    # Try to parse as page number
    try:
        page_num = int(choice)
        if 1 <= page_num <= total_pages:
            return 'jump', page_num - 1  # Convert to 0-indexed
        console.print(f"[yellow]Invalid page number. Enter 1-{total_pages}[/yellow]")
        return 'stay', current_page
    except ValueError:
        console.print("[yellow]Invalid input. Use n/p/q or enter a page number.[/yellow]")
        return 'stay', current_page


def paginate_items(
    items: List[Any],
    render_item_func: Callable[[Any, int], None],
    page_size: int = 10,
    title: str = "Items"
) -> None:
    """
    Paginate a list of items with custom rendering.
    
    Args:
        items: List of items to paginate
        render_item_func: Function to render each item. Signature: (item, index) -> None
        page_size: Number of items per page (default: 10)
        title: Title displayed in page header
    
    Example:
        def render_stat(stat, index):
            console.print(f"[bold cyan]Item {index}:[/bold cyan] {stat['name']}")
        
        paginate_items(stats_list, render_stat, page_size=10, title="Statistics")
    """
    if not items:
        console.print(f"\n[yellow]No {title.lower()} to display.[/yellow]\n")
        return
    
    total_pages, needs_pagination = _calculate_pagination_info(len(items), page_size)
    
    if not needs_pagination:
        # Single page - display without pagination UI
        console.print()
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]", box=box.DOUBLE))
        console.print()
        for i, item in enumerate(items):
            render_item_func(item, i + 1)
        console.print()
        return
    
    # Multi-page pagination loop
    current_page = 0
    
    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(items))
        
        _display_page_header(title, current_page, total_pages)
        
        for i in range(start_idx, end_idx):
            render_item_func(items[i], i + 1)
        
        # Show navigation if not on last page or if user might want to go back
        _display_navigation_prompt()
        action, new_page = _get_page_input(current_page, total_pages)
        
        if action == 'quit':
            break
        
        current_page = new_page
    
    console.print()


def paginate_table(
    rows: List[Tuple[str, ...]],
    columns: List[Dict[str, Any]],
    page_size: int = 20,
    title: str = "Table",
    table_kwargs: Optional[Dict[str, Any]] = None
) -> None:
    """
    Paginate Rich Table rows.
    
    Args:
        rows: List of row tuples (each tuple contains column values)
        columns: List of column definitions, e.g., [{"name": "Col", "style": "cyan", "width": 20}]
        page_size: Rows per page (default: 20)
        title: Table title
        table_kwargs: Additional Rich Table constructor arguments
    
    Example:
        columns = [
            {"name": "ID", "style": "cyan"},
            {"name": "Name", "style": "white"},
            {"name": "Status", "style": "green"}
        ]
        rows = [("1", "Item A", "Active"), ("2", "Item B", "Inactive")]
        paginate_table(rows, columns, page_size=20, title="Items")
    """
    if not rows:
        console.print(f"\n[yellow]No {title.lower()} to display.[/yellow]\n")
        return
    
    total_pages, needs_pagination = _calculate_pagination_info(len(rows), page_size)
    table_kwargs = table_kwargs or {}
    
    def create_table_page(page_rows: List[Tuple[str, ...]], page_title: str) -> Table:
        """Create a table for a single page of rows."""
        table = Table(
            title=page_title,
            box=table_kwargs.get('box', box.ROUNDED),
            title_style=table_kwargs.get('title_style', 'bold cyan')
        )
        
        for col in columns:
            table.add_column(
                col.get('name', ''),
                style=col.get('style'),
                width=col.get('width'),
                justify=col.get('justify', 'left'),
                no_wrap=col.get('no_wrap', False)
            )
        
        for row in page_rows:
            table.add_row(*row)
        
        return table
    
    if not needs_pagination:
        # Single page - display without pagination UI
        table = create_table_page(rows, title)
        console.print()
        console.print(table)
        console.print(f"\n[dim]Total: {len(rows)} rows[/dim]\n")
        return
    
    # Multi-page pagination loop
    current_page = 0
    
    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(rows))
        page_rows = rows[start_idx:end_idx]
        
        page_title = f"{title} - Page {current_page + 1} of {total_pages}"
        table = create_table_page(page_rows, page_title)
        
        console.print()
        console.print(table)
        console.print(f"\n[dim]Showing rows {start_idx + 1}-{end_idx} of {len(rows)} total[/dim]")
        
        _display_navigation_prompt()
        action, new_page = _get_page_input(current_page, total_pages)
        
        if action == 'quit':
            break
        
        current_page = new_page
    
    console.print()


def paginate_renderables(
    renderables: List[RenderableType],
    page_size: int = 5,
    title: str = "Content"
) -> None:
    """
    Paginate pre-rendered Rich objects (Panels, Syntax, etc.).
    
    Args:
        renderables: List of Rich renderable objects
        page_size: Items per page (default: 5)
        title: Page header title
    
    Example:
        panels = [Panel(f"Item {i}") for i in range(20)]
        paginate_renderables(panels, page_size=5, title="Results")
    """
    if not renderables:
        console.print(f"\n[yellow]No {title.lower()} to display.[/yellow]\n")
        return
    
    total_pages, needs_pagination = _calculate_pagination_info(len(renderables), page_size)
    
    if not needs_pagination:
        # Single page - display without pagination UI
        console.print()
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]", box=box.DOUBLE))
        console.print()
        for renderable in renderables:
            console.print(renderable)
            console.print()
        return
    
    # Multi-page pagination loop
    current_page = 0
    
    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(renderables))
        
        _display_page_header(title, current_page, total_pages)
        
        for i in range(start_idx, end_idx):
            console.print(renderables[i])
            console.print()
        
        console.print(f"[dim]Showing items {start_idx + 1}-{end_idx} of {len(renderables)} total[/dim]")
        
        _display_navigation_prompt()
        action, new_page = _get_page_input(current_page, total_pages)
        
        if action == 'quit':
            break
        
        current_page = new_page
    
    console.print()
