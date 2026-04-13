"""
Masscan binary installation and verification for K1 Network Wing.

Handles installation from source and environment verification.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Optional


def verify_masscan_installed() -> bool:
    """
    Verify that masscan binary is available in $PATH.

    Returns:
        True if masscan is installed and executable, False otherwise.
    """
    return shutil.which("masscan") is not None


def get_masscan_version() -> Optional[str]:
    """
    Get installed masscan version.

    Returns:
        Version string or None if masscan not found.
    """
    if not verify_masscan_installed():
        return None

    try:
        result = subprocess.run(
            ["masscan", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def install_masscan_from_apt() -> bool:
    """
    Install masscan from apt package manager (Debian/Ubuntu).

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

        # Install masscan
        subprocess.run(
            ["sudo", "apt-get", "install", "-y", "masscan"],
            check=True,
            timeout=300,
            capture_output=True,
        )

        return verify_masscan_installed()
    except Exception:
        return False


def install_masscan_from_source(install_dir: str | Path = "/opt/masscan") -> bool:
    """
    Install masscan from source (GitHub).

    Args:
        install_dir: Directory to clone masscan repository to.

    Returns:
        True if installation succeeded, False otherwise.
    """
    install_path = Path(install_dir)

    try:
        # Clone repository if not already present
        if not install_path.exists():
            subprocess.run(
                ["git", "clone", "https://github.com/robertdavidgraham/masscan", str(install_path)],
                check=True,
                timeout=120,
                capture_output=True,
            )

        # Build masscan
        subprocess.run(
            ["make", "-j4"],
            cwd=str(install_path),
            check=True,
            timeout=300,
            capture_output=True,
        )

        # Create symlink in /usr/local/bin if not already done
        bin_path = Path("/usr/local/bin/masscan")
        masscan_bin = install_path / "bin" / "masscan"

        if masscan_bin.exists() and not bin_path.exists():
            try:
                subprocess.run(
                    ["sudo", "ln", "-s", str(masscan_bin), str(bin_path)],
                    check=True,
                    timeout=10,
                    capture_output=True,
                )
            except Exception:
                pass

        return verify_masscan_installed()
    except Exception:
        return False


def ensure_masscan_ready() -> tuple[bool, str]:
    """
    Ensure masscan is installed and ready to use.

    Attempts installation if not already present:
    1. Try apt-get install (fastest)
    2. Fall back to source build if apt fails

    Returns:
        Tuple of (success: bool, message: str)
    """
    if verify_masscan_installed():
        version = get_masscan_version() or "unknown"
        return True, f"Masscan already installed: {version}"

    # Try apt installation first (faster)
    if install_masscan_from_apt():
        version = get_masscan_version() or "unknown"
        return True, f"Masscan installed via apt: {version}"

    # Fall back to source build
    if install_masscan_from_source():
        version = get_masscan_version() or "unknown"
        return True, f"Masscan built from source: {version}"

    return False, "Failed to install masscan via apt or source build"
