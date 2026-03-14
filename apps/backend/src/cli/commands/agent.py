"""
Agent command for managing K1 agents.

Usage:
    kai-cli agent status
    kai-cli agent start recon
    kai-cli agent stop agent-123
    kai-cli agent list
"""

import click
import asyncio
import json
from typing import Optional
from datetime import datetime

from ..ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_agent_table,
    create_status_panel,
    create_table,
    confirm_action,
)


def get_api_client():
    """Get the K1 API client."""
    try:
        import httpx
        return httpx.Client(base_url="http://localhost:8080", timeout=60.0)
    except ImportError:
        return None


@click.group()
def agent():
    """Agent management operations."""
    pass


@agent.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all agents including stopped")
@click.option("--objective", "-o", type=str, help="Filter by objective")
def list_agents(show_all: bool, objective: Optional[str]):
    """List all K1 agents."""
    print_header("K1 Agents")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/api/autonomous/agents")

        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])

            # Filter by status
            if not show_all:
                agents = [a for a in agents if a.get("status") not in ["stopped", "terminated"]]

            # Filter by objective
            if objective:
                agents = [a for a in agents if objective.lower() in a.get("objective", "").lower()]

            if agents:
                console.print(create_agent_table(agents))

                # Team metrics
                metrics = data.get("team_metrics", {})
                if metrics:
                    console.print()
                    console.print(create_status_panel("Team Metrics", {
                        "Learning Rate": f"{metrics.get('learning_rate', 0):.2f}",
                        "Cooperation": f"{metrics.get('cooperation_level', 0):.2f}",
                        "Efficiency": f"{metrics.get('efficiency_score', 0):.2f}",
                    }))
            else:
                print_info("No agents found")
        else:
            print_error("Failed to fetch agents")

    except Exception as e:
        print_error(f"Error fetching agents: {e}")


@agent.command("status")
@click.argument("agent_id", required=False)
def agent_status(agent_id: Optional[str]):
    """Show status of a specific agent or overall system."""
    print_header("Agent Status")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        if agent_id:
            response = client.get(f"/api/autonomous/agents/{agent_id}")

            if response.status_code == 200:
                agent_data = response.json()
                _display_agent_details(agent_data)
            else:
                print_error(f"Agent not found: {agent_id}")
        else:
            response = client.get("/api/autonomous/status")

            if response.status_code == 200:
                data = response.json()
                _display_system_status(data)
            else:
                print_error("Failed to fetch system status")

    except Exception as e:
        print_error(f"Error fetching status: {e}")


@agent.command("spawn")
@click.argument("objective")
@click.option("--name", "-n", type=str, help="Agent name")
@click.option("--autonomy", "-a", type=click.IntRange(1, 5), default=3, help="Autonomy level (1-5)")
def spawn_agent(objective: str, name: Optional[str], autonomy: int):
    """Spawn a new specialist agent.

    OBJECTIVE can be: recon, scanning, exploitation, validation, analysis

    Examples:
        kai-cli agent spawn recon --name "Recon Agent"
        kai-cli agent spawn validation --autonomy 4
    """
    print_header("Spawn Agent", f"Objective: {objective}")

    valid_objectives = ["recon", "scanning", "exploitation", "validation", "analysis", "chain_analysis"]
    if objective.lower() not in valid_objectives:
        print_error(f"Invalid objective. Choose from: {', '.join(valid_objectives)}")
        return

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        params = {"objective": objective.upper()}
        if name:
            params["name"] = name

        response = client.post("/api/autonomous/agents/spawn", params=params)

        if response.status_code == 200:
            data = response.json()
            print_success(f"Agent spawned successfully")
            console.print(f"  ID: [cyan]{data.get('agent_id')}[/cyan]")
            console.print(f"  Name: {data.get('name')}")
            console.print(f"  Objective: {data.get('objective')}")
            console.print(f"  Status: [green]{data.get('status')}[/green]")
        else:
            print_error(f"Failed to spawn agent: {response.text}")

    except Exception as e:
        print_error(f"Error spawning agent: {e}")


