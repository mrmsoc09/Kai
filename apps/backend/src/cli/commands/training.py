"""Training data management commands."""

import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ...core.persistence import get_db
from ...services.report_intelligence_engine import ReportIntelligenceEngine

console = Console()


@click.group()
def training():
    """Training data management commands."""
    pass


@training.command()
@click.option(
    "--data-dir",
    default="/home/k1-admin/Kai/real_scan_data",
    help="Directory containing real scan data"
)
def update_real_training_data(data_dir: str):
    """Update training data by chunking real scan data."""
    async def _update():
        async for db in get_db():
            engine = ReportIntelligenceEngine(db)
            result = await engine.chunk_real_scan_data_for_training(data_dir)
            console.print(f"[green]✓[/green] Updated training data: {result}")
            break

    asyncio.run(_update())


@training.command()
@click.option(
    "--data-dir",
    default="/home/k1-admin/Kai/synthetic_data",
    help="Directory containing synthetic data"
)
def load_synthetic_data(data_dir: str):
    """Load synthetic data into the platform."""
    async def _load():
        from ...core.synthetic_data_loader import SyntheticDataLoader
        async for db in get_db():
            loader = SyntheticDataLoader(data_dir)
            result = await loader.load_all(db)
            console.print(f"[green]✓[/green] Loaded synthetic data: {result}")
            break

    asyncio.run(_load())


@training.command()
@click.option(
    "--output-dir",
    default="/home/k1-admin/Kai/synthetic_data",
    help="Output directory for generated data"
)
@click.option(
    "--chains",
    default=10,
    help="Number of vuln chains to generate"
)
@click.option(
    "--zero-days",
    default=5,
    help="Number of zero-day scenarios to generate"
)
@click.option(
    "--cve-entries",
    default=50,
    help="Number of CVE database entries to generate"
)
@click.option(
    "--exploit-scenarios",
    default=30,
    help="Number of exploitability validation scenarios to generate"
)
@click.option(
    "--scanning-scenarios",
    default=20,
    help="Number of scanning training scenarios to generate"
)
@click.option(
    "--knowledge-nodes",
    default=100,
    help="Number of knowledge graph nodes to generate"
)
@click.option(
    "--agent-training",
    default=200,
    help="Number of agent training examples to generate"
)
def generate_advanced_synthetic(
    output_dir: str,
    chains: int,
    zero_days: int,
    cve_entries: int,
    exploit_scenarios: int,
    scanning_scenarios: int,
    knowledge_nodes: int,
    agent_training: int
):
    """Generate comprehensive advanced synthetic data for AI training."""
    from ....scripts.generate_advanced_synthetic_data import AdvancedSyntheticDataGenerator

    generator = AdvancedSyntheticDataGenerator(output_dir)

    # Generate all data types with specified counts
    vuln_chains = generator.generate_vuln_chains(chains)
    zero_day_scenarios = generator.generate_zero_day_scenarios(zero_days)
    cve_database = generator.generate_cve_database_entries(cve_entries)
    exploitability_scenarios = generator.generate_exploitability_validation_scenarios(exploit_scenarios)
    scanning_training = generator.generate_scanning_training_scenarios(scanning_scenarios)
    knowledge_graph = generator.generate_knowledge_graph_data(knowledge_nodes)
    agent_training_data = generator.generate_agent_training_data(agent_training)

    # Save all data
    results = {
        "vuln_chains": len(vuln_chains),
        "zero_day_scenarios": len(zero_day_scenarios),
        "cve_entries": len(cve_database),
        "exploitability_scenarios": len(exploitability_scenarios),
        "scanning_scenarios": len(scanning_training),
        "knowledge_graph_nodes": len(knowledge_graph["nodes"]),
        "knowledge_graph_relationships": len(knowledge_graph["relationships"]),
        "agent_training_examples": len(agent_training_data)
    }

    # Save files
    import json
    from pathlib import Path

    output_path = Path(output_dir)

    # Save each data type
    (output_path / "advanced" / "vuln_chains.json").parent.mkdir(exist_ok=True, parents=True)
    with open(output_path / "advanced" / "vuln_chains.json", "w") as f:
        json.dump(vuln_chains, f, indent=2)

    with open(output_path / "advanced" / "zero_days.json", "w") as f:
        json.dump(zero_day_scenarios, f, indent=2)

    with open(output_path / "advanced" / "cve_database.json", "w") as f:
        json.dump(cve_database, f, indent=2)

    with open(output_path / "advanced" / "exploitability_scenarios.json", "w") as f:
        json.dump(exploitability_scenarios, f, indent=2)

    with open(output_path / "advanced" / "scanning_scenarios.json", "w") as f:
        json.dump(scanning_training, f, indent=2)

    with open(output_path / "advanced" / "knowledge_graph.json", "w") as f:
        json.dump(knowledge_graph, f, indent=2)

    with open(output_path / "training" / "agent_training.json", "w") as f:
        json.dump(agent_training_data, f, indent=2)

    # Generate legacy prompts for backward compatibility
    prompts = generator.generate_training_prompts(vuln_chains, zero_day_scenarios)
    with open(output_path / "training" / "advanced_training.json", "w") as f:
        json.dump(prompts, f, indent=2)

    results["legacy_prompts"] = len(prompts)

    console.print(f"[green]✓[/green] Generated comprehensive advanced synthetic data: {results}")


@training.command()
def schedule_daily_updates():
    """Set up daily cron job for training data updates."""
    import subprocess

    script_path = Path("/home/k1-admin/Kai/scripts/daily_training_update.sh")

    # Add to crontab (runs at 6 AM daily)
    cron_job = f"0 6 * * * {script_path}"

    try:
        # Check if cron job already exists
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if cron_job in result.stdout:
            console.print("[yellow]⚠[/yellow] Cron job already exists")
            return

        # Add the job
        new_crontab = result.stdout + cron_job + "\n"
        subprocess.run(["crontab", "-"], input=new_crontab, text=True)
        console.print(f"[green]✓[/green] Added daily cron job: {cron_job}")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to set up cron job: {e}")
        console.print("Manual setup: Run 'crontab -e' and add:")
        console.print(cron_job)