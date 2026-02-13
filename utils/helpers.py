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

