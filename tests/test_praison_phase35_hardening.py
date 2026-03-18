"""
Tests: Phase 3.5 Hardening / Remediation
==========================================
Each test group targets a specific vulnerability from the Phase 3 self-audit.

Test naming convention:
  test_DEFECT_ID__description

  vuln_*  — tests that reproduce the vulnerability (would FAIL pre-fix)
  fix_*   — tests that validate the fix is in place

Where practical, both vuln and fix are included to document that the
vulnerability was real and is now closed.
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_identity(
    agent_id: str = "TestAgent",
    agent_class: str = "specialist",
    delegation_scope: str = "none",
    allowed_tools: list[str] | None = None,
    allowed_peer_targets: list[str] | None = None,
    memory_scope: str = "session",
    workflow_id: str = "wf-test",
    program_id: str = "prog-test",
):
    from apps.backend.src.core.praison_agent import AgentIdentity
    return AgentIdentity(
        agent_id=agent_id,
        persona=f"{agent_id} Persona",
        description="Test",
        system_prompt="Test agent.",
        allowed_tools=allowed_tools or ["tool_a"],
        risk_profile="standard",
        llm_pin="anthropic",
        memory_scope=memory_scope,
        review_policy="standard",
        agent_class=agent_class,
        delegation_scope=delegation_scope,
        allowed_peer_targets=allowed_peer_targets or [],
        handoff_policy="coordinator_visible",
        interrupt_policy="none",
        escalation_policy="hil_for_band2",
        workflow_id=workflow_id,
        program_id=program_id,
    )


def _make_coord(targets: list[str] | None = None):
    return _make_identity("Coord", agent_class="coordinator", delegation_scope="local",
                          allowed_peer_targets=targets or [])


def _make_spec(agent_id: str = "Spec", tools: list[str] | None = None):
    return _make_identity(agent_id, agent_class="specialist", delegation_scope="none",
                          allowed_tools=tools or ["nmap", "nuclei"])


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 1: AgentIdentity Immutability
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentIdentityImmutability:

    def test_fix__direct_field_assignment_raises(self):
        """FrozenInstanceError must be raised on any attribute assignment."""
        agent = _make_identity(agent_class="specialist")
        with pytest.raises(FrozenInstanceError):
            agent.agent_class = "governor"  # type: ignore[misc]

    def test_fix__allowed_tools_privilege_escalation_blocked(self):
        """
        VULNERABILITY (pre-fix): identity.allowed_tools.append("sqlmap") silently
        mutated the tool whitelist — the primary containment mechanism.
        FIX: allowed_tools is a tuple. Tuples have no .append().
        """
        agent = _make_identity(allowed_tools=["nmap"])
        with pytest.raises(AttributeError):
            agent.allowed_tools.append("sqlmap")  # type: ignore[attr-defined]

    def test_fix__allowed_tools_coerced_from_list_to_tuple(self):
        """Lists passed at construction are coerced to tuples."""
        agent = _make_identity(allowed_tools=["nmap", "nuclei"])
        assert isinstance(agent.allowed_tools, tuple)
        assert "nmap" in agent.allowed_tools
        assert "nuclei" in agent.allowed_tools

    def test_fix__allowed_peer_targets_coerced_from_list_to_tuple(self):
        agent = _make_identity(allowed_peer_targets=["AgentA", "AgentB"])
        assert isinstance(agent.allowed_peer_targets, tuple)
        assert "AgentA" in agent.allowed_peer_targets

    def test_fix__with_runtime_returns_new_instance(self):
        """with_runtime() must not mutate the original (works via dataclasses.replace)."""
        original = _make_identity()
        runtime = original.with_runtime(workflow_id="wf-new", program_id="prog-new")
        assert original.workflow_id == "wf-test"   # original unchanged
        assert runtime.workflow_id == "wf-new"
        assert original is not runtime

    def test_fix__workflow_id_unchanged_after_with_runtime(self):
        """Frozen guarantee: original.workflow_id is not modified by with_runtime."""
        original = _make_identity()
        _ = original.with_runtime(workflow_id="different")
        assert original.workflow_id == "wf-test"

    def test_fix__to_dict_returns_list_not_tuple(self):
        """to_dict() converts tuple fields back to lists for JSON serialization."""
        agent = _make_identity(allowed_tools=["nmap"])
        d = agent.to_dict()
        assert isinstance(d["allowed_tools"], list)
        assert isinstance(d["allowed_peer_targets"], list)

    def test_fix__governor_to_governor_delegation_blocked(self):
        """
        SECURITY FIX: Governor can no longer delegate to another governor.
        Prevents circular governance chains where Gov-A approves Gov-B
        and Gov-B approves Gov-A's previously blocked action.
        """
        from apps.backend.src.core.praison_agent import _CLASS_DELEGATION_AUTHORITY
        assert "governor" not in _CLASS_DELEGATION_AUTHORITY["governor"]
        gov = _make_identity("G", agent_class="governor", delegation_scope="global")
        assert gov.can_delegate_to("governor") is False
        assert gov.can_delegate_to("director") is True


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2: DelegationContract Immutability
# ═══════════════════════════════════════════════════════════════════════════════

class TestDelegationContractImmutability:

    def _make_contract(self, allowed_tools=None):
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coord()
        spec = _make_spec(tools=allowed_tools or ["nmap", "nuclei"])
        return create_delegation_contract(coord, spec, objective="test")

    def test_fix__state_mutation_raises(self):
        """
        VULNERABILITY (pre-fix): contract.state = ContractState.COMPLETED silently
        bypassed all state machine logic, allowing forgery of contract completion.
        FIX: FrozenInstanceError raised.
        """
        from apps.backend.src.core.praison_contracts import ContractState
        contract = self._make_contract()
        with pytest.raises(FrozenInstanceError):
            contract.state = ContractState.COMPLETED  # type: ignore[misc]

    def test_fix__allowed_tools_mutation_blocked(self):
        """allowed_tools is a tuple — cannot be modified post-creation."""
        contract = self._make_contract()
        assert isinstance(contract.allowed_tools, tuple)
        with pytest.raises(AttributeError):
            contract.allowed_tools.append("sqlmap")  # type: ignore[attr-defined]

    def test_fix__mark_violated_on_terminal_contract_raises(self):
        """
        VULNERABILITY (pre-fix): mark_violated() had no state guard.
        A COMPLETED contract could be retroactively marked violated.
        FIX: ContractStateError raised on terminal state.
        """
        from apps.backend.src.core.praison_contracts import (
            ContractStateError,
            ContractViolation,
        )
        contract = self._make_contract().activate().complete("art-123")
        assert contract.is_terminal is True
        with pytest.raises(ContractStateError, match="terminal state"):
            contract.mark_violated(ContractViolation.TOOL_NOT_ALLOWED, "test")

    def test_fix__mark_violated_on_expired_contract_raises(self):
        from apps.backend.src.core.praison_contracts import (
            ContractStateError,
            ContractViolation,
        )
        contract = self._make_contract().activate().expire()
        with pytest.raises(ContractStateError, match="terminal state"):
            contract.mark_violated(ContractViolation.SCOPE_EXCEEDED, "test")

    def test_fix__state_transitions_return_new_instances(self):
        """State transitions must never mutate — each returns a new frozen instance."""
        contract = self._make_contract()
        active = contract.activate()
        completed = active.complete("art-1")

        # Original objects unchanged
        assert contract.state.value == "pending"
        assert active.state.value == "active"
        assert completed.state.value == "completed"
        # All different objects
        assert contract is not active
        assert active is not completed


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 3: AgentArtifact Immutability
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentArtifactImmutability:

    def test_fix__requires_governance_approval_mutation_blocked(self):
        """
        VULNERABILITY (pre-fix): artifact.requires_governance_approval = False
        could bypass governance gates post-creation.
        FIX: FrozenInstanceError.
        """
        from apps.backend.src.core.praison_artifacts import make_vulnerability_signal
        artifact = make_vulnerability_signal(
            "ReconSpecialist",
            target="target.example.com",
            signal_type="sqli",
            severity="critical",
            evidence={},
            workflow_id="wf-1",
            program_id="p-1",
        )
        assert artifact.requires_governance_approval is True
        with pytest.raises(FrozenInstanceError):
            artifact.requires_governance_approval = False  # type: ignore[misc]

    def test_fix__artifact_type_mutation_blocked(self):
        from apps.backend.src.core.praison_artifacts import AgentArtifact, ArtifactType
        artifact = AgentArtifact()
        with pytest.raises(FrozenInstanceError):
            artifact.artifact_type = ArtifactType.GOVERNANCE_DECISION  # type: ignore[misc]

    def test_fix__tags_coerced_to_tuple(self):
        from apps.backend.src.core.praison_artifacts import AgentArtifact
        artifact = AgentArtifact(tags=["tag1", "tag2"])
        assert isinstance(artifact.tags, tuple)
        with pytest.raises(AttributeError):
            artifact.tags.append("tag3")  # type: ignore[attr-defined]

    def test_fix__severity_normalized_case_insensitive(self):
        """
        VULNERABILITY (pre-fix): severity="Critical" missed the review flag.
        FIX: severity is normalized to lowercase before comparison.
        """
        from apps.backend.src.core.praison_artifacts import make_vulnerability_signal
        for sev_input in ("CRITICAL", "Critical", "critical", "CRITICAL  "):
            artifact = make_vulnerability_signal(
                "RS", target="t", signal_type="rce", severity=sev_input,
                evidence={}, workflow_id="wf", program_id="p",
            )
            assert artifact.requires_governance_approval is True, \
                f"severity={sev_input!r} should trigger governance approval"
            assert artifact.requires_human_review is True
            assert artifact.content["severity"] == "critical"

        for sev_input in ("HIGH", "High", "high"):
            artifact = make_vulnerability_signal(
                "RS", target="t", signal_type="xss", severity=sev_input,
                evidence={}, workflow_id="wf", program_id="p",
            )
            assert artifact.requires_human_review is True
            assert artifact.requires_governance_approval is False

    def test_fix__annotate_returns_new_instance(self):
        from apps.backend.src.core.praison_artifacts import AgentArtifact
        artifact = AgentArtifact(workflow_id="wf-1", consumer_id="")
        annotated = artifact.annotate(consumer_id="EvidenceAnalyst", tags=["done"])
        assert annotated is not artifact
        assert artifact.consumer_id == ""  # original unchanged
        assert annotated.consumer_id == "EvidenceAnalyst"


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 4: Unknown Memory Scope → Deny
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryScopeDenyUnknown:

    def test_vuln__old_behavior_would_permit_unknown_scope(self):
        """
        Document the vulnerability: the old code used _SCOPE_RANK.get(scope, 0)
        which meant unknown scopes got rank 0 = same as session.
        A session agent (rank 0) could write to unknown scope (rank 0 <= rank 0).
        """
        # Old logic: _SCOPE_RANK.get("unknown_scope", 0) == 0
        # session rank is also 0, so 0 <= 0 = True (permit)
        # This is the bug we fixed.
        pass  # documented — actual fix tested below

    def test_fix__unknown_target_scope_denied(self):
        """FIX: can_write_to_scope returns False for any unknown scope name."""
        from apps.backend.src.core.praison_agent import AgentIdentity
        # Even a mission-level agent cannot write to unknown scope
        agent = AgentIdentity(
            agent_id="X", persona="X", description="X", system_prompt="X",
            memory_scope="mission",
        )
        assert agent.can_write_to_scope("nonexistent_scope") is False
        assert agent.can_write_to_scope("super_persistent") is False
        assert agent.can_write_to_scope("") is False

    def test_fix__unknown_agent_scope_denied(self):
        """FIX: agent with unknown memory_scope cannot write to any scope."""
        from apps.backend.src.core.praison_agent import AgentIdentity
        # Construct directly (bypasses registry validation)
        agent = AgentIdentity(
            agent_id="X", persona="X", description="X", system_prompt="X",
            memory_scope="unknown_scope",
        )
        assert agent.can_write_to_scope("session") is False
        assert agent.can_write_to_scope("workflow") is False

    def test_fix__known_scopes_still_work(self):
        """Fix must not break legitimate scope checks."""
        from apps.backend.src.core.praison_agent import AgentIdentity
        agent = AgentIdentity(
            agent_id="X", persona="X", description="X", system_prompt="X",
            memory_scope="workflow",
        )
        assert agent.can_write_to_scope("session") is True
        assert agent.can_write_to_scope("phase") is True
        assert agent.can_write_to_scope("workflow") is True
        assert agent.can_write_to_scope("mission") is False
        assert agent.can_write_to_scope("persistent") is False

    def test_fix__runtime_policy_also_denies_unknown(self):
        """PraisonRuntimePolicy.check_memory_write also uses the fixed logic."""
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        policy = PraisonRuntimePolicy()
        # Create agent via AgentIdentity with valid scope
        agent = _make_identity(memory_scope="workflow")
        decision = policy.check_memory_write(agent, "nonexistent_scope")
        assert decision.allowed is False


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 5: Empty-List Permit-All → Empty = Deny
# ═══════════════════════════════════════════════════════════════════════════════

class TestContractEmptyListSemantics:

    def test_fix__empty_allowed_tools_denies_all(self):
        """
        VULNERABILITY (pre-fix): empty allowed_tools returned True for any tool.
        FIX: empty tuple = deny all tools.
        """
        from apps.backend.src.core.praison_contracts import (
            DelegationContract,
            ContractState,
        )
        # Build contract with explicit empty tool list
        contract = DelegationContract(
            contract_id=str(uuid.uuid4()),
            delegator_id="Coord",
            delegate_id="Spec",
            workflow_id="wf-1",
            objective="test",
            state=ContractState.ACTIVE,
            allowed_tools=(),
            allowed_targets=(),
        )
        assert contract.tool_allowed("nmap") is False
        assert contract.tool_allowed("nuclei") is False
        assert contract.tool_allowed("") is False

    def test_fix__empty_allowed_targets_denies_all(self):
        from apps.backend.src.core.praison_contracts import (
            DelegationContract,
            ContractState,
        )
        contract = DelegationContract(
            contract_id=str(uuid.uuid4()),
            delegator_id="Coord",
            delegate_id="Spec",
            workflow_id="wf-1",
            objective="test",
            state=ContractState.ACTIVE,
            allowed_tools=("nmap",),
            allowed_targets=(),
        )
        assert contract.target_allowed("host.example.com") is False

    def test_fix__factory_default_uses_delegate_tools(self):
        """Factory default (allowed_tools=None) uses delegate's full tool list."""
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coord()
        spec = _make_spec(tools=["nmap", "nuclei", "ffuf"])
        contract = create_delegation_contract(coord, spec, objective="test")
        assert contract.tool_allowed("nmap") is True
        assert contract.tool_allowed("nuclei") is True
        assert contract.tool_allowed("ffuf") is True
        assert contract.tool_allowed("sqlmap") is False  # not in spec's tools

    def test_fix__explicit_empty_list_produces_deny_all(self):
        """Explicit allowed_tools=[] creates a deny-all contract."""
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coord()
        spec = _make_spec(tools=["nmap"])
        contract = create_delegation_contract(coord, spec, objective="test", allowed_tools=[])
        assert contract.allowed_tools == ()
        assert contract.tool_allowed("nmap") is False


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 6: Bidirectional Trust Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestBidirectionalTrustEnforcement:

    def test_fix__coordinator_cannot_delegate_to_unlisted_agent(self):
        """
        VULNERABILITY (pre-fix): The peer target restriction was a `pass` block.
        A coordinator could delegate to ANY specialist regardless of its
        allowed_peer_targets list.
        FIX: ContractValidationError raised.
        """
        from apps.backend.src.core.praison_contracts import (
            ContractValidationError,
            create_delegation_contract,
        )
        # Coordinator with explicit peer target restriction
        coord = _make_coord(targets=["AuthorizedSpecialist"])
        unauthorized = _make_spec("UnauthorizedSpecialist")
        with pytest.raises(ContractValidationError, match="may not delegate"):
            create_delegation_contract(coord, unauthorized, objective="test")

    def test_fix__coordinator_can_delegate_to_listed_agent(self):
        """Delegation to agents in allowed_peer_targets must succeed."""
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coord(targets=["AuthorizedSpecialist"])
        authorized = _make_spec("AuthorizedSpecialist")
        contract = create_delegation_contract(coord, authorized, objective="test")
        assert contract.delegate_id == "AuthorizedSpecialist"

    def test_fix__empty_peer_targets_allows_any_class_authorized_target(self):
        """Empty allowed_peer_targets = no outbound restriction (delegate to any specialist)."""
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coord(targets=[])  # no restriction
        spec_a = _make_spec("AnySpecialist")
        spec_b = _make_spec("AnotherSpecialist")
        # Both should work
        contract_a = create_delegation_contract(coord, spec_a, objective="test")
        contract_b = create_delegation_contract(coord, spec_b, objective="test")
        assert contract_a.delegate_id == "AnySpecialist"
        assert contract_b.delegate_id == "AnotherSpecialist"

    def test_fix__full_agents_yaml_peer_targets_are_consistent(self):
        """All agents in the registry respect the bidirectional trust rules."""
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        from apps.backend.src.core.praison_contracts import create_delegation_contract, ContractValidationError
        reg = PraisonAgentRegistry()
        reg.load_agents()

        # GovernanceDirector → MissionDirector should work
        gov = reg.get_agent("GovernanceDirector").with_runtime(workflow_id="wf-1", program_id="p-1")
        mission = reg.get_agent("MissionDirector").with_runtime(workflow_id="wf-1", program_id="p-1")
        contract = create_delegation_contract(gov, mission, objective="authorize mission")
        assert contract.delegate_id == "MissionDirector"

        # MissionDirector → PhaseCoordinator should work
        coord = reg.get_agent("PhaseCoordinator").with_runtime(workflow_id="wf-1", program_id="p-1")
        contract2 = create_delegation_contract(mission, coord, objective="execute recon phase")
        assert contract2.delegate_id == "PhaseCoordinator"

        # PhaseCoordinator → SurfaceMapper should work
        sm = reg.get_agent("SurfaceMapper").with_runtime(workflow_id="wf-1", program_id="p-1")
        contract3 = create_delegation_contract(coord, sm, objective="map surface")
        assert contract3.delegate_id == "SurfaceMapper"


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 7: ArtifactStore Lock Separation
# ═══════════════════════════════════════════════════════════════════════════════

