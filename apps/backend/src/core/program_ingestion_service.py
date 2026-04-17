from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Asset types that represent scannable network targets
_SCANNABLE_ASSET_TYPES = {"url", "domain", "wildcard", "cidr", "api", "web"}


@dataclass
class IngestedProgram:
    program_handle: str
    platform: str
    in_scope_assets: list[str] = field(default_factory=list)
    out_of_scope_assets: list[str] = field(default_factory=list)
    asset_types: dict[str, str] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ProgramIngestionService:
    """Ingests bug bounty programs from platform payloads and derives scan targets."""

    def ingest_from_hackerone_payload(self, payload: dict[str, Any]) -> IngestedProgram:
        """Parse H1 program API response with structured_scopes.

        Expected payload shapes:
        - Direct scope: {handle, in_scope: [{asset_identifier, asset_type}], out_of_scope: [...]}
        - H1 GraphQL: {handle, structured_scopes: {edges: [{node: {asset_identifier, asset_type}}]}}
        """
        handle = str(payload.get("handle", payload.get("name", "unknown"))).strip()
        platform = str(payload.get("platform", "hackerone")).strip()

        in_scope: list[str] = []
        out_of_scope: list[str] = []
        asset_types: dict[str, str] = {}

        # Parse in_scope entries
        in_entries = payload.get("in_scope", [])
        if not in_entries:
            # Try H1 GraphQL structured_scopes format
            scopes = payload.get("structured_scopes", {})
            edges = scopes.get("edges", []) if isinstance(scopes, dict) else []
            in_entries = [edge.get("node", edge) for edge in edges]

        for entry in in_entries:
            identifier = str(entry.get("asset_identifier", "")).strip()
            atype = str(entry.get("asset_type", "")).strip().lower()
            if identifier:
                in_scope.append(identifier)
                asset_types[identifier] = atype

        # Parse out_of_scope entries
        for entry in payload.get("out_of_scope", []):
            identifier = str(entry.get("asset_identifier", "")).strip()
            atype = str(entry.get("asset_type", "")).strip().lower()
            if identifier:
                out_of_scope.append(identifier)
                asset_types[identifier] = atype

        return IngestedProgram(
            program_handle=handle,
            platform=platform,
            in_scope_assets=in_scope,
            out_of_scope_assets=out_of_scope,
            asset_types=asset_types,
            ingested_at=datetime.now(timezone.utc),
        )

    def ingest_from_structured(self, data: dict[str, Any]) -> IngestedProgram:
        """Parse structured dict with explicit handle/platform/scope fields."""
        return self.ingest_from_hackerone_payload(data)

    def derive_scan_targets(self, program: IngestedProgram) -> list[str]:
        """Return normalized list of scannable targets from in-scope assets.

        Filters out non-URL/domain types (hardware, other, etc).
        Normalizes wildcards (*.example.com -> example.com kept as wildcard pattern).
        """
        targets: list[str] = []
        out_set = set(a.lower().strip() for a in program.out_of_scope_assets)

        for asset in program.in_scope_assets:
            atype = program.asset_types.get(asset, "domain").lower()

            # Skip non-scannable asset types
            if atype in {"hardware", "other", "physical", "social_engineering"}:
                continue

            normalized = asset.strip().lower()

            # Extract hostname from URLs
            if "://" in normalized:
                parsed = urlparse(normalized)
                normalized = parsed.hostname or normalized

            # Skip if in out-of-scope
            if normalized in out_set:
                continue

            if normalized and normalized not in targets:
                targets.append(normalized)

        return targets

    def schedule_program(
        self, program: IngestedProgram, interval_hours: int = 24
    ) -> dict[str, Any]:
        """Return a schedule descriptor for periodic scanning."""
        now = datetime.now(timezone.utc)
        targets = self.derive_scan_targets(program)
        return {
            "program_handle": program.program_handle,
            "next_run_at": (now + timedelta(hours=interval_hours)).isoformat(),
            "interval_hours": interval_hours,
            "targets_count": len(targets),
        }
