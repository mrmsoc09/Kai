"""Installation planning utilities for K1 Content Mining & Fuzzing Wing.

This module intentionally returns deterministic command plans and environment checks.
It does not execute network installs by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Iterable


GO_TOOLS = {
    "ffuf": "github.com/ffuf/ffuf/v2@latest",
    "hakrawler": "github.com/hakluke/hakrawler@latest",
    "gau": "github.com/lc/gau/v2/cmd/gau@latest",
    "dalfox": "github.com/hahwul/dalfox/v2@latest",
}

PYTHON_TOOLS = {
    "arjun": "arjun",
    "smuggler": "smuggler",
}


@dataclass(frozen=True)
class InstallPlan:
    go_install_commands: list[list[str]]
    python_install_commands: list[list[str]]
    wordlist_commands: list[list[str]]


@dataclass(frozen=True)
class InstallStatus:
    tool: str
    installed: bool
    resolved_path: str | None


def build_go_install_commands(go_bin_dir: str = "") -> list[list[str]]:
    commands: list[list[str]] = []
    for _, module in GO_TOOLS.items():
        if go_bin_dir:
            commands.append(["env", f"GOBIN={go_bin_dir}", "go", "install", module])
        else:
            commands.append(["go", "install", module])
    return commands


def build_python_install_commands(venv_python: str = ".venv/bin/python") -> list[list[str]]:
    commands: list[list[str]] = [[venv_python, "-m", "pip", "install", "--upgrade", "pip"]]
    for package in PYTHON_TOOLS.values():
        commands.append([venv_python, "-m", "pip", "install", package])
    return commands


def build_wordlist_commands(
    nvme_root: str = "/mnt/nvme/k1-wordlists",
    seclists_git: str = "https://github.com/danielmiessler/SecLists.git",
) -> list[list[str]]:
    target_root = Path(nvme_root)
    curated = target_root / "top-1k-discovery.txt"
    seclists_dir = target_root / "SecLists"
    return [
        ["mkdir", "-p", str(target_root)],
        ["git", "clone", "--depth", "1", seclists_git, str(seclists_dir)],
        [
            "ln",
            "-sf",
            str(seclists_dir / "Discovery" / "Web-Content" / "common.txt"),
            str(curated),
        ],
    ]


def build_install_plan(
    venv_python: str = ".venv/bin/python",
    go_bin_dir: str = "",
    nvme_root: str = "/mnt/nvme/k1-wordlists",
) -> InstallPlan:
    return InstallPlan(
        go_install_commands=build_go_install_commands(go_bin_dir=go_bin_dir),
        python_install_commands=build_python_install_commands(venv_python=venv_python),
        wordlist_commands=build_wordlist_commands(nvme_root=nvme_root),
    )


def check_installed_tools(tools: Iterable[str] | None = None) -> list[InstallStatus]:
    selected = list(tools) if tools is not None else [*GO_TOOLS.keys(), *PYTHON_TOOLS.keys()]
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
