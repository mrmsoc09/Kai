"""
Testssl.sh binary installation and verification for K1 Network Wing.

Handles git cloning and environment verification.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Optional


def verify_testssl_installed() -> bool:
    """
    Verify that testssl.sh binary is available in $PATH or at /opt/testssl.sh.

    Returns:
        True if testssl.sh is installed and executable, False otherwise.
    """
    if shutil.which("testssl.sh"):
        return True

    testssl_path = Path("/opt/testssl.sh/testssl.sh")
    return testssl_path.exists() and testssl_path.is_file()


def get_testssl_version() -> Optional[str]:
    """
    Get installed testssl.sh version.

    Returns:
        Version string or None if testssl.sh not found.
    """
    if not verify_testssl_installed():
        return None

    # Try to get version from testssl.sh
    testssl_bin = shutil.which("testssl.sh") or "/opt/testssl.sh/testssl.sh"

    try:
        result = subprocess.run(
            [testssl_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def install_testssl_from_git(install_dir: str | Path = "/opt/testssl.sh") -> bool:
    """
    Install testssl.sh from GitHub.

    Args:
        install_dir: Directory to clone testssl.sh repository to.

    Returns:
        True if installation succeeded, False otherwise.
    """
    install_path = Path(install_dir)

    try:
        # Clone repository if not already present
        if not install_path.exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", "https://github.com/drwetter/testssl.sh", str(install_path)],
                check=True,
                timeout=120,
                capture_output=True,
            )

        # Make testssl.sh executable
        testssl_bin = install_path / "testssl.sh"
        if testssl_bin.exists():
            testssl_bin.chmod(0o755)

        # Create symlink in /usr/local/bin for convenience
        bin_path = Path("/usr/local/bin/testssl.sh")
        if testssl_bin.exists() and not bin_path.exists():
            try:
                subprocess.run(
                    ["sudo", "ln", "-s", str(testssl_bin), str(bin_path)],
                    check=True,
                    timeout=10,
                    capture_output=True,
                )
            except Exception:
                pass

        return verify_testssl_installed()
    except Exception:
        return False


def ensure_testssl_ready() -> tuple[bool, str]:
    """
    Ensure testssl.sh is installed and ready to use.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if verify_testssl_installed():
        version = get_testssl_version() or "unknown"
        return True, f"Testssl.sh already installed: {version}"

    # Try git installation
    if install_testssl_from_git():
        version = get_testssl_version() or "unknown"
        return True, f"Testssl.sh cloned from git: {version}"

    return False, "Failed to install testssl.sh from git"
