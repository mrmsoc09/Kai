"""Installation planning for K1 Deep Intelligence & Darknet Wing.

This module is intentionally non-executing. It returns deterministic install and
verification command plans for bootstrap workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
import shutil
from typing import Iterable


DEEP_INTEL_BINARIES = ("tor", "torbot", "onionsearch", "ahmia", "trufflehog", "gitleaks", "spiderfoot")


@dataclass(frozen=True)
class InstallPlan:
    tor_setup_commands: list[list[str]]
    scanner_install_commands: list[list[str]]
    spiderfoot_install_commands: list[list[str]]
    verification_commands: list[list[str]]


@dataclass(frozen=True)
class InstallStatus:
    tool: str
    installed: bool
    resolved_path: str | None


def build_tor_setup_commands() -> list[list[str]]:
    return [
        ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "-y", "tor"],
        ["sudo", "systemctl", "enable", "--now", "tor"],
    ]


def build_scanner_install_commands() -> list[list[str]]:
    return [
        ["go", "install", "github.com/trufflesecurity/trufflehog/v3@latest"],
        ["go", "install", "github.com/gitleaks/gitleaks/v8@latest"],
    ]


def build_spiderfoot_install_commands(venv_python: str = ".venv/bin/python") -> list[list[str]]:
    return [
        [venv_python, "-m", "pip", "install", "--upgrade", "pip"],
        [venv_python, "-m", "pip", "install", "spiderfoot"],
    ]


def build_verification_commands() -> list[list[str]]:
    return [
        ["systemctl", "is-active", "tor"],
        ["ss", "-ltn"],
        ["curl", "-sS", "--socks5-hostname", "127.0.0.1:9050", "https://check.torproject.org/api/ip"],
        ["trufflehog", "version"],
        ["gitleaks", "version"],
        ["spiderfoot", "--help"],
    ]


def build_install_plan(venv_python: str = ".venv/bin/python") -> InstallPlan:
    return InstallPlan(
        tor_setup_commands=build_tor_setup_commands(),
        scanner_install_commands=build_scanner_install_commands(),
        spiderfoot_install_commands=build_spiderfoot_install_commands(venv_python=venv_python),
        verification_commands=build_verification_commands(),
    )


def check_installed_tools(tools: Iterable[str] | None = None) -> list[InstallStatus]:
    selected = list(tools) if tools is not None else list(DEEP_INTEL_BINARIES)
    statuses: list[InstallStatus] = []
    for tool in selected:
        resolved = shutil.which(tool)
        statuses.append(
            InstallStatus(
                tool=tool,
                installed=resolved is not None,
                resolved_path=resolved,
            )
        )
    return statuses