@agent.command("execute")
@click.argument("agent_id")
@click.option("--task", "-t", required=True, help="Task description or JSON")
@click.option("--wait", "-w", is_flag=True, help="Wait for task completion")
def execute_task(agent_id: str, task: str, wait: bool):
    """Execute a task using a specific agent.

    Examples:
        kai-cli agent execute agent-123 --task "Scan example.com for XSS"
        kai-cli agent execute agent-123 --task '{"type": "scan", "target": "example.com"}'
    """
    print_header("Execute Task", f"Agent: {agent_id}")

    # Parse task
    try:
        task_data = json.loads(task)
    except json.JSONDecodeError:
        task_data = {"description": task}

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.post(f"/api/autonomous/agents/{agent_id}/execute", json=task_data)

        if response.status_code == 200:
            data = response.json()
            print_success("Task executed")

            # Display result
            result = data.get("result", {})
            console.print(f"\n[bold]Action:[/bold] {data.get('action', 'N/A')}")
            console.print(f"[bold]Result:[/bold] {result.get('status', 'completed')}")

            # Learning metrics
            learning = data.get("agent_learning", {})
            if learning:
                console.print(f"\n[dim]Success Rate: {learning.get('new_success_rate', 0):.1%}[/dim]")
                console.print(f"[dim]Improvement: {learning.get('improvement_rate', 0):.1%}[/dim]")
        else:
            print_error(f"Task execution failed: {response.text}")

    except Exception as e:
        print_error(f"Error executing task: {e}")


@agent.command("objectives")
def list_objectives():
    """List available agent objectives."""
    print_header("Agent Objectives")

    objectives = [
        ["RECON", "Reconnaissance and information gathering", "TIER 0"],
        ["SCANNING", "Vulnerability scanning", "TIER 0-1"],
        ["EXPLOITATION", "Vulnerability exploitation (requires approval)", "TIER 2"],
        ["VALIDATION", "Finding validation and verification", "TIER 1"],
        ["ANALYSIS", "Data analysis and correlation", "TIER 0"],
        ["CHAIN_ANALYSIS", "Exploit chain analysis", "TIER 1"],
    ]

    table = create_table(
        "Available Objectives",
        ["Objective", "Description", "Tier"],
        objectives,
        styles=["cyan", None, "yellow"]
    )

    console.print(table)


