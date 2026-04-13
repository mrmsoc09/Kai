"""
Wafw00f binary installation and verification for K1 Network Wing.

Handles pip installation and environment verification.
"""

from __future__ import annotations

import subprocess
import shutil
from typing import Optional


def verify_wafw00f_installed() -> bool:
    """
    Verify that wafw00f is available in $PATH.

    Returns:
        True if wafw00f is installed and executable, False otherwise.
    """
    return shutil.which("wafw00f") is not None


def get_wafw00f_version() -> Optional[str]:
    """
    Get installed wafw00f version.

    Returns:
        Version string or None if wafw00f not found.
    """
    if not verify_wafw00f_installed():
        return None

    try:
        result = subprocess.run(
            ["wafw00f", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def install_wafw00f_from_pip() -> bool:
    """
    Install wafw00f from PyPI via pip.

    Returns:
        True if installation succeeded, False otherwise.
    """
    try:
        subprocess.run(
            ["pip", "install", "wafw00f"],
            check=True,
            timeout=300,
            capture_output=True,
        )
        return verify_wafw00f_installed()
    except Exception:
        return False


def install_wafw00f_from_git() -> bool:
    """
    Install wafw00f from GitHub source.

    Returns:
        True if installation succeeded, False otherwise.
    """
    try:
        subprocess.run(
            ["pip", "install", "git+https://github.com/EnableSecurity/wafw00f.git"],
            check=True,
            timeout=300,
            capture_output=True,
        )
        return verify_wafw00f_installed()
    except Exception:
        return False


def ensure_wafw00f_ready() -> tuple[bool, str]:
    """
    Ensure wafw00f is installed and ready to use.

    Attempts installation if not already present:
    1. Try pip install from PyPI (standard)
    2. Fall back to git install if pip fails

    Returns:
        Tuple of (success: bool, message: str)
    """
    if verify_wafw00f_installed():
        version = get_wafw00f_version() or "unknown"
        return True, f"Wafw00f already installed: {version}"

    # Try pip installation first
    if install_wafw00f_from_pip():
        version = get_wafw00f_version() or "unknown"
        return True, f"Wafw00f installed via pip: {version}"

    # Fall back to git installation
    if install_wafw00f_from_git():
        version = get_wafw00f_version() or "unknown"
        return True, f"Wafw00f installed from git: {version}"

    return False, "Failed to install wafw00f via pip or git"
