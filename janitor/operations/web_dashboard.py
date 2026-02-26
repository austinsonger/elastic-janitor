"""
Web dashboard launcher for the interactive menu.
"""
from ..config import console
from ..utils import show_breadcrumb


def option_launch_web_dashboard(es):
    """Launch the web-based monitoring dashboard in a background thread."""
    show_breadcrumb(["Main Menu", "Launch Web Dashboard"])

    # Lazy-check for optional dependencies
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        console.print()
        console.print("[red]Web Dashboard requires additional dependencies.[/red]")
        console.print("[yellow]Install with:[/yellow]  pip install fastapi uvicorn")
        console.print("[dim]Then restart Elastic Janitor and try again.[/dim]")
        console.print()
        return

    from ..web.manager import WebServerManager

    host = "127.0.0.1"
    port = 8000
    manager = WebServerManager(es, host=host, port=port)

    console.print()
    console.print("[cyan]Starting web dashboard server...[/cyan]")

    try:
        manager.start()
    except Exception as exc:
        console.print(f"[red]Failed to start web dashboard: {exc}[/red]")
        console.print("[dim]Port 8000 may already be in use.[/dim]")
        console.print()
        return

    if not manager.is_running():
        console.print("[red]Server failed to start.[/red]")
        console.print()
        return

    console.print()
    console.print(f"[bold green]Dashboard running at http://{host}:{port}[/bold green]")
    console.print("[dim]Open the URL above in your browser to view the dashboard.[/dim]")
    console.print()

    try:
        input("Press Enter to stop the dashboard server...")
    except KeyboardInterrupt:
        pass

    console.print()
    console.print("[cyan]Stopping web dashboard...[/cyan]")
    manager.stop()
    console.print("[green]Dashboard stopped.[/green]")
    console.print()
