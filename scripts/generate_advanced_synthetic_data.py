"""Advanced Synthetic Data Generator for Kai Platform

Generates complex synthetic data including vulnerability chains and zero-day scenarios.
"""

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any


class AdvancedSyntheticDataGenerator:
    """Generates advanced synthetic data with chains and zero-days."""

    def __init__(self, output_dir: str = "/home/k1-admin/Kai/synthetic_data"):
        self.output_dir = Path(output_dir)
        self.vuln_chains = self._define_vuln_chains()
        self.zero_days = self._define_zero_days()

    def _define_vuln_chains(self) -> List[Dict[str, Any]]:
        """Define common vulnerability chains."""
        return [
            {
                "name": "Web App Chain",
                "steps": [
                    {"type": "discovery", "desc": "Find exposed admin panel"},
                    {"type": "fingerprint", "desc": "Detect outdated CMS version"},
                    {"type": "exploit", "desc": "SQL injection in login form"},
                    {"type": "escalate", "desc": "Privilege escalation via misconfigured permissions"}
                ]
            },
            {
                "name": "API Chain",
                "steps": [
                    {"type": "recon", "desc": "Discover API endpoints"},
                    {"type": "auth_bypass", "desc": "Broken authentication"},
                    {"type": "injection", "desc": "Command injection in API parameter"},
                    {"type": "data_exfil", "desc": "Extract sensitive data"}
                ]
            },
            {
                "name": "Network Chain",
                "steps": [
                    {"type": "port_scan", "desc": "Find open ports"},
                    {"type": "service_enum", "desc": "Enumerate service versions"},
                    {"type": "exploit", "desc": "Buffer overflow in service"},
                    {"type": "pivot", "desc": "Use compromised host to attack internal network"}
                ]
            }
        ]

    def _define_zero_days(self) -> List[Dict[str, Any]]:
        """Define zero-day vulnerability scenarios."""
        return [
            {
                "name": "Zero-Day RCE in Custom Framework",
                "description": "Remote code execution in proprietary web framework",
                "severity": "CRITICAL",
                "cve": "CVE-2026-XXXX",
                "indicators": ["unusual HTTP headers", "custom error messages"]
            },
            {
                "name": "Zero-Day Auth Bypass",
                "description": "Authentication bypass in SSO implementation",
                "severity": "HIGH",
                "cve": "CVE-2026-YYYY",
                "indicators": ["JWT manipulation", "session fixation"]
            },
            {
                "name": "Zero-Day Memory Corruption",
                "description": "Heap overflow in embedded device firmware",
                "severity": "CRITICAL",
                "cve": "CVE-2026-ZZZZ",
                "indicators": ["device crashes", "unusual network traffic"]
            }
        ]

    def generate_vuln_chains(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate synthetic vulnerability chains."""
        chains = []
        for i in range(count):
            base_chain = random.choice(self.vuln_chains)
            chain = {
                "chain_id": f"chain-syn-{i:03d}",
                "name": f"{base_chain['name']} Instance {i+1}",
                "target": f"target{random.randint(1,5)}.example.com",
                "severity": random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
                "steps": base_chain["steps"],
                "success_probability": random.uniform(0.1, 0.9),
                "prerequisites": [f"Step {j+1} completed" for j in range(len(base_chain["steps"]) - 1)],
                "impact": "Data exfiltration and system compromise",
                "mitigation": "Apply security patches and input validation"
            }
            chains.append(chain)
        return chains

    def generate_zero_day_scenarios(self, count: int = 5) -> List[Dict[str, Any]]:
        """Generate synthetic zero-day scenarios."""
        scenarios = []
        for i in range(count):
            base_zero = random.choice(self.zero_days)
            scenario = {
                "scenario_id": f"zero-syn-{i:03d}",
                "name": base_zero["name"],
                "description": base_zero["description"],
                "target_type": random.choice(["web_app", "api", "network_device", "mobile_app"]),
                "discovery_date": datetime.now(timezone.utc).isoformat(),
                "severity": base_zero["severity"],
                "cve_candidate": base_zero["cve"].replace("XXXX", f"{random.randint(1000,9999)}"),
                "indicators": base_zero["indicators"] + [f"custom_indicator_{random.randint(1,10)}"],
                "exploit_complexity": random.choice(["LOW", "MEDIUM", "HIGH"]),
                "detection_difficulty": random.choice(["EASY", "MODERATE", "HARD"]),
                "potential_impact": "Complete system compromise",
                "recommended_response": "Isolate affected systems, monitor for IOCs"
            }
            scenarios.append(scenario)
        return scenarios

    def generate_training_prompts(self, chains: List[Dict], zero_days: List[Dict]) -> List[Dict[str, str]]:
        """Generate AI training prompts from chains and zero-days."""
        prompts = []

        for chain in chains:
            prompt = {
                "input": f"Analyze this vulnerability chain: {chain['name']} on {chain['target']}. Steps: {[s['desc'] for s in chain['steps']]}. What is the next best action?",
                "output": f"Given the chain severity {chain['severity']} and success probability {chain['success_probability']:.2f}, recommend {random.choice(['immediate exploitation', 'further reconnaissance', 'report finding'])}."
            }
            prompts.append(prompt)

        for zero in zero_days:
            prompt = {
                "input": f"Detected potential zero-day: {zero['name']} with indicators {zero['indicators']}. Severity: {zero['severity']}. How to proceed?",
                "output": f"For this {zero['exploit_complexity']} complexity zero-day, {random.choice(['isolate and analyze', 'monitor closely', 'engage incident response'])}."
            }
            prompts.append(prompt)

        return prompts

    def save_all(self):
        """Generate and save all advanced synthetic data."""
        chains = self.generate_vuln_chains()
        zero_days = self.generate_zero_day_scenarios()
        prompts = self.generate_training_prompts(chains, zero_days)

        # Save chains
        chains_file = self.output_dir / "advanced" / "vuln_chains.json"
        chains_file.parent.mkdir(exist_ok=True, parents=True)
        with open(chains_file, "w") as f:
            json.dump(chains, f, indent=2)

        # Save zero-days
        zero_file = self.output_dir / "advanced" / "zero_days.json"
        with open(zero_file, "w") as f:
            json.dump(zero_days, f, indent=2)

        # Save training prompts
        train_file = self.output_dir / "training" / "advanced_training.json"
        with open(train_file, "w") as f:
            json.dump(prompts, f, indent=2)

        return {
            "chains_file": str(chains_file),
            "zero_days_file": str(zero_file),
            "training_file": str(train_file),
            "chains_count": len(chains),
            "zero_days_count": len(zero_days),
            "prompts_count": len(prompts)
        }


if __name__ == "__main__":
    generator = AdvancedSyntheticDataGenerator()
    results = generator.save_all()
    print(f"Generated advanced synthetic data: {results}")