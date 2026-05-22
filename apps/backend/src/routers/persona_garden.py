from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import require_roles, ROLE_ANALYST

router = APIRouter(
    prefix="/personas",
    tags=["personas"],
    dependencies=[Depends(require_roles(ROLE_ANALYST))],
)

REGISTRY_PATH = Path(
    "personas/persona_registry.json"
)
PERSONAS_DIR = Path("personas/hacker_inputs")


def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"total": 0, "personas": []}
    try:
        return json.loads(
            REGISTRY_PATH.read_text()
        )
    except Exception:
        return {"total": 0, "personas": []}


def _parse_persona_file(
    file_path: Path,
) -> dict | None:
    try:
        content = file_path.read_text(
            encoding="utf-8"
        )
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        meta = yaml.safe_load(parts[1]) or {}
        meta["body"] = parts[2].strip()
        meta["file_path"] = str(file_path)
        return meta
    except Exception:
        return None


@router.get("/")
def list_personas(
    tier: str | None = None,
    phase: int | None = None,
    trained: bool | None = None,
    vertical: str | None = None,
    hunting_style: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    List personas with filtering.
    tier: community or pro
    phase: 1-9
    trained: true/false
    vertical: web, api, fintech, etc.
    hunting_style: methodical, aggressive, etc.
    """
    registry = _load_registry()
    personas = registry.get("personas", [])

    if tier:
        personas = [
            p for p in personas
            if p.get("tier") == tier
        ]
    if phase is not None:
        personas = [
            p for p in personas
            if phase in p.get(
                "phase_affinity", []
            )
        ]
    if trained is not None:
        personas = [
            p for p in personas
            if p.get("trained") == trained
        ]
    if vertical:
        personas = [
            p for p in personas
            if vertical in p.get(
                "target_verticals", []
            )
        ]
    if hunting_style:
        personas = [
            p for p in personas
            if p.get("hunting_style")
            == hunting_style
        ]

    total = len(personas)
    paginated = personas[offset: offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "personas": [
            {
                "persona_id": p.get(
                    "persona_id"
                ),
                "display_name": p.get(
                    "display_name"
                ),
                "specialization": p.get(
                    "specialization"
                ),
                "phase_affinity": p.get(
                    "phase_affinity", []
                ),
                "tier": p.get("tier"),
                "hunting_style": p.get(
                    "hunting_style"
                ),
                "target_verticals": p.get(
                    "target_verticals", []
                ),
                "trained": p.get(
                    "trained", False
                ),
            }
            for p in paginated
        ],
    }


@router.get("/stats")
def get_persona_stats() -> dict:
    """Summary stats for the persona garden."""
    registry = _load_registry()
    personas = registry.get("personas", [])
    phases: dict[int, int] = {}
    verticals: dict[str, int] = {}
    styles: dict[str, int] = {}
    for p in personas:
        for ph in p.get("phase_affinity", []):
            phases[ph] = phases.get(ph, 0) + 1
        for v in p.get("target_verticals", []):
            verticals[v] = (
                verticals.get(v, 0) + 1
            )
        style = p.get("hunting_style", "")
        if style:
            styles[style] = (
                styles.get(style, 0) + 1
            )
    return {
        "total": registry.get("total", 0),
        "community": registry.get("community", 0),
        "pro": registry.get("pro", 0),
        "trained": registry.get("trained", 0),
        "phase_coverage": phases,
        "vertical_coverage": verticals,
        "hunting_styles": styles,
    }


@router.get("/phase/{phase_number}")
def get_personas_for_phase(
    phase_number: int,
    tier: str = "community",
) -> dict:
    """
    Get personas for a specific hunt phase.
    Used by crew agents to select personas
    before tool dispatch.
    """
    if phase_number < 1 or phase_number > 9:
        raise HTTPException(
            status_code=400,
            detail="Phase must be 1-9",
        )
    return list_personas(
        tier=tier,
        phase=phase_number,
    )


@router.get("/{persona_id}")
def get_persona(persona_id: str) -> dict:
    """Get full persona including backstory."""
    registry = _load_registry()
    personas = registry.get("personas", [])
    match = next(
        (
            p for p in personas
            if p.get("persona_id") == persona_id
        ),
        None,
    )
    if not match:
        raise HTTPException(
            status_code=404,
            detail=f"Persona not found: "
                   f"{persona_id}",
        )
    file_path = Path(
        match.get("file_path", "")
    )
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Persona file not found",
        )
    full = _parse_persona_file(file_path)
    if not full:
        raise HTTPException(
            status_code=500,
            detail="Could not parse persona",
        )
    return full
