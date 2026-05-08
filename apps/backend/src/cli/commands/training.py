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
def generate_advanced_synthetic(output_dir: str, chains: int, zero_days: int):
    """Generate advanced synthetic data with chains and zero-days."""
    from ....scripts.generate_advanced_synthetic_data import AdvancedSyntheticDataGenerator

    generator = AdvancedSyntheticDataGenerator(output_dir)
    # Override counts by modifying the generator
    original_chains = generator.generate_vuln_chains
    original_zero = generator.generate_zero_day_scenarios

    def new_chains():
        return original_chains(chains)

    def new_zero():
        return original_zero(zero_days)

    generator.generate_vuln_chains = new_chains
    generator.generate_zero_day_scenarios = new_zero

    results = generator.save_all()
    console.print(f"[green]✓[/green] Generated advanced synthetic data: {results}")


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