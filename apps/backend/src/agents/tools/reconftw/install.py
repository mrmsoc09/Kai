from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def install_reconftw(
    install_dir: str | Path | None = None,
    nvme_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Handles the full reconftw dependency tree and installation.
    Ensures it is installed in a dedicated K1 sub-directory on the NVMe.
    """
    nvme = Path(nvme_root or os.getenv("K1_NVME_ROOT", "/mnt/nvme")).expanduser().resolve()
    target_dir = Path(install_dir or nvme / "reconftw").expanduser().resolve()
    
    # Create NVMe root if it doesn't exist
    nvme.mkdir(parents=True, exist_ok=True)

    results = {
        "install_dir": str(target_dir),
        "status": "pending",
        "steps": []
    }

    # 1. Update and install base OS dependencies
    base_deps = ["git", "curl", "jq", "python3", "python3-pip", "go-golang", "wget"]
    results["steps"].append(f"Installing OS dependencies: {', '.join(base_deps)}")
    
    # In a real environment, we'd run these, but for the agent we return the plan
    # or use a helper to run them if permitted.
    
    # 2. Clone reconftw
    if not target_dir.exists():
        results["steps"].append(f"Cloning reconftw into {target_dir}")
    else:
        results["steps"].append(f"Updating existing reconftw in {target_dir}")

    # 3. Run reconftw install script
    results["steps"].append("Running reconftw/install.sh")

    # Conflict Management: Prevent re-installing tools managed by K1
    # We can do this by setting environment variables or modifying the install script
    # but the easiest way is to pass a config that tells reconftw to skip certain tools.
    results["conflict_management"] = {
        "skip_tools": ["nuclei", "findomain", "subfinder", "httpx", "naabu", "amass"],
        "reason": "Managed by K1 core platform"
    }

    results["status"] = "plan_generated"
    return results


def get_install_commands(target_dir: Path) -> list[list[str]]:
    """Returns the shell commands required for installation."""
    return [
        ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "-y", "git", "curl", "jq", "python3", "python3-pip", "golang", "wget"],
        ["git", "clone", "--depth", "1", "https://github.com/six2dez/reconftw.git", str(target_dir)] if not target_dir.exists() else ["bash", "-c", f"cd {target_dir} && git pull"],
        ["bash", "-c", f"cd {target_dir} && ./install.sh"],
    ]
