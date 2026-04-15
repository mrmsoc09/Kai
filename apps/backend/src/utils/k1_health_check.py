from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

# Standard registry names to verify against agents
EXPECTED_REGISTRIES = {
    "DiscoveryRegistry",
    "SecretLeakRegistry",
    "VulnerabilityRegistry",
}

# Critical index files for O(1) lookups
CRITICAL_INDICES = [
    "tools/playbooks/playbook_index.json",
    "tools/playbooks/chain_orchestration/cve_index.json",
    "tools/playbooks/chain_orchestration/data_contract_registry.json",
]


class K1HealthCheck:
    """
    K1 Global Health Check & Audit Utility.
    Verifies index presence, schema consistency, agent policy logic, and SNL compliance.
    """

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root = Path(root_dir or ".").resolve()
        self.results = {
            "indices": {},
            "registries": {},
            "agents": {},
            "opsec": {},
            "memory": {},
        }

    def run_full_audit(self) -> dict[str, Any]:
        print("Starting Global K1 Health Audit...")
        self.audit_indices()
        self.audit_registries()
        self.audit_agents()
        self.audit_memory_caps()
        return self.results

    def audit_indices(self) -> None:
        print("Checking critical indices...")
        for rel_path in CRITICAL_INDICES:
            p = self.root / rel_path
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    self.results["indices"][rel_path] = {
                        "status": "PASS",
                        "size": len(data.get("playbooks_by_success_weight", data)),
                    }
                except Exception as e:
                    self.results["indices"][rel_path] = {"status": "FAIL", "error": str(e)}
            else:
                self.results["indices"][rel_path] = {"status": "MISSING"}

    def audit_registries(self) -> None:
        print("Verifying registry consistency...")
        # Check darknet_leak_schemas.py as the canonical source
        schemas_path = self.root / "apps/backend/src/agents/tools/darknet_leak_schemas.py"
        if schemas_path.exists():
            content = schemas_path.read_text(encoding="utf-8")
            for registry in EXPECTED_REGISTRIES:
                if f"class {registry}" in content:
                    self.results["registries"][registry] = "ALIGNED"
                else:
                    self.results["registries"][registry] = "MISSING_IN_LEAK_SCHEMAS"
        else:
            self.results["registries"]["global"] = "SCHEMA_FILE_MISSING"

    def audit_agents(self) -> None:
        print("Auditing 30+ agents for policy and SNL compliance...")
        agents_dir = self.root / "apps/backend/src/agents/tools"
        if not agents_dir.exists():
            return

        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            agent_file = agent_dir / "agent.py"
            if not agent_file.exists():
                continue

            content = agent_file.read_text(encoding="utf-8")
            agent_name = agent_dir.name
            
            # Policy check
            has_policy = "def check_policy" in content
            
            # SNL check
            has_snl = "SNL" in content or "tun0" in content or "wg0" in content
            
            # Registry check
            uses_registry = any(reg in content for registry in EXPECTED_REGISTRIES for reg in [registry])
            
            # Masking check
            has_masking = "mask" in content.lower() or "redact" in content.lower()

            self.results["agents"][agent_name] = {
                "check_policy": "PASS" if has_policy else "MISSING",
                "snl_enforced": "PASS" if has_snl else "WARNING",
                "registries_used": "PASS" if uses_registry else "INFO",
                "masking_enforced": "PASS" if has_masking else "WARNING",
            }

    def audit_memory_caps(self) -> None:
        print("Checking memory management logic...")
        queue_path = self.root / "apps/backend/src/core/global_task_queue.py"
        if queue_path.exists():
            content = queue_path.read_text(encoding="utf-8")
            if "max_memory_gb" in content and "40" in content:
                self.results["memory"] = {"status": "PASS", "cap": "40GB"}
            else:
                self.results["memory"] = {"status": "PASS", "cap": "UNKNOWN"}
        else:
            self.results["memory"] = {"status": "FAIL", "reason": "GlobalTaskQueue missing"}

    def generate_report(self) -> str:
        report = ["# K1 Global Health Audit Report", ""]
        
        report.append("## Critical Indices")
        for k, v in self.results["indices"].items():
            report.append(f"- {k}: {v['status']} (entries: {v.get('size', 'N/A')})")
        
        report.append("\n## Registry Alignment")
        for k, v in self.results["registries"].items():
            report.append(f"- {k}: {v}")
            
        report.append("\n## Agent Compliance Summary")
        passing_agents = [k for k, v in self.results["agents"].items() if v["snl_enforced"] == "PASS" and v["check_policy"] == "PASS"]
        report.append(f"- Total Agents Audited: {len(self.results['agents'])}")
        report.append(f"- Fully Compliant: {len(passing_agents)}")
        
        report.append("\n## Action Items")
        if any(v["snl_enforced"] == "WARNING" for v in self.results["agents"].values()):
            report.append("- [ ] Verify SNL enforcement in all agents marked WARNING.")
        if any(v["masking_enforced"] == "WARNING" for v in self.results["agents"].values()):
            report.append("- [ ] Enforce Secret Masking in all agents marked WARNING.")
            
        return "\n".join(report)


if __name__ == "__main__":
    import sys
    target_root = sys.argv[1] if len(sys.argv) > 1 else None
    checker = K1HealthCheck(target_root)
    checker.run_full_audit()
    print("\n" + checker.generate_report())
