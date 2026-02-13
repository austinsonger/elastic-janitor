"""
Helper functions for user input and confirmations.
"""
import sys
import questionary
from ..config import PROTECT_SYSTEM, console, custom_style


def safe_input(prompt):
    """Safe input with keyboard interrupt handling."""
    try:
        return input(prompt)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        sys.exit(0)


def is_system(name):
    """Check if an index/data stream is a system resource."""
    if not PROTECT_SYSTEM:
        return False
    return name.startswith(".")


def confirm_delete():
    """Confirm deletion by requiring user to type DELETE."""
    console.print("\n[yellow]🟡 Type DELETE to proceed. Anything else cancels.[/yellow]\n")
    c = safe_input("Confirmation: ").strip()
    return c == "DELETE"


def confirm_action(message, items_count=None):
    """Enhanced confirmation dialog using questionary."""
    if items_count:
        message = f"{message} ({items_count} items)"

    try:
        return questionary.confirm(
            message,
            default=False,
            style=custom_style
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return False


def select_from_list(message, choices, multi=False):
    """Interactive selection from a list with fuzzy search."""
    try:
        if multi:
            return questionary.checkbox(
                message,
                choices=choices,
                style=custom_style
            ).ask()
        else:
            return questionary.select(
                message,
                choices=choices,
                style=custom_style
            ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return None


def get_number_input(message, default=None, min_val=None, max_val=None):
    """Get validated number input with optional min/max constraints."""
    def validate_number(text):
        if text == "" and default is not None:
            return True
        if not text.isdigit():
            return "Please enter a valid number"
        num = int(text)
        if min_val is not None and num < min_val:
            return f"Number must be at least {min_val}"
        if max_val is not None and num > max_val:
            return f"Number must be at most {max_val}"
        return True

    try:
        result = questionary.text(
            message,
            default=str(default) if default else "",
            validate=validate_number,
            style=custom_style
        ).ask()

        if result == "" and default is not None:
            return default
        return int(result) if result else None
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return None


def get_text_input(message, default=""):
    """Get text input with autocomplete support."""
    try:
        return questionary.text(
            message,
            default=default,
            style=custom_style
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
        return None




def get_index_pattern_selection(es):
    """
    Interactive index pattern selection with auto-discovered patterns.

    Fetches all indices from the cluster, extracts common patterns,
    and displays an interactive selection menu.

    Args:
        es: Elasticsearch client instance

    Returns:
        str: Selected index pattern or None if cancelled
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from collections import defaultdict
    import re

    try:
        # Fetch all indices with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Discovering index patterns..."),
            transient=True,
        ) as progress:
            progress.add_task("fetch", total=None)
            indices_response = es.cat.indices(format="json", h="index")

        # Extract index names
        all_indices = []
        for idx in indices_response:
            index_name = idx.get("index")
            if index_name:
                all_indices.append(index_name)

        if not all_indices:
            console.print("\n[yellow]⚠️  No indices found in cluster.[/yellow]")
            console.print("[dim]Falling back to manual input...[/dim]\n")
            return get_text_input(
                "Enter index pattern (e.g., logs-*, * for all):",
                default="*"
            )

        # Extract patterns from index names
        patterns = set()
        prefix_groups = defaultdict(list)

        for index_name in all_indices:
            # Skip system indices for pattern extraction (but keep for matching)
            if is_system(index_name):
                # Add data stream patterns
                if index_name.startswith(".ds-"):
                    # Extract data stream pattern: .ds-logs-default-2024.01.01 -> .ds-logs-*
                    parts = index_name.split("-")
                    if len(parts) >= 3:
                        # .ds-<type>-<dataset>-<date> -> .ds-<type>-*
                        pattern = f"{parts[0]}-{parts[1]}-*"
                        patterns.add(pattern)
                continue

            # Split on common separators to find prefixes
            # Handle patterns like: logs-2024-01-01, filebeat-7.x-2024.01.01, metrics_system_cpu
            separators = ['-', '_', '.']

            # Try to extract prefix by splitting on separators
            for sep in separators:
                if sep in index_name:
                    parts = index_name.split(sep)
                    if len(parts) >= 2:
                        prefix = parts[0]
                        prefix_groups[prefix].append(index_name)
                        # Add pattern with wildcard
                        patterns.add(f"{prefix}-*")
                        patterns.add(f"{prefix}_*")
                        patterns.add(f"{prefix}.*")
                    break

            # Also check for date patterns and create more specific patterns
            # Match patterns like: logs-2024-01-01, logs-2024.01.01, logs-20240101
            date_pattern = re.compile(r'^([a-zA-Z0-9_-]+?)[-_.]?\d{4}[-_.]?\d{2}')
            match = date_pattern.match(index_name)
            if match:
                prefix = match.group(1)
                patterns.add(f"{prefix}-*")
                patterns.add(f"{prefix}_*")
                patterns.add(f"{prefix}.*")

        # Clean up patterns - remove duplicates and invalid ones
        valid_patterns = set()
        for pattern in patterns:
            # Remove patterns that are just "*" or end with multiple wildcards
            if pattern and pattern != "*" and not pattern.endswith("**"):
                # Verify pattern matches at least one index
                try:
                    # Simple check: does this pattern make sense?
                    if pattern.count("*") == 1 and len(pattern) > 2:
                        valid_patterns.add(pattern)
                except Exception:
                    pass

        # Build choices list
        choices = []

        # Add "All indices" at the top
        choices.append(questionary.Choice("* (All indices)", value="*"))

        # Add separator
        if valid_patterns:
            choices.append(questionary.Separator())

        # Add discovered patterns (sorted)
        for pattern in sorted(valid_patterns):
            choices.append(questionary.Choice(pattern, value=pattern))

        # Add separator and custom option
        choices.append(questionary.Separator())
        choices.append(questionary.Choice("Custom pattern...", value="__custom__"))

        # Display selection menu
        try:
            selected = questionary.select(
                "Select index pattern:",
                choices=choices,
                style=custom_style
            ).ask()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return None

        # Handle custom pattern selection
        if selected == "__custom__":
            return get_text_input(
                "Enter custom index pattern (e.g., logs-*, * for all):",
                default="*"
            )

        return selected

    except Exception as e:
        # Fallback to manual input on error
        console.print(f"\n[yellow]⚠️  Could not fetch indices: {e}[/yellow]")
        console.print("[dim]Falling back to manual input...[/dim]\n")
        return get_text_input(
            "Enter index pattern (e.g., logs-*, * for all):",
            default="*"
        )
