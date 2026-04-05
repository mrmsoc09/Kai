"""
KAISON AI Crew YAML Runner

Runs PraisonAI crew YAML files programmatically
using the documented PraisonAI CLI interface.

Reference: https://docs.praison.ai/docs/framework/crewai
Install: pip install "praisonai[crewai]" "praisonai[autogen]"
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CREW_REGISTRY_PATH = Path("crews/crew_registry.yaml")
CREWS_DIR = Path("crews")


def run_crew_yaml(
    yaml_path: str,
    framework: str = "crewai",
    timeout: int = 600,
) -> dict[str, Any]:
    """
    Run a PraisonAI crew YAML file via documented CLI.

    Uses: praisonai <yaml_path> --framework <framework>

    Args:
        yaml_path: Path to the crew YAML file
        framework: crewai, autogen, or praisonai
        timeout: Subprocess timeout in seconds

    Returns:
        dict with success, output, error, metadata
    """
    path = Path(yaml_path)
    if not path.exists():
        return {
            "success": False,
            "output": "",
            "error": f"Crew YAML not found: {yaml_path}",
            "yaml_path": yaml_path,
            "framework": framework,
        }

    cmd = [
        "praisonai",
        str(path),
        "--framework",
        framework,
    ]

    try:
        logger.info(
            "Running crew: %s (framework: %s)",
            yaml_path,
            framework,
        )
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        success = result.returncode == 0
        if not success:
            logger.warning(
                "Crew failed: %s — %s",
                yaml_path,
                result.stderr[:500],
            )
        return {
            "success": success,
            "output": result.stdout,
            "error": result.stderr,
            "yaml_path": yaml_path,
            "framework": framework,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.error(
            "Crew timed out after %ds: %s",
            timeout,
            yaml_path,
        )
        return {
            "success": False,
            "output": "",
            "error": f"Crew timed out after {timeout}s",
            "yaml_path": yaml_path,
            "framework": framework,
        }
    except FileNotFoundError:
        logger.error(
            "praisonai CLI not found. "
            "Install with: pip install praisonai[crewai]"
        )
        return {
            "success": False,
            "output": "",
            "error": (
                "praisonai CLI not found. "
                "Run: pip install 'praisonai[crewai]'"
            ),
            "yaml_path": yaml_path,
            "framework": framework,
        }
    except Exception as e:
        logger.error(
            "Crew execution error: %s",
            str(e),
        )
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "yaml_path": yaml_path,
            "framework": framework,
        }


def get_crew_for_phase(phase: str) -> str | None:
    """
    Get the primary crew YAML path for a hunt phase.

    Args:
        phase: Phase key from crew_registry.yaml
               e.g. 'phase_1_2_recon'

    Returns:
        Path to primary crew YAML or None
    """
    if not CREW_REGISTRY_PATH.exists():
        logger.warning(
            "Crew registry not found: %s",
            CREW_REGISTRY_PATH,
        )
        return None
    try:
        registry = yaml.safe_load(
            CREW_REGISTRY_PATH.read_text()
        )
        phase_crews = registry.get("phase_crews", {})
        crew = phase_crews.get(phase, {})
        return crew.get("primary")
    except Exception as e:
        logger.error(
            "Failed to read crew registry: %s",
            e,
        )
        return None


def list_all_crews() -> list[dict[str, Any]]:
    """
    List all crew YAML files with metadata.

    Returns:
        List of crew dicts with name, framework,
        path, is_primary, phase info
    """
    crews = []
    if not CREWS_DIR.exists():
        return crews

    for yaml_file in sorted(CREWS_DIR.rglob("*.yaml")):
        if yaml_file.name == "crew_registry.yaml":
            continue
        try:
            parsed = yaml.safe_load(yaml_file.read_text())
            roles = parsed.get("roles", {})
            crews.append(
                {
                    "name": yaml_file.stem.replace("_", " ").title(),
                    "framework": parsed.get("framework", "praisonai"),
                    "topic": parsed.get("topic", ""),
                    "file_path": str(yaml_file),
                    "role_count": len(roles),
                    "roles": [
                        {
                            "key": k,
                            "role": v.get("role", ""),
                            "goal": v.get("goal", ""),
                            "backstory": v.get("backstory", "")[
                                :200
                            ],
                            "task_count": len(
                                v.get("tasks", {})
                            ),
                        }
                        for k, v in roles.items()
                    ],
                }
            )
        except Exception as e:
            logger.warning(
                "Could not parse crew YAML %s: %s",
                yaml_file,
                e,
            )
    return crews


def run_validation_crews(
    finding: dict[str, Any],
) -> dict[str, Any]:
    """
    Run AutoGen2 validation conversation on a finding.

    Runs finding_review_conversation first,
    then severity_consensus if finding is approved.

    Args:
        finding: Finding dict from tool agent output

    Returns:
        Validation result with verdict and severity
    """
    if not CREW_REGISTRY_PATH.exists():
        return {
            "verdict": "SKIPPED",
            "reason": "Crew registry not found",
        }

    registry = yaml.safe_load(
        CREW_REGISTRY_PATH.read_text()
    )
    validation = registry.get("validation_crews", {}).get(
        "autogen", {}
    )

    review_path = validation.get("finding_review")
    severity_path = validation.get("severity_consensus")

    if not review_path:
        return {
            "verdict": "SKIPPED",
            "reason": "Finding review crew not configured",
        }

    # Run finding review conversation
    review_result = run_crew_yaml(
        review_path,
        framework="autogen",
        timeout=300,
    )

    verdict = "UNKNOWN"
    if review_result["success"]:
        output = review_result["output"].upper()
        if "APPROVED" in output:
            verdict = "APPROVED"
        elif "REJECTED" in output:
            verdict = "REJECTED"
        elif "NEEDS REVISION" in output:
            verdict = "NEEDS_REVISION"

    result = {
        "verdict": verdict,
        "review_output": review_result["output"],
        "review_success": review_result["success"],
    }

    # Run severity consensus if approved
    if verdict == "APPROVED" and severity_path:
        severity_result = run_crew_yaml(
            severity_path,
            framework="autogen",
            timeout=300,
        )
        result["severity_output"] = severity_result["output"]
        result["severity_success"] = severity_result["success"]

    return result
