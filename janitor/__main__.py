"""
Entry point for running Elastic Janitor as a module.

Usage:
    # Interactive menu mode (no arguments)
    python -m janitor

    # CLI mode (with arguments)
    python -m janitor cluster health
    python -m janitor index largest --top 25
    python -m janitor datastream clean --retention 90d --dry-run
"""
import sys


def main():
    """
    Main entry point that supports both CLI and menu modes.

    - If arguments are provided: Run in CLI mode
    - If no arguments: Run in interactive menu mode
    """
    # Check if arguments were provided (excluding the script name)
    if len(sys.argv) > 1:
        # CLI mode - import and run CLI
        from .cli import cli
        cli()
    else:
        # Menu mode - import and run interactive menu
        from .menus import main as menu_main
        menu_main()


if __name__ == "__main__":
    main()

