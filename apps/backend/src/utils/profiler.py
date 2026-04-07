from __future__ import annotations

import functools
import json
import logging
import os
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Dedicated telemetry log file
TELEMETRY_LOG = Path("logs/telemetry.jsonl")

def execution_timer(node_name: str | None = None):
    """
    Decorator to measure raw execution time and peak memory usage.
    Logs data to logs/telemetry.jsonl.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = node_name or getattr(func, "__name__", "unknown_node")
            
            # Start profiling
            tracemalloc.start()
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # End profiling
                end_time = time.perf_counter()
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                
                duration_ms = (end_time - start_time) * 1000
                peak_mb = peak / (1024 * 1024)
                
                telemetry_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "node": name,
                    "execution_ms": round(duration_ms, 2),
                    "peak_memory_mb": round(peak_mb, 4),
                }
                
                # Write to 'Black Box' logger
                try:
                    # Ensure directory exists (redundant but safe)
                    TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
                    with open(TELEMETRY_LOG, "a", encoding="utf-8") as f:
                        f.write(json.dumps(telemetry_entry) + "\n")
                except Exception as e:
                    logger.error(f"Failed to write to telemetry log: {e}")
                    
        return wrapper
    return decorator
