"""
Nmap binary installation and verification for K1 Network Wing.

Handles installation from package manager and environment verification.
"""

from __future__ import annotations

import subprocess
import shutil
from typing import Optional


def verify_nmap_installed() -> bool:
    """
    Verify that nmap binary is available in $PATH.

    Returns:
        True if nmap is installed and executable, False otherwise.
    """
    return shutil.which("nmap") is not None


def get_nmap_version() -> Optional[str]:
    """
    Get installed nmap version.

    Returns:
        Version string or None if nmap not found.
    """
    if not verify_nmap_installed():
        return None

    try:
        result = subprocess.run(
            ["nmap", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Extract first line which contains version info
            return result.stdout.split("\n")[0].strip()
    except Exception:
        pass

    return None


def install_nmap_from_apt() -> bool:
    """
    Install nmap from apt package manager (Debian/Ubuntu).

    Returns:
        True if installation succeeded, False otherwise.
    """
    try:
        # Update package list
        subprocess.run(
            ["sudo", "apt-get", "update"],
            check=True,
            timeout=60,
            capture_output=True,
        )

        # Install nmap and nmap-scripts
        subprocess.run(
            ["sudo", "apt-get", "install", "-y", "nmap"],
            check=True,
            timeout=300,
            capture_output=True,
        )

        return verify_nmap_installed()
    except Exception:
        return False


def ensure_nmap_ready() -> tuple[bool, str]:
    """
    Ensure nmap is installed and ready to use.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if verify_nmap_installed():
        version = get_nmap_version() or "unknown"
        return True, f"Nmap already installed: {version}"

    # Try apt installation
    if install_nmap_from_apt():
        version = get_nmap_version() or "unknown"
        return True, f"Nmap installed via apt: {version}"

    return False, "Failed to install nmap via apt"
