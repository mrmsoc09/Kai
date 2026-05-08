"""Celery tasks for training data management."""

import logging
from pathlib import Path

from ..celery_app import celery_app
from ..services.report_intelligence_engine import ReportIntelligenceEngine
from ..core.persistence import get_db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="training.update_real_training_data")
def update_real_training_data_task(self, data_dir: str = "/home/k1-admin/Kai/real_scan_data"):
    """Celery task to update training data by chunking real scan data."""
    async def _update():
        async for db in get_db():
            engine = ReportIntelligenceEngine(db)
            result = await engine.chunk_real_scan_data_for_training(data_dir)
            logger.info(f"Updated training data: {result}")
            return result

    import asyncio
    return asyncio.run(_update())


@celery_app.task(bind=True, name="training.generate_synthetic_data")
def generate_synthetic_data_task(self, output_dir: str = "/home/k1-admin/Kai/synthetic_data", chains: int = 10, zero_days: int = 5):
    """Celery task to generate advanced synthetic data."""
    from ...scripts.generate_advanced_synthetic_data import AdvancedSyntheticDataGenerator

    generator = AdvancedSyntheticDataGenerator(output_dir)
    # Override counts
    original_chains = generator.generate_vuln_chains
    original_zero = generator.generate_zero_day_scenarios

    def new_chains():
        return original_chains(chains)

    def new_zero():
        return original_zero(zero_days)

    generator.generate_vuln_chains = new_chains
    generator.generate_zero_day_scenarios = new_zero

    results = generator.save_all()
    logger.info(f"Generated synthetic data: {results}")
    return results