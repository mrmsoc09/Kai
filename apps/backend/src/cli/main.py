#!/usr/bin/env python3
"""
Kaison K1 Command Line Interface

Main entry point for the kai-cli command.

Usage:
    kai-cli --help
    kai-cli hunt start example.com
    kai-cli scan run example.com --tool nuclei
    kai-cli agent list
    kai-cli workflow list
    kai-cli findings list
    kai-cli orchestrator status
    kai-cli bug-bounty programs
"""

import click
import sys
from typing import Optional

from .ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_info,
)

from .commands import (
    hunt,
    scan,
    agent,
    workflow,
    findings,
    orchestrator,
    tools,
    bug_bounty,
)


# Version
__version__ = "1.0.0"


@click.group()
@click.version_option(version=__version__, prog_name="kai-cli")
@click.option("--api-url", envvar="K1_API_URL", default="http://localhost:8000", help="K1 API URL")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.pass_context
def cli(ctx: click.Context, api_url: str, verbose: bool, quiet: bool):
    """
    Kaison K1 - Unified Automated Bug Bounty Intelligence Platform

    Full-featured CLI for headless and automated operation.

    \b
    Commands:
      hunt         Vulnerability hunting operations
      scan         Security scanning operations
      agent        Agent management
      workflow     Workflow management
      findings     Finding management
      orchestrator Orchestrator management
      tools        Tool catalog and readiness checks
      bug-bounty   Continuous bug bounty program scheduling and triage

    \b
    Examples:
      kai-cli hunt start example.com --watch
      kai-cli scan run example.com --tool nuclei
      kai-cli agent list
      kai-cli findings export --format json -o findings.json

    \b
    Environment Variables:
      K1_API_URL   API server URL (default: http://localhost:8000)

    For more information, visit: https://github.com/kaison/k1
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Store global options in context
    ctx.obj["api_url"] = api_url
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


# Register command groups
cli.add_command(hunt)
cli.add_command(scan)
cli.add_command(agent)
cli.add_command(workflow)
cli.add_command(findings)
cli.add_command(orchestrator)
cli.add_command(tools)
cli.add_command(bug_bounty)


@cli.command()
def status():
    """Show overall K1 system status."""
    print_header("Kaison K1 Status", "Unified Automated Bug Bounty Intelligence Platform")

    try:
        import httpx
        client = httpx.Client(base_url="http://localhost:8000", timeout=10.0)

        # Check API health
        try:
            response = client.get("/healthz")
            api_status = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            api_status = "unreachable"

        # Check Agent Zero
        try:
            response = client.get("/api/v1/agent-zero/health")
            agent_zero_status = "healthy" if response.status_code == 200 else "degraded"
        except Exception:
            agent_zero_status = "unavailable"

        # Check Autonomous System
        try:
            response = client.get("/api/autonomous/status")
            if response.status_code == 200:
                data = response.json()
                agents = data.get("autonomous_agents", {})
                autonomous_status = f"healthy ({agents.get('total_agents', 0)} agents)"
            else:
                autonomous_status = "degraded"
        except Exception:
            autonomous_status = "unavailable"

        # Display status
        from .ui import create_status_panel

        status_data = {
            "API Server": api_status,
            "Agent Zero": agent_zero_status,
            "Autonomous System": autonomous_status,
            "Version": __version__,
        }

        console.print(create_status_panel("System Status", status_data))

        if api_status == "healthy":
            print_success("K1 is operational")
        else:
            print_error("K1 has issues - check component status")

    except ImportError:
        print_error("httpx not installed. Run: pip install httpx")
    except Exception as e:
        print_error(f"Error checking status: {e}")


@cli.command()
def interactive():
    """Start interactive CLI mode."""
    print_header("Interactive Mode", "Type 'help' for commands, 'exit' to quit")

    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from pathlib import Path

    history_file = Path.home() / ".kai_history"
    session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory()
    )

    commands = {
        "help": "Show available commands",
        "status": "Show system status",
        "hunt <target>": "Start hunt on target",
        "scan <target>": "Run scan on target",
        "agents": "List agents",
        "workflows": "List workflows",
        "findings": "List findings",
        "exit": "Exit interactive mode",
    }

    while True:
        try:
            user_input = session.prompt("kai> ").strip()

            if not user_input:
                continue

            if user_input == "exit" or user_input == "quit":
                print_info("Goodbye!")
                break

            if user_input == "help":
                console.print("\n[bold]Available Commands:[/bold]")
                for cmd, desc in commands.items():
                    console.print(f"  [cyan]{cmd}[/cyan] - {desc}")
                console.print()
                continue

            if user_input == "status":
                ctx = click.Context(cli)
                ctx.invoke(status)
                continue

            if user_input == "agents":
                ctx = click.Context(agent)
                ctx.invoke(agent.commands["list"])
                continue

            if user_input == "workflows":
                ctx = click.Context(workflow)
                ctx.invoke(workflow.commands["list"])
                continue

            if user_input == "findings":
                ctx = click.Context(findings)
                ctx.invoke(findings.commands["list"])
                continue

            if user_input.startswith("hunt "):
                target = user_input[5:].strip()
                if target:
                    ctx = click.Context(hunt)
                    ctx.invoke(hunt.commands["start"], target=target)
                else:
                    print_error("Usage: hunt <target>")
                continue

            if user_input.startswith("scan "):
                target = user_input[5:].strip()
                if target:
                    ctx = click.Context(scan)
                    ctx.invoke(scan.commands["run"], target=target)
                else:
                    print_error("Usage: scan <target>")
                continue

            print_error(f"Unknown command: {user_input}")
            print_info("Type 'help' for available commands")

        except KeyboardInterrupt:
            continue
        except EOFError:
            print_info("\nGoodbye!")
            break


@cli.command()
@click.argument("target")
@click.option("--scope", "-s", type=click.Path(exists=True), help="Scope file")
@click.option("--output", "-o", type=click.Path(), help="Output file")
def quick_hunt(target: str, scope: Optional[str], output: Optional[str]):
    """Quick hunt shortcut - runs full hunt workflow.

    Equivalent to: kai-cli hunt start <target> --watch
    """
    ctx = click.Context(hunt)
    ctx.invoke(
        hunt.commands["start"],
        target=target,
        scope=scope,
        intensity="normal",
        watch=True,
        dry_run=False,
        tier=1,
        output=output,
        output_format="json"
    )


@cli.command()
@click.argument("target")
@click.option("--output", "-o", type=click.Path(), help="Output file")
def quick_scan(target: str, output: Optional[str]):
    """Quick scan shortcut - runs nuclei scan.

    Equivalent to: kai-cli scan run <target> --tool nuclei
    """
    ctx = click.Context(scan)
    ctx.invoke(
        scan.commands["run"],
        target=target,
        tool=("nuclei",),
        templates=None,
        severity="medium",
        timeout=300,
        output=output,
        output_format="json",
        parallel=False
    )


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        print_info("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
