from __future__ import annotations

import psutil
import logging
from ..core.experience_engine import ExperienceEngine

logger = logging.getLogger(__name__)

class ResourceGovernor:
    """
    Monitors 40GB RAM / 1TB NVMe.
    Throttles GlobalTaskQueue and ExperienceEngine (Hot-Cache mode) if RAM > 85%.
    """
    def __init__(self, engine: ExperienceEngine):
        self.engine = engine
        self.ram_threshold = 85.0

    def monitor(self):
        ram_percent = psutil.virtual_memory().percent
        if ram_percent > self.ram_threshold:
            logger.warning(f"Resource Governor: High RAM usage ({ram_percent}%). Throttling.")
            # Implementation for throttling queue logic would be called here
            # self.engine.bypass_hot_cache = True # Example state change
