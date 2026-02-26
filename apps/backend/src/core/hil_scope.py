from __future__ import annotations

from typing import Optional, Sequence

from ..models.hil import Finding
from ..models.hil_extra import ProgramScope


_SEV_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _matches(item: str, values: Optional[Sequence[str]]) -> bool:
    if not values:
        return False
    for value in values:
        if not value:
            continue
        if value.lower() in item.lower():
            return True
    return False


class ScopeViolation(Exception):
    pass


def enforce_scope(finding: Finding, policy: Optional[ProgramScope]):
    if policy is None:
        return

    asset = (finding.asset or "").strip()

    if _matches(asset, policy.excluded_assets) or _matches(asset, policy.excluded_domains):
        raise ScopeViolation("Asset/domain explicitly excluded by scope policy")

    has_allow = bool(
        (policy.allowed_assets and len(policy.allowed_assets) > 0)
        or (policy.allowed_domains and len(policy.allowed_domains) > 0)
    )
    if has_allow and not (
        _matches(asset, policy.allowed_assets) or _matches(asset, policy.allowed_domains)
    ):
        raise ScopeViolation("Asset/domain not in allowed scope")

    min_sev_raw = policy.min_severity.value if policy.min_severity is not None else "LOW"
    finding_sev_raw = finding.severity.value if finding.severity is not None else "LOW"
    min_sev = min_sev_raw.upper()
    finding_sev = finding_sev_raw.upper()
    if _SEV_ORDER.get(finding_sev, 0) < _SEV_ORDER.get(min_sev, 1):
        raise ScopeViolation(f"Severity below policy threshold: {finding_sev} < {min_sev}")
