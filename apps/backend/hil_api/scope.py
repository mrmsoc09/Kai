from typing import Optional, Sequence
from .models import Finding
from .models_extra import ProgramScope

_SEV_ORDER = {"INFO":0, "LOW":1, "MEDIUM":2, "HIGH":3, "CRITICAL":4}

def _matches(item: str, values: Optional[Sequence[str]]) -> bool:
    if not values:
        return False
    for v in values:
        if not v:
            continue
        if v.lower() in item.lower():
            return True
    return False

class ScopeViolation(Exception):
    pass

def enforce_scope(finding: Finding, policy: Optional[ProgramScope]):
    if policy is None:
        return  # no policy set → allow by default
    asset = (finding.asset or "").strip()
    # Exclusions first
    if _matches(asset, policy.excluded_assets) or _matches(asset, policy.excluded_domains):
        raise ScopeViolation("Asset/domain explicitly excluded by scope policy")
    # If any allowed_* present, must match one of them
    has_allow = bool((policy.allowed_assets and len(policy.allowed_assets)>0) or (policy.allowed_domains and len(policy.allowed_domains)>0))
    if has_allow and not (_matches(asset, policy.allowed_assets) or _matches(asset, policy.allowed_domains)):
        raise ScopeViolation("Asset/domain not in allowed scope")
    # Severity threshold
    min_sev = (policy.min_severity or "LOW").upper()
    fsev = (finding.severity or "LOW").upper()
    if _SEV_ORDER.get(fsev, 0) < _SEV_ORDER.get(min_sev, 1):
        raise ScopeViolation(f"Severity below policy threshold: {fsev} < {min_sev}")
