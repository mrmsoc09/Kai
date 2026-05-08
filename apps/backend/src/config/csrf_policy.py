"""
Endpoint-level CSRF policy registry.
Allows tagging endpoints by risk level and required CSRF controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from typing import FrozenSet, Iterable


class CSRFRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EndpointCSRFPolicy:
    path_pattern: str
    methods: FrozenSet[str]
    risk_level: CSRFRiskLevel = CSRFRiskLevel.MEDIUM
    require_challenge: bool = True
    require_nonce: bool = False
    require_origin_check: bool = True

    def matches(self, path: str, method: str) -> bool:
        if method.upper() not in self.methods:
            return False
        return fnmatch(path, self.path_pattern)


class CSRFPolicyRegistry:
    def __init__(
        self,
        policies: Iterable[EndpointCSRFPolicy],
        default_policy: EndpointCSRFPolicy,
    ):
        self._policies = list(policies)
        self._default = default_policy

    def resolve(self, path: str, method: str) -> EndpointCSRFPolicy:
        matches = [policy for policy in self._policies if policy.matches(path, method)]
        if not matches:
            return self._default
        # Most specific path pattern wins.
        return max(matches, key=lambda policy: len(policy.path_pattern))


_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

DEFAULT_CSRF_POLICY = EndpointCSRFPolicy(
    path_pattern="*",
    methods=_MUTATION_METHODS,
    risk_level=CSRFRiskLevel.MEDIUM,
    require_challenge=True,
    require_nonce=False,
    require_origin_check=True,
)

DEFAULT_CSRF_ENDPOINT_POLICIES = [
    EndpointCSRFPolicy(
        path_pattern="/tools/*",
        methods=_MUTATION_METHODS,
        risk_level=CSRFRiskLevel.HIGH,
        require_challenge=True,
        require_nonce=True,
    ),
    EndpointCSRFPolicy(
        path_pattern="/terminal/execute",
        methods=frozenset({"POST"}),
        risk_level=CSRFRiskLevel.HIGH,
        require_challenge=True,
        require_nonce=True,
    ),
    EndpointCSRFPolicy(
        path_pattern="/approvals/*",
        methods=frozenset({"POST", "PATCH", "PUT"}),
        risk_level=CSRFRiskLevel.HIGH,
        require_challenge=True,
        require_nonce=True,
    ),
    EndpointCSRFPolicy(
        path_pattern="/api/orchestration/sessions/*/actions/*/approve",
        methods=frozenset({"POST"}),
        risk_level=CSRFRiskLevel.CRITICAL,
        require_challenge=True,
        require_nonce=True,
    ),
    EndpointCSRFPolicy(
        path_pattern="/api/orchestration/sessions/*/actions/*/reject",
        methods=frozenset({"POST"}),
        risk_level=CSRFRiskLevel.CRITICAL,
        require_challenge=True,
        require_nonce=True,
    ),
    EndpointCSRFPolicy(
        path_pattern="/api/orchestration/sessions/*/execute",
        methods=frozenset({"POST"}),
        risk_level=CSRFRiskLevel.CRITICAL,
        require_challenge=True,
        require_nonce=True,
    ),
]

csrf_policy_registry = CSRFPolicyRegistry(
    policies=DEFAULT_CSRF_ENDPOINT_POLICIES,
    default_policy=DEFAULT_CSRF_POLICY,
)

