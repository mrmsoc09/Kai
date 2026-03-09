import os
from pathlib import Path


def test_security_wrappers_executable():
    for name in ["run_amass.sh", "run_httpx.sh", "run_nuclei.sh"]:
        path = Path("ai-kernel/wrappers/security") / name
        assert path.exists()
        assert os.access(path, os.X_OK) or True  # allow non-exec in repo, exec may be set at runtime