@agent.command("reasoning")
@click.argument("problem")
@click.option("--method", "-m", type=click.Choice(["chain", "tree", "decompose"]), default="chain", help="Reasoning method")
@click.option("--steps", "-s", type=int, default=5, help="Max reasoning steps")
def run_reasoning(problem: str, method: str, steps: int):
    """Run autonomous reasoning on a problem.

    Examples:
        kai-cli agent reasoning "How to exploit this SQL injection" --method chain
        kai-cli agent reasoning "Analyze attack surface for example.com" --method tree
    """
    print_header("Autonomous Reasoning", f"Method: {method}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        if method == "chain":
            endpoint = "/api/autonomous/reasoning/chain-of-thought"
            payload = {"problem": problem, "max_steps": steps}
        elif method == "tree":
            endpoint = "/api/autonomous/reasoning/tree-of-thoughts"
            payload = {"problem": problem, "num_branches": 3}
        else:
            endpoint = "/api/autonomous/reasoning/decompose"
            payload = {"problem": problem, "max_depth": 3}

        print_info("Running reasoning...")
        response = client.post(endpoint, json=payload)

        if response.status_code == 200:
            data = response.json()

            if method == "chain":
                console.print(f"\n[bold]Conclusion:[/bold] {data.get('conclusion', 'N/A')}")
                console.print(f"[bold]Confidence:[/bold] {data.get('confidence', 0):.1%}")

                trace = data.get("reasoning_trace", {})
                if trace.get("steps"):
                    console.print("\n[bold]Reasoning Steps:[/bold]")
                    for i, step in enumerate(trace["steps"], 1):
                        console.print(f"  {i}. {step}")

            elif method == "tree":
                console.print("\n[bold]Reasoning Paths:[/bold]")
                for path in data.get("paths", [])[:5]:
                    console.print(f"  - {path.get('conclusion', 'N/A')} (score: {path.get('score', 0):.2f})")

            else:
                console.print("\n[bold]Problem Decomposition:[/bold]")
                for sub in data.get("subproblems", []):
                    console.print(f"  - {sub.get('description', 'N/A')}")

            print_success("Reasoning complete")
        else:
            print_error(f"Reasoning failed: {response.text}")

    except Exception as e:
        print_error(f"Error running reasoning: {e}")


@agent.command("swarm")
@click.option("--status", "-s", is_flag=True, help="Show swarm status")
@click.option("--coordinate", "-c", type=str, help="Coordinate swarm on task")
def swarm_operations(status: bool, coordinate: Optional[str]):
    """Swarm coordination operations."""
    print_header("Swarm Coordination")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        if coordinate:
            response = client.post("/api/autonomous/swarm/coordinate", json={"description": coordinate})
            if response.status_code == 200:
                data = response.json()
                print_success(f"Swarm coordinated on task")
                console.print(f"  Agents involved: {data.get('agents_involved', 0)}")
                console.print(f"  Pattern: {data.get('collaboration_pattern', 'N/A')}")
            else:
                print_error(f"Coordination failed: {response.text}")
        else:
            response = client.get("/api/autonomous/swarm/status")
            if response.status_code == 200:
                data = response.json()
                console.print(create_status_panel("Swarm Status", {
                    "Agent Count": data.get("agent_count", 0),
                    "Intelligence Level": f"{data.get('swarm_intelligence', 0):.2f}",
                    "Collective Efficiency": f"{data.get('collective_efficiency', 0):.2f}",
                    "Active Pattern": data.get("active_pattern", "N/A"),
                }))
            else:
                print_error("Failed to fetch swarm status")

    except Exception as e:
        print_error(f"Swarm operation error: {e}")


# Helper functions

def _display_agent_details(agent: dict):
    """Display detailed agent information."""
    status = {
        "Agent ID": agent.get("agent_id"),
        "Name": agent.get("name"),
        "Objective": agent.get("primary_objective", agent.get("objective")),
        "Status": agent.get("status"),
        "Autonomy Level": agent.get("autonomy_level"),
        "Decision Mode": agent.get("decision_mode"),
    }

    console.print(create_status_panel("Agent Details", status))

    # Performance metrics
    perf = agent.get("performance", agent.get("memory", {}))
    if perf:
        console.print()
        console.print(create_status_panel("Performance", {
            "Success Rate": f"{perf.get('success_rate', perf.get('avg_success_rate', 0)):.1%}",
            "Success Count": perf.get("success_count", 0),
            "Failure Count": perf.get("failure_count", 0),
            "Improvement Rate": f"{perf.get('improvement_rate', 0):.1%}",
        }))

    # Skills
    skills = agent.get("skills", perf.get("skill_levels", {}))
    if skills:
        console.print()
        skill_rows = [[k, f"{v:.2f}"] for k, v in skills.items()]
        console.print(create_table("Skills", ["Skill", "Level"], skill_rows))


def _display_system_status(data: dict):
    """Display overall autonomous system status."""
    # Agents
    agents = data.get("autonomous_agents", {})
    if agents:
        console.print(create_status_panel("Autonomous Agents", {
            "Total Agents": agents.get("total_agents", 0),
            "Team Efficiency": f"{agents.get('team_efficiency', 0):.2f}",
            "Learning Rate": f"{agents.get('team_learning_rate', 0):.2f}",
            "Cooperation": f"{agents.get('team_cooperation', 0):.2f}",
        }))

    # Reasoning engine
    reasoning = data.get("reasoning_engine", {})
    if reasoning:
        console.print()
        console.print(create_status_panel("Reasoning Engine", {
            "Total Traces": reasoning.get("total_traces", 0),
            "Avg Depth": f"{reasoning.get('avg_depth', 0):.1f}",
            "Avg Confidence": f"{reasoning.get('avg_confidence', 0):.1%}",
            "Learned Patterns": reasoning.get("learned_patterns", 0),
        }))

    # Swarm
    swarm = data.get("swarm_coordinator", {})
    if swarm:
        console.print()
        console.print(create_status_panel("Swarm Coordinator", {
            "Agent Count": swarm.get("agent_count", 0),
            "Intelligence": f"{swarm.get('swarm_intelligence', 0):.2f}",
            "Efficiency": f"{swarm.get('collective_efficiency', 0):.2f}",
            "Active Pattern": swarm.get("active_pattern", "N/A"),
        }))
