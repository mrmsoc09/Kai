from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import yaml
from ..security import RBAC, Permission
from ..vault_client import VaultClient

router = APIRouter(prefix="/providers", tags=["providers"])

REGISTRY_PATH = os.getenv(
    "PROVIDER_REGISTRY_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", "configs", "provider_registry.yaml"))
)

class ProviderKey(BaseModel):
    # Generalized fields; only send what applies to provider's auth_type
    api_key: Optional[str] = None
    token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    notes: Optional[str] = None
    rate_limit: Optional[str] = None
    tos_version: Optional[str] = None

class SelectionBody(BaseModel):
    market: str = Field(..., description="Market key e.g., healthcare, finance, ecommerce, government_contracts_grants, supply_chain")
    selected_ids: List[str] = Field(default_factory=list)


def _load_registry() -> Dict[str, Any]:
    if not os.path.exists(REGISTRY_PATH):
        raise HTTPException(500, f"Provider registry not found at {REGISTRY_PATH}")
    with open(REGISTRY_PATH, 'r') as f:
        data = yaml.safe_load(f) or {}
    return data

@router.get("/catalog")
def get_catalog(market: Optional[str] = Query(None, description="Filter providers by market")) -> Dict[str, Any]:
    reg = _load_registry()
    providers = reg.get("providers", [])
    if market and market != "cross":
        providers = [p for p in providers if p.get("market") in (market, "cross")]
    return {"markets": reg.get("markets", []), "providers": providers}

@router.get("/selection")
def get_selection(market: str) -> Dict[str, Any]:
    vc = VaultClient()
    data = vc.read_secret(path=f"osint_selections/{market}") or {}
    return {"market": market, "selected_ids": data.get("selected_ids", [])}

@router.post("/selection", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
def set_selection(body: SelectionBody) -> Dict[str, Any]:
    vc = VaultClient()
    vc.write_secret(path=f"osint_selections/{body.market}", data={"selected_ids": body.selected_ids})
    return {"status": "ok", "market": body.market, "selected_ids": body.selected_ids}

@router.post("/{provider_id}/key", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
def store_provider_key(provider_id: str, payload: ProviderKey) -> Dict[str, Any]:
    # Minimal validation that provider exists in registry
    reg = _load_registry()
    ids = {p.get("id") for p in reg.get("providers", [])}
    if provider_id not in ids:
        raise HTTPException(404, "Unknown provider id")
    # Write to Vault KV v2 under secret/data/osint/{provider_id}
    vc = VaultClient()
    # Do not log secrets; only return metadata
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(422, "No key data provided")
    vc.write_secret(path=f"osint/{provider_id}", data=data)
    return {"status": "stored", "provider_id": provider_id, "fields": sorted(list(data.keys()))}