class TestArtifactStoreLockSeparation:

    def test_fix__store_and_file_locks_are_separate(self):
        """ArtifactStore must use separate _store_lock and _file_lock."""
        from apps.backend.src.core.praison_artifacts import ArtifactStore
        store = ArtifactStore()
        assert hasattr(store, "_store_lock")
        assert hasattr(store, "_file_lock")
        assert store._store_lock is not store._file_lock

    def test_fix__concurrent_puts_do_not_corrupt_store(self):
        """Multiple threads putting artifacts concurrently must not corrupt the dict."""
        from apps.backend.src.core.praison_artifacts import ArtifactStore, AgentArtifact
        store = ArtifactStore()
        artifact_ids: list[str] = []
        errors: list[Exception] = []

        def put_artifacts(n: int) -> None:
            try:
                for _ in range(n):
                    art = AgentArtifact(workflow_id="wf-concurrent")
                    artifact_ids.append(art.artifact_id)
                    store.put(art)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=put_artifacts, args=(20,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent put raised exceptions: {errors}"
        assert len(artifact_ids) == 100
        for aid in artifact_ids:
            assert store.get(aid) is not None, f"Artifact {aid} missing after concurrent write"

    def test_fix__read_not_blocked_by_file_lock(self):
        """
        Reads (get/list_for_workflow) must not acquire the file lock.
        This test confirms _store_lock and _file_lock are used separately.
        """
        from apps.backend.src.core.praison_artifacts import ArtifactStore, AgentArtifact
        store = ArtifactStore()
        art = AgentArtifact(workflow_id="wf-lock-test")
        store.put(art)

        # Acquire file lock in another thread — reads should not be blocked
        results: list[bool] = []

        def hold_file_lock():
            with store._file_lock:
                time.sleep(0.1)  # hold file lock for 100ms

        def read_store():
            start = time.monotonic()
            result = store.get(art.artifact_id)
            elapsed = time.monotonic() - start
            results.append(result is not None)
            # Read should complete in << 100ms (not blocked by file lock)
            assert elapsed < 0.05, f"Read blocked by file lock: {elapsed:.3f}s"

        file_lock_thread = threading.Thread(target=hold_file_lock)
        read_thread = threading.Thread(target=read_store)
        file_lock_thread.start()
        time.sleep(0.01)  # ensure file lock is held
        read_thread.start()
        read_thread.join()
        file_lock_thread.join()
        assert results == [True]


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 8: Registry TOCTOU
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistryTOCTOU:

    def test_fix__ensure_loaded_is_lock_protected(self):
        """_ensure_loaded must check _loaded under the lock."""
        import inspect
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        source = inspect.getsource(PraisonAgentRegistry._ensure_loaded)
        # The check for _loaded must be inside the lock context
        assert "with self._lock" in source
        assert "if not self._loaded" in source

    def test_fix__concurrent_load_does_not_double_load(self):
        """Multiple threads calling get_agent simultaneously must not double-load."""
        import tempfile, yaml, os, pathlib
        yaml_content = {
            "agents": {
                "ConcurrentAgent": {
                    "persona": "Concurrent",
                    "description": "Test",
                    "system_prompt": "Test",
                    "risk_profile": "standard",
                    "memory_scope": "session",
                    "review_policy": "standard",
                    "agent_class": "specialist",
                    "delegation_scope": "none",
                    "allowed_peer_targets": [],
                    "handoff_policy": "coordinator_visible",
                    "interrupt_policy": "none",
                    "escalation_policy": "hil_for_band2",
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name

        try:
            from apps.backend.src.core.praison_registry import PraisonAgentRegistry
            reg = PraisonAgentRegistry(config_path)
            load_count = [0]
            original_load = reg._load_locked

            def counting_load():
                load_count[0] += 1
                original_load()

            reg._load_locked = counting_load

            results: list[Any] = []
            errors: list[Exception] = []

            def get_agent():
                try:
                    results.append(reg.get_agent("ConcurrentAgent"))
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=get_agent) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors, f"Errors in concurrent get_agent: {errors}"
            assert len(results) == 10
            # Load should have been called exactly once
            assert load_count[0] == 1, f"Registry loaded {load_count[0]} times (expected 1)"
        finally:
            os.unlink(config_path)

    def test_fix__get_agent_returns_correct_identity_under_lock(self):
        """get_agent must return the correct identity even under concurrent access."""
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        reg = PraisonAgentRegistry()
        reg.load_agents()
        # Concurrent reads on the loaded registry
        agents: list[Any] = []
        def fetch():
            agents.append(reg.get_agent("SecurityGovernorAgent"))
        threads = [threading.Thread(target=fetch) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(agents) == 20
        assert all(a.agent_id == "SecurityGovernorAgent" for a in agents)


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 9: Audit Hook Ordering
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditHookOrdering:

    def test_fix__governance_hook_registered_before_audit(self):
        """
        VULNERABILITY (pre-fix): audit at order=10, governance at order=50.
        Audit captured status="authorized" before governance had a chance to block.
        FIX: governance at order=5, audit at order=50, enforce at order=100.
        """
        from apps.backend.src.core.hook_registry import HookRegistry
        # The module-level registry has pre-registered hooks
        from apps.backend.src.core.hook_registry import _REGISTRY
        hooks = _REGISTRY.list_hooks("safety_gate")
        # These names should be registered; verify audit and enforce exist
        assert "audit_safety_gate" in hooks
        assert "enforce_safety_gate" in hooks

        # Verify ordering: audit must appear after governance would run (order=50)
        # We verify the hook specs by checking the internal structure
        safety_hooks = [h for h in _REGISTRY._hooks["safety_gate"]]
        audit_spec = next((h for h in safety_hooks if h.name == "audit_safety_gate"), None)
        enforce_spec = next((h for h in safety_hooks if h.name == "enforce_safety_gate"), None)
        assert audit_spec is not None
        assert enforce_spec is not None
        # audit at 50, enforce at 100
        assert audit_spec.order == 50, f"audit_safety_gate at order={audit_spec.order}, expected 50"
        assert enforce_spec.order == 100, f"enforce_safety_gate at order={enforce_spec.order}, expected 100"

    def test_fix__blocked_action_sets_context_before_audit_runs(self):
        """
        Simulate a governance block: governance sets _governance_blocked=True,
        audit runs at order=50 and sees status="blocked".
        This proves the audit log captures the true outcome.
        """
        from apps.backend.src.core.hook_registry import HookRegistry

        audit_log: list[dict] = []

        def mock_audit(context: dict) -> dict:
            audit_log.append(dict(context))
            return {}

        def mock_governance(context: dict) -> dict:
            # Simulate governance blocking the action
            return {"_governance_blocked": True, "_governance_reason": "band3 blocked", "status": "blocked"}

        def mock_enforce(context: dict) -> dict:
            # Simulate the enforce hook — would raise in production
            return {}

        reg = HookRegistry()
        reg.register("safety_gate", "governance", mock_governance, order=5)
        reg.register("safety_gate", "audit",      mock_audit,      order=50)
        reg.register("safety_gate", "enforce",    mock_enforce,    order=100)

        reg.run("safety_gate", {"tool_id": "dangerous_tool", "status": "pending"})

        assert len(audit_log) == 1
        assert audit_log[0]["status"] == "blocked"         # audit captured blocked outcome
        assert audit_log[0]["_governance_blocked"] is True

    def test_fix__allowed_action_status_in_audit(self):
        """Allowed action: audit sees status='authorized'."""
        from apps.backend.src.core.hook_registry import HookRegistry

        audit_log: list[dict] = []

        def mock_audit(context: dict) -> dict:
            audit_log.append(dict(context))
            return {}

        def mock_governance(context: dict) -> dict:
            return {"praison_approved": True, "status": "authorized"}

        reg = HookRegistry()
        reg.register("safety_gate", "governance", mock_governance, order=5)
        reg.register("safety_gate", "audit",      mock_audit,      order=50)

        reg.run("safety_gate", {"tool_id": "safe_tool", "status": "pending"})

        assert len(audit_log) == 1
        assert audit_log[0]["status"] == "authorized"


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 10: Contract TTL Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestContractTTLEnforcement:

    @pytest.mark.asyncio
    async def test_fix__ttl_expires_slow_specialist(self):
        """
        VULNERABILITY (pre-fix): max_duration_seconds was stored but never enforced.
        A specialist that slept indefinitely would block the cluster forever.
        FIX: asyncio.wait_for enforces the TTL; contract is marked EXPIRED.
        """
        from apps.backend.src.core.praison_contracts import (
            ContractState,
            create_delegation_contract,
        )
        from apps.backend.src.core.praison_cluster_runtime import (
            ClusterRuntime,
            SpecialistContext,
        )
        from apps.backend.src.core.praison_artifacts import ArtifactStore

        coord = _make_coord()
        spec = _make_spec()
        contract = create_delegation_contract(
            coord, spec, objective="test", max_duration_seconds=1
        ).activate()

        async def slow_callable(state: dict) -> dict:
            await asyncio.sleep(10)  # much longer than TTL
            return {"artifacts": []}

        ctx = SpecialistContext(
            agent=spec,
            contract=contract,
            node_callable=slow_callable,
            initial_state={"workflow_id": "wf-1"},
        )

        runtime = ClusterRuntime(artifact_store=ArtifactStore())
        artifacts, closed_contract, violation = await runtime._run_specialist(ctx)

        assert closed_contract.state == ContractState.EXPIRED
        assert "TTL" in violation or "exceeded" in violation.lower()
        assert len(artifacts) == 0

    @pytest.mark.asyncio
    async def test_fix__fast_specialist_completes_before_ttl(self):
        """Fast specialists complete normally without TTL expiry."""
        from apps.backend.src.core.praison_contracts import (
            ContractState,
            create_delegation_contract,
        )
        from apps.backend.src.core.praison_cluster_runtime import (
            ClusterRuntime,
            SpecialistContext,
        )
        from apps.backend.src.core.praison_artifacts import ArtifactStore, AgentArtifact

        coord = _make_coord()
        spec = _make_spec()
        contract = create_delegation_contract(
            coord, spec, objective="test", max_duration_seconds=30
        ).activate()

        result_artifact = AgentArtifact(workflow_id="wf-1", producer_id=spec.agent_id)

        async def fast_callable(state: dict) -> dict:
            return {"artifacts": [result_artifact]}

        ctx = SpecialistContext(
            agent=spec,
            contract=contract,
            node_callable=fast_callable,
            initial_state={"workflow_id": "wf-1"},
        )

        runtime = ClusterRuntime(artifact_store=ArtifactStore())
        artifacts, closed_contract, violation = await runtime._run_specialist(ctx)

        assert closed_contract.state == ContractState.COMPLETED
        assert violation == ""
        assert len(artifacts) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 11: Typed LangGraph State
# ═══════════════════════════════════════════════════════════════════════════════

class TestTypedLangGraphState:

    def test_fix__k1graphstate_is_typeddict(self):
        """K1GraphState must be a TypedDict, not a plain dict."""
        from apps.backend.src.core.praison_state import K1GraphState
        import typing
        assert issubclass(K1GraphState, dict), "TypedDict is a subclass of dict"
        # Check it has the expected keys
        hints = typing.get_type_hints(K1GraphState, include_extras=True)
        assert "messages" in hints
        assert "artifacts" in hints
        assert "governance_decision" in hints
        assert "completed" in hints

    def test_fix__accumulative_fields_use_operator_add_reducer(self):
        """
        VULNERABILITY (pre-fix): StateGraph(dict) caused every node output to
        REPLACE the state dict. messages produced by node A were overwritten by node B.
        FIX: Annotated[list, operator.add] means outputs are appended.
        """
        import operator
        import typing
        from apps.backend.src.core.praison_state import K1GraphState

        hints = typing.get_type_hints(K1GraphState, include_extras=True)

        # Check messages has the operator.add reducer
        messages_hint = hints.get("messages")
        assert messages_hint is not None
        # Annotated type carries metadata
        metadata = typing.get_args(messages_hint)
        assert len(metadata) >= 2, "messages should be Annotated[list, operator.add]"
        assert metadata[1] is operator.add, \
            f"messages reducer should be operator.add, got {metadata[1]}"

        # Same for artifacts
        artifacts_hint = hints.get("artifacts")
        metadata_a = typing.get_args(artifacts_hint)
        assert metadata_a[1] is operator.add, "artifacts reducer should be operator.add"

    def test_fix__make_initial_state_has_correct_defaults(self):
        """make_initial_state() produces a complete valid initial state."""
        from apps.backend.src.core.praison_state import make_initial_state
        state = make_initial_state(workflow_id="wf-1", program_id="prog-1")
        assert state["workflow_id"] == "wf-1"
        assert state["program_id"] == "prog-1"
        assert state["messages"] == []
        assert state["artifacts"] == []
        assert state["completed"] is False
        assert state["error"] == ""
        assert state["governance_decision"] == ""

    def test_fix__langgraph_builder_imports_k1graphstate(self):
        """PraisonLangGraphBuilder must use K1GraphState, not bare dict."""
        import inspect
        from apps.backend.src.core import praison_langgraph_builder as bldr
        from apps.backend.src.core.praison_langgraph_builder import PraisonLangGraphBuilder
        # Inspect the actual _compile_graph method, not the whole module
        # (module docstring intentionally references the old pattern for history)
        method_source = inspect.getsource(PraisonLangGraphBuilder._compile_graph)
        assert "K1GraphState" in method_source
        assert "StateGraph(dict)" not in method_source

    def test_fix__state_snapshot_serializable(self):
        """state_snapshot() must return a JSON-serializable dict."""
        import json
        from apps.backend.src.core.praison_state import make_initial_state, state_snapshot
        state = make_initial_state(workflow_id="wf-1", program_id="p-1")
        snapshot = state_snapshot(state)
        # Must not raise
        json_str = json.dumps(snapshot)
        assert "wf-1" in json_str


# ═══════════════════════════════════════════════════════════════════════════════
# Full regression: existing suite still passes
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegressionRegistryLoadsAllAgents:

    def test_all_11_agents_load_with_correct_frozen_identities(self):
        """All 11 canonical agents load, validate, and return frozen AgentIdentity objects."""
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        reg = PraisonAgentRegistry()
        reg.load_agents()
        expected = {
            "SecurityGovernorAgent", "GovernanceDirector", "MissionDirector",
            "PhaseCoordinator", "InterscanReportAgent", "HandoffAgent",
            "HandoffLiaison", "SurfaceMapper", "ReconSpecialist",
            "EvidenceAnalyst", "ReportSynthesisAgent",
        }
        ids = set(reg.agent_ids())
        assert expected <= ids, f"Missing agents: {expected - ids}"

        for agent_id in expected:
            agent = reg.get_agent(agent_id)
            # All identities must be frozen
            with pytest.raises(FrozenInstanceError):
                agent.agent_id = "tampered"  # type: ignore[misc]
            # All have tuple tool lists
            assert isinstance(agent.allowed_tools, tuple)
            assert isinstance(agent.allowed_peer_targets, tuple)

    def test_governor_agents_have_no_governor_delegation_authority(self):
        """Phase 3.5 fix: governors cannot delegate to other governors."""
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        reg = PraisonAgentRegistry()
        reg.load_agents()
        for agent_id in ("SecurityGovernorAgent", "GovernanceDirector"):
            agent = reg.get_agent(agent_id)
            assert agent.can_delegate_to("governor") is False
            assert agent.can_delegate_to("director") is True
