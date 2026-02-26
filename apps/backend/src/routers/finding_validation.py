"""
Router for K1 Finding Validation Workflow
Routes findings to HiL validation or exploit chaining based on severity/duplicates
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
import json

router = APIRouter(prefix="/api/findings", tags=["findings"])


def get_systems():
    """Get references to all finding-related systems"""
    try:
        from apps.backend.src.core.duplicate_detection import duplicate_detection_system
        from apps.backend.src.core.exploit_chaining import chaining_engine
        from apps.backend.src.core.finding_router import finding_router
        from apps.backend.src.core.episodic_memory import episodic_memory

        return duplicate_detection_system, chaining_engine, finding_router, episodic_memory
    except Exception:
        return None, None, None, None


# ==================== FINDING SUBMISSION ====================

@router.post("/submit")
async def submit_finding(
    target_domain: str,
    vulnerability_type: str,
    endpoint: str,
    description: str,
    cvss_score: float,
    severity: str,
    affected_parameters: Optional[List[str]] = None,
    techniques: Optional[List[str]] = None,
    payload_hash: Optional[str] = None,
    confidence_score: float = 0.7,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Submit a finding for processing"""

    dup_sys, chain_sys, router_sys, mem_sys = get_systems()

    if not (dup_sys and router_sys):
        raise HTTPException(status_code=503, detail="Finding systems not initialized")

    try:
        # Step 1: Check for duplicates
        dup_result = await dup_sys.check_duplicate(
            target_domain=target_domain,
            vulnerability_type=vulnerability_type,
            endpoint=endpoint,
            techniques=techniques or [],
            affected_parameters=affected_parameters or [],
            description=description,
            payload_hash=payload_hash
        )

        # Step 2: Route finding
        routed = await router_sys.route_finding(
            target_domain=target_domain,
            vulnerability_type=vulnerability_type,
            endpoint=endpoint,
            cvss_score=cvss_score,
            severity=severity,
            confidence_score=confidence_score,
            is_duplicate=dup_result.is_duplicate,
            duplicate_reason=dup_result.reason,
            chainable_with=[f.finding_id for f in dup_result.chainable_with] if dup_result.chainable_with else None
        )

        return {
            "finding_id": routed.finding_id,
            "route": routed.route.value,
            "routing_reasoning": routed.reasoning,
            "duplicate_check": {
                "is_duplicate": dup_result.is_duplicate,
                "similarity_score": dup_result.similarity_score,
                "confidence": dup_result.confidence,
                "matched_finding": dup_result.matched_finding.finding_id if dup_result.matched_finding else None
            },
            "next_steps": _get_next_steps(routed.route)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DUPLICATE DETECTION ====================

@router.post("/check-duplicate")
async def check_duplicate(
    target_domain: str,
    vulnerability_type: str,
    endpoint: str,
    description: str,
    techniques: Optional[List[str]] = None,
    affected_parameters: Optional[List[str]] = None,
    payload_hash: Optional[str] = None
) -> Dict[str, Any]:
    """Check if finding is duplicate"""

    dup_sys, _, _, _ = get_systems()

    if not dup_sys:
        raise HTTPException(status_code=503, detail="Duplicate detection system not initialized")

    try:
        result = await dup_sys.check_duplicate(
            target_domain=target_domain,
            vulnerability_type=vulnerability_type,
            endpoint=endpoint,
            techniques=techniques or [],
            affected_parameters=affected_parameters or [],
            description=description,
            payload_hash=payload_hash
        )

        return {
            "is_duplicate": result.is_duplicate,
            "similarity_score": result.similarity_score,
            "confidence": result.confidence,
            "matched_finding": {
                "finding_id": result.matched_finding.finding_id,
                "program": result.matched_finding.program_name,
                "status": result.matched_finding.status,
                "cvss_score": result.matched_finding.cvss_score,
                "bounty_paid": result.matched_finding.bounty_paid
            } if result.matched_finding else None,
            "chainable_with": len(result.chainable_with),
            "reason": result.reason
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FINDING ROUTING ====================

@router.post("/route")
async def route_finding(
    target_domain: str,
    vulnerability_type: str,
    endpoint: str,
    cvss_score: float,
    severity: str,
    confidence_score: float = 0.7,
    is_duplicate: bool = False,
    duplicate_reason: Optional[str] = None
) -> Dict[str, Any]:
    """Route finding to appropriate module"""

    _, _, router_sys, _ = get_systems()

    if not router_sys:
        raise HTTPException(status_code=503, detail="Finding router not initialized")

    try:
        routed = await router_sys.route_finding(
            target_domain=target_domain,
            vulnerability_type=vulnerability_type,
            endpoint=endpoint,
            cvss_score=cvss_score,
            severity=severity,
            confidence_score=confidence_score,
            is_duplicate=is_duplicate,
            duplicate_reason=duplicate_reason
        )

        return {
            "finding_id": routed.finding_id,
            "route": routed.route.value,
            "reasoning": routed.reasoning,
            "next_steps": _get_next_steps(routed.route)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/routing-stats")
async def get_routing_statistics() -> Dict[str, Any]:
    """Get finding routing statistics"""

    _, _, router_sys, _ = get_systems()

    if not router_sys:
        raise HTTPException(status_code=503, detail="Finding router not initialized")

    return router_sys.get_routing_stats()


@router.get("/pending-hil-validation")
async def get_findings_pending_hil() -> Dict[str, Any]:
    """Get findings awaiting HiL validation"""

    _, _, router_sys, _ = get_systems()

    if not router_sys:
        raise HTTPException(status_code=503, detail="Finding router not initialized")

    findings = router_sys.get_findings_for_hil_validation()

    return {
        "count": len(findings),
        "findings": [
            {
                "finding_id": f.finding_id,
                "domain": f.target_domain,
                "vulnerability_type": f.vulnerability_type,
                "cvss": f.cvss_score,
                "severity": f.severity,
                "confidence": f.confidence_score,
                "endpoint": f.metadata.get("endpoint")
            }
            for f in findings
        ]
    }


@router.get("/pending-chaining")
async def get_findings_pending_chaining() -> Dict[str, Any]:
    """Get findings awaiting exploit chaining"""

    _, _, router_sys, _ = get_systems()

    if not router_sys:
        raise HTTPException(status_code=503, detail="Finding router not initialized")

    findings = router_sys.get_findings_for_chaining()

    return {
        "count": len(findings),
        "findings": [
            {
                "finding_id": f.finding_id,
                "domain": f.target_domain,
                "vulnerability_type": f.vulnerability_type,
                "cvss": f.cvss_score,
                "severity": f.severity,
                "endpoint": f.metadata.get("endpoint"),
                "chainable_with": f.metadata.get("chainable_with", [])
            }
            for f in findings
        ]
    }


# ==================== EXPLOIT CHAINING ====================

@router.post("/chain/identify")
async def identify_chainable_findings(
    target_domain: str,
    findings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Identify chainable findings"""

    _, chain_sys, _, _ = get_systems()

    if not chain_sys:
        raise HTTPException(status_code=503, detail="Exploit chaining system not initialized")

    try:
        from apps.backend.src.core.exploit_chaining import Finding

        # Convert to Finding objects
        finding_objs = [
            Finding(
                finding_id=f.get("finding_id", f"f_{i}"),
                target_domain=target_domain,
                vulnerability_type=f.get("vulnerability_type"),
                endpoint=f.get("endpoint"),
                cvss_score=f.get("cvss_score", 5.0),
                severity=f.get("severity", "medium"),
                description=f.get("description"),
                affected_parameters=f.get("affected_parameters", []),
                payload=f.get("payload")
            )
            for i, f in enumerate(findings)
        ]

        chains = await chain_sys.identify_chainable_findings(target_domain, finding_objs)

        return {
            "target_domain": target_domain,
            "total_findings": len(finding_objs),
            "potential_chains": len(chains),
            "chains": [
                {
                    "chain_type": chain_type.value,
                    "component_count": len(chain_findings),
                    "components": [f.vulnerability_type for f in chain_findings]
                }
                for chain_type, chain_findings in chains
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chain/create")
async def create_exploit_chain(
    target_domain: str,
    chain_type: str,
    finding_ids: List[str],
    findings_data: List[Dict[str, Any]],
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Create exploit chain from findings"""

    _, chain_sys, _, _ = get_systems()

    if not chain_sys:
        raise HTTPException(status_code=503, detail="Exploit chaining system not initialized")

    try:
        from apps.backend.src.core.exploit_chaining import Finding, ChainType

        # Convert to Finding objects
        finding_objs = [
            Finding(
                finding_id=f.get("finding_id", f"f_{i}"),
                target_domain=target_domain,
                vulnerability_type=f.get("vulnerability_type"),
                endpoint=f.get("endpoint"),
                cvss_score=f.get("cvss_score", 5.0),
                severity=f.get("severity", "medium"),
                description=f.get("description")
            )
            for i, f in enumerate(findings_data)
        ]

        chain_type_enum = ChainType[chain_type.upper()]

        chain = await chain_sys.create_chain(
            domain=target_domain,
            chain_type=chain_type_enum,
            findings=finding_objs,
            chain_description=description or ""
        )

        # Generate exploit steps
        steps = await chain_sys.generate_exploit_steps(chain)
        chain.attack_steps = steps

        # Estimate success probability
        success_prob = await chain_sys.estimate_success_probability(chain)
        chain.success_probability = success_prob

        # Validate chain
        validation = await chain_sys.validate_chain(chain)

        return {
            "chain_id": chain.chain_id,
            "chain_type": chain.chain_type.value,
            "component_findings": len(chain.findings),
            "original_severities": chain.get_original_severities(),
            "combined_cvss": chain.combined_cvss,
            "combined_severity": chain.combined_severity,
            "attack_description": chain.attack_description,
            "attack_steps": chain.attack_steps,
            "success_probability": success_prob,
            "validation": {
                "is_valid": validation["is_valid"],
                "issues": validation.get("issues", []),
                "warnings": validation.get("warnings", [])
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EPISODIC MEMORY ====================

@router.post("/memory/record-attempt")
async def record_attack_attempt(
    agent_id: str,
    target_domain: str,
    endpoint: str,
    vulnerability_type: str,
    technique: str,
    payload_hash: str,
    outcome: str,
    response_code: Optional[int] = None,
    error_message: Optional[str] = None,
    api_credits_used: float = 0.0
) -> Dict[str, Any]:
    """Record attack attempt in episodic memory"""

    _, _, _, mem_sys = get_systems()

    if not mem_sys:
        raise HTTPException(status_code=503, detail="Episodic memory not initialized")

    try:
        from apps.backend.src.core.episodic_memory import AttemptOutcome

        outcome_enum = AttemptOutcome[outcome.upper()]

        attempt = mem_sys.record_attempt(
            agent_id=agent_id,
            target_domain=target_domain,
            endpoint=endpoint,
            vulnerability_type=vulnerability_type,
            technique=technique,
            payload_hash=payload_hash,
            outcome=outcome_enum,
            response_code=response_code,
            error_message=error_message,
            api_credits_used=api_credits_used
        )

        # Check if should retry
        should_retry, reason = mem_sys.should_retry_technique(agent_id, target_domain, endpoint, technique)

        # Recommend next technique
        all_techniques = ["basic", "advanced", "obfuscated", "bypass", "variant"]
        next_technique, rec_reason = mem_sys.recommend_next_technique(
            agent_id=agent_id,
            target_domain=target_domain,
            endpoint=endpoint,
            available_techniques=all_techniques,
            vulnerability_type=vulnerability_type
        )

        return {
            "attempt_id": attempt.attempt_id,
            "recorded": True,
            "should_retry_technique": should_retry,
            "retry_reason": reason,
            "recommended_next_technique": next_technique,
            "recommendation_reason": rec_reason
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/target-history/{agent_id}/{target_domain}")
async def get_target_history(agent_id: str, target_domain: str) -> Dict[str, Any]:
    """Get attack history for target"""

    _, _, _, mem_sys = get_systems()

    if not mem_sys:
        raise HTTPException(status_code=503, detail="Episodic memory not initialized")

    return mem_sys.get_target_history(agent_id, target_domain)


@router.get("/memory/wasted-credits/{agent_id}")
async def get_wasted_credits(agent_id: str) -> Dict[str, Any]:
    """Get API credits wasted on repeated attempts"""

    _, _, _, mem_sys = get_systems()

    if not mem_sys:
        raise HTTPException(status_code=503, detail="Episodic memory not initialized")

    return mem_sys.get_wasted_api_credits(agent_id)


# ==================== HELPER FUNCTIONS ====================

def _get_next_steps(route: Any) -> Dict[str, str]:
    """Get next steps based on route"""
    route_value = route.value if hasattr(route, 'value') else str(route)

    steps_map = {
        "hil_validation": "This finding is ready for Human-in-the-Loop validation. Route to auditor for review and approval.",
        "exploit_chaining": "This finding will be combined with other low-severity findings to create higher-impact exploit chains.",
        "duplicate_skip": "This finding matches a previously reported vulnerability. It will be analyzed for chaining opportunities.",
        "discarded": "This finding has insufficient confidence for processing. It may be revisited if confidence improves."
    }

    return {
        "primary": steps_map.get(route_value, "Unknown next step"),
        "workflow": "submit → route → validate/chain → report"
    }
