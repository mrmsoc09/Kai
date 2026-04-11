from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.hil_security import Permission, RBAC
from ..core.hil_vault_client import VaultClient


router = APIRouter(prefix="/providers", tags=["hil-providers"])


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[4] / "config" / "provider_registry.yaml"
REGISTRY_PATH = Path(os.getenv("PROVIDER_REGISTRY_PATH", str(DEFAULT_REGISTRY_PATH))).resolve()


class ProviderKey(BaseModel):
    api_key: Optional[str] = None
    token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    notes: Optional[str] = None
    rate_limit: Optional[str] = None
    tos_version: Optional[str] = None


class SelectionBody(BaseModel):
    market: str = Field(
        ...,
        description=(
            "Market key e.g., healthcare, finance, ecommerce, "
            "government_contracts_grants, supply_chain"
        ),
    )
    selected_ids: List[str] = Field(default_factory=list)


def _load_registry_sync() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise HTTPException(500, f"Provider registry not found at {REGISTRY_PATH}")

    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


async def _load_registry() -> Dict[str, Any]:
    return await asyncio.to_thread(_load_registry_sync)


@router.get("/catalog")
async def get_catalog(market: Optional[str] = Query(None, description="Filter providers by market")) -> Dict[str, Any]:
    registry = await _load_registry()
    providers = registry.get("providers", [])
    if market and market != "cross":
        providers = [p for p in providers if p.get("market") in (market, "cross")]
    return {"markets": registry.get("markets", []), "providers": providers}


@router.get("/selection")
async def get_selection(market: str) -> Dict[str, Any]:
    vault = await asyncio.to_thread(VaultClient)
    data = await asyncio.to_thread(vault.read_secret, path=f"osint_selections/{market}")
    return {"market": market, "selected_ids": (data or {}).get("selected_ids", [])}


@router.post("/selection", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
async def set_selection(body: SelectionBody) -> Dict[str, Any]:
    vault = await asyncio.to_thread(VaultClient)
    await asyncio.to_thread(
        vault.write_secret,
        path=f"osint_selections/{body.market}",
        data={"selected_ids": body.selected_ids},
    )
    return {"status": "ok", "market": body.market, "selected_ids": body.selected_ids}


@router.post("/{provider_id}/key", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
async def store_provider_key(provider_id: str, payload: ProviderKey) -> Dict[str, Any]:
    registry = await _load_registry()
    ids = {provider.get("id") for provider in registry.get("providers", [])}
    if provider_id not in ids:
        raise HTTPException(404, "Unknown provider id")

    data = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not data:
        raise HTTPException(422, "No key data provided")

    vault = await asyncio.to_thread(VaultClient)
    await asyncio.to_thread(vault.write_secret, path=f"osint/{provider_id}", data=data)
    return {"status": "stored", "provider_id": provider_id, "fields": sorted(data.keys())}
