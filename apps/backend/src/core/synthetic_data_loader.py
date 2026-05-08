"""Synthetic Data Loader for Kai Platform

Loads synthetic data into the platform for testing and training purposes.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.bugbounty import Target, DNSRecord, LiveService, WebApplication, URLRecord
from .persistence import get_db


class SyntheticDataLoader:
    """Loads synthetic data from files into the database."""

    def __init__(self, data_dir: str = "/home/k1-admin/Kai/synthetic_data"):
        self.data_dir = Path(data_dir)

    async def load_all(self, db: AsyncSession) -> Dict[str, int]:
        """Load all synthetic data types."""
        results = {}
        results.update(await self.load_targets(db))
        results.update(await self.load_artifacts(db))
        return results

    async def load_targets(self, db: AsyncSession) -> Dict[str, int]:
        """Load synthetic targets."""
        targets_file = self.data_dir / "targets" / "mock_targets.json"
        if not targets_file.exists():
            return {"targets_loaded": 0}

        with open(targets_file, "r") as f:
            targets_data = json.load(f)

        loaded = 0
        for target_data in targets_data:
            target = Target(**target_data)
            db.add(target)
            loaded += 1

        await db.commit()
        return {"targets_loaded": loaded}

    async def load_artifacts(self, db: AsyncSession) -> Dict[str, int]:
        """Load synthetic artifacts."""
        results = {}

        # DNS Records
        dns_file = self.data_dir / "artifacts" / "mock_dns_records.json"
        if dns_file.exists():
            with open(dns_file, "r") as f:
                dns_data = json.load(f)
            for record_data in dns_data:
                record = DNSRecord(**record_data)
                db.add(record)
            results["dns_records_loaded"] = len(dns_data)

        # Live Services
        services_file = self.data_dir / "artifacts" / "mock_live_services.json"
        if services_file.exists():
            with open(services_file, "r") as f:
                services_data = json.load(f)
            for service_data in services_data:
                service = LiveService(**service_data)
                db.add(service)
            results["live_services_loaded"] = len(services_data)

        # Web Applications
        apps_file = self.data_dir / "artifacts" / "mock_web_applications.json"
        if apps_file.exists():
            with open(apps_file, "r") as f:
                apps_data = json.load(f)
            for app_data in apps_data:
                app = WebApplication(**app_data)
                db.add(app)
            results["web_applications_loaded"] = len(apps_data)

        # URL Records
        urls_file = self.data_dir / "artifacts" / "mock_url_records.json"
        if urls_file.exists():
            with open(urls_file, "r") as f:
                urls_data = json.load(f)
            for url_data in urls_data:
                url = URLRecord(**url_data)
                db.add(url)
            results["url_records_loaded"] = len(urls_data)

        await db.commit()
        return results


# CLI integration
async def load_synthetic_data():
    """CLI command to load synthetic data."""
    async for db in get_db():
        loader = SyntheticDataLoader()
        results = await loader.load_all(db)
        print(f"Loaded synthetic data: {results}")
        break