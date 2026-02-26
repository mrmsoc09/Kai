"""
Rich UI components for Kaison K1 CLI.

Provides beautiful terminal output with progress bars, tables, panels, and styling.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.style import Style
from rich.theme import Theme
from typing import List, Dict, Any, Optional
from datetime import datetime

# Custom theme matching K1 branding (forest green + orange)
K1_THEME = Theme({
    "primary": "green",
    "secondary": "dark_orange",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "cyan",
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "blue",
    "finding": "bold cyan",
    "agent": "bold magenta",
    "workflow": "bold blue",
})

console = Console(theme=K1_THEME)


def print_header(text: str, subtitle: Optional[str] = None):
    """Print a styled header with optional subtitle."""
    header_text = Text()
    header_text.append("K1 ", style="bold green")
    header_text.append(text, style="bold white")

    if subtitle:
        content = f"{header_text}\n[dim]{subtitle}[/dim]"
    else:
        content = header_text

    console.print(Panel(
        content,
        border_style="green",
        padding=(0, 2)
    ))


def print_success(message: str):
    """Print a success message."""
    console.print(f"[success][OK][/success] {message}")


def print_error(message: str):
    """Print an error message."""
    console.print(f"[error][ERROR][/error] {message}")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[warning][WARN][/warning] {message}")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[info][INFO][/info] {message}")


def create_table(
    title: str,
    columns: List[str],
    rows: List[List[str]],
    styles: Optional[List[str]] = None
) -> Table:
    """Create a styled table."""
    table = Table(title=title, border_style="green")

    for i, col in enumerate(columns):
        style = styles[i] if styles and i < len(styles) else None
        table.add_column(col, style=style)

    for row in rows:
        table.add_row(*row)

    return table


def create_progress() -> Progress:
    """Create a progress bar for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console
    )


def create_status_panel(
    title: str,
    status: Dict[str, Any],
    style: str = "green"
) -> Panel:
    """Create a status panel showing key-value pairs."""
    content = ""
    for key, value in status.items():
        if isinstance(value, bool):
            value_str = "[green]Yes[/green]" if value else "[red]No[/red]"
        elif isinstance(value, (int, float)):
            value_str = f"[cyan]{value}[/cyan]"
        elif value is None:
            value_str = "[dim]N/A[/dim]"
        else:
            value_str = str(value)
        content += f"[bold]{key}:[/bold] {value_str}\n"

    return Panel(content.strip(), title=title, border_style=style)


def create_findings_table(findings: List[Dict[str, Any]]) -> Table:
    """Create a table of findings with severity coloring."""
    table = Table(title="Findings", border_style="green")

    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Severity")
    table.add_column("Type")
    table.add_column("Target")
    table.add_column("Status")
    table.add_column("Confidence")

    severity_styles = {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
        "info": "dim"
    }

    status_styles = {
        "new": "cyan",
        "validated": "green",
        "submitted": "blue",
        "accepted": "bold green",
        "rejected": "red",
        "duplicate": "dim"
    }

    for f in findings:
        severity = f.get("severity", "medium").lower()
        status = f.get("status", "new").lower()
        confidence = f.get("confidence", 0)

        confidence_str = f"{confidence:.0%}" if isinstance(confidence, float) else str(confidence)

        table.add_row(
            f.get("id", "")[:8],
            f.get("title", "Untitled")[:50],
            f"[{severity_styles.get(severity, 'white')}]{severity.upper()}[/{severity_styles.get(severity, 'white')}]",
            f.get("type", "unknown"),
            f.get("target", "")[:30],
            f"[{status_styles.get(status, 'white')}]{status}[/{status_styles.get(status, 'white')}]",
            confidence_str
        )

    return table


def create_agent_table(agents: List[Dict[str, Any]]) -> Table:
    """Create a table of agents with status indicators."""
    table = Table(title="Agents", border_style="magenta")

    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Objective")
    table.add_column("Status")
    table.add_column("Autonomy")
    table.add_column("Success Rate")

    status_styles = {
        "idle": "dim",
        "active": "green",
        "busy": "yellow",
        "error": "red",
        "stopped": "red"
    }

    for agent in agents:
        status = agent.get("status", "idle").lower()
        success_rate = agent.get("performance", {}).get("success_rate", 0)

        table.add_row(
            agent.get("agent_id", "")[:8],
            agent.get("name", "Unnamed"),
            agent.get("objective", "unknown"),
            f"[{status_styles.get(status, 'white')}]{status.upper()}[/{status_styles.get(status, 'white')}]",
            str(agent.get("autonomy_level", "N/A")),
            f"{success_rate:.0%}" if isinstance(success_rate, (int, float)) else str(success_rate)
        )

    return table


def create_workflow_table(workflows: List[Dict[str, Any]]) -> Table:
    """Create a table of workflows with progress indicators."""
    table = Table(title="Workflows", border_style="blue")

    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Status")
    table.add_column("Target")
    table.add_column("Progress")
    table.add_column("Created")

    status_styles = {
        "pending": "dim",
        "running": "green",
        "completed": "bold green",
        "failed": "red",
        "cancelled": "yellow"
    }

    for wf in workflows:
        status = wf.get("status", "pending").lower()
        progress = wf.get("progress", 0)
        created = wf.get("created_at", "")

        if isinstance(created, datetime):
            created_str = created.strftime("%Y-%m-%d %H:%M")
        else:
            created_str = str(created)[:16] if created else "N/A"

        progress_bar = "=" * int(progress / 10) + "-" * (10 - int(progress / 10))

        table.add_row(
            wf.get("workflow_id", wf.get("id", ""))[:8],
            wf.get("name", "Untitled"),
            f"[{status_styles.get(status, 'white')}]{status.upper()}[/{status_styles.get(status, 'white')}]",
            wf.get("target", "")[:25],
            f"[{progress_bar}] {progress}%",
            created_str
        )

    return table


def confirm_action(message: str, default: bool = False) -> bool:
    """Prompt user for confirmation."""
    return Confirm.ask(message, default=default, console=console)


def prompt_input(message: str, default: Optional[str] = None, password: bool = False) -> str:
    """Prompt user for input."""
    return Prompt.ask(message, default=default, password=password, console=console)


def format_json(data: Dict[str, Any]) -> str:
    """Format JSON data for display."""
    import json
    return json.dumps(data, indent=2, default=str)


def print_json(data: Dict[str, Any], title: Optional[str] = None):
    """Print formatted JSON data."""
    from rich.syntax import Syntax
    import json

    json_str = json.dumps(data, indent=2, default=str)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)

    if title:
        console.print(Panel(syntax, title=title, border_style="green"))
    else:
        console.print(syntax)


def print_divider(char: str = "─"):
    """Print a divider line."""
    console.print(char * console.width, style="dim")


def create_hunt_summary(result: Dict[str, Any]) -> Panel:
    """Create a summary panel for hunt results."""
    findings_count = result.get("findings_count", 0)
    high_severity = result.get("high_severity_count", 0)
    duration = result.get("duration", "N/A")
    target = result.get("target", "Unknown")

    content = f"""
[bold]Target:[/bold] {target}
[bold]Duration:[/bold] {duration}
[bold]Total Findings:[/bold] [cyan]{findings_count}[/cyan]
[bold]High Severity:[/bold] [{'red' if high_severity > 0 else 'green'}]{high_severity}[/{'red' if high_severity > 0 else 'green'}]
"""

    style = "red" if high_severity > 0 else "green"
    return Panel(content.strip(), title="Hunt Summary", border_style=style)
