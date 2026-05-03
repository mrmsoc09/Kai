"""
PentAGI BBP-Optimized Attack Chains
Autonomous pentesting workflows for bug bounty programs
"""
import yaml
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class AttackChain:
    name: str
    description: str
    steps: List[Dict[str, Any]]
    target_categories: List[str]
    estimated_time: str
    bounty_potential: str

class PentAGIBBPChains:
    """
    BBP-optimized attack chains for PentAGI autonomous agent.
    Pre-configured workflows for maximum bounty yield.
    """

    CHAINS = {
        "idor_gold_rush": AttackChain(
            name="IDOR Gold Rush",
            description="Sequential ID enumeration for horizontal/vertical privilege escalation",
            steps=[
                {"tool": "katana", "action": "crawl_endpoints", "params": {"depth": 3}},
                {"tool": "ffuf", "action": "fuzz_ids", "params": {"wordlist": "ids.txt", "pattern": "?id=FUZZ"}},
                {"tool": "burp_bapps", "action": "run_autorize", "params": {"detect_missing_auth": True}},
                {"tool": "pentagi", "action": "analyze_auth_patterns", "params": {"compare_privilege_levels": True}},
            ],
            target_categories=["idor", "authentication_bypass", "privilege_escalation"],
            estimated_time="45m",
            bounty_potential="high"
        ),

        "xss_blitz": AttackChain(
            name="XSS Blitz",
            description="Rapid XSS detection across all input vectors",
            steps=[
                {"tool": "katana", "action": "extract_forms_inputs", "params": {}},
                {"tool": "dalfox", "action": "scan_urls", "params": {"blind": True}},
                {"tool": "ffuf", "action": "fuzz_parameters", "params": {"wordlist": "xss_vectors.txt"}},
                {"tool": "cai", "action": "analyze_js_sinks", "params": {}},
            ],
            target_categories=["xss", "stored_xss", "dom_xss", "reflected_xss"],
            estimated_time="30m",
            bounty_potential="medium"
        ),

        "sqli_deep_dive": AttackChain(
            name="SQLi Deep Dive",
            description="Comprehensive SQL injection detection with automated exploitation",
            steps=[
                {"tool": "nikto", "action": "scan_sqli", "params": {}},
                {"tool": "ffuf", "action": "fuzz_sql_params", "params": {"wordlist": "sqli_payloads.txt"}},
                {"tool": "pentagi", "action": "test_sql_injection", "params": {"check_time_based": True}},
                {"tool": "trilium", "action": "exploit_confirm", "params": {"safe_only": True}},
            ],
            target_categories=["sqli", "blind_sqli", "time_based_sqli"],
            estimated_time="60m",
            bounty_potential="critical"
        ),

        "ssrf_rce_hunter": AttackChain(
            name="SSRF/RCE Hunter",
            description="Server-side request forgery and remote code execution detection",
            steps=[
                {"tool": "katana", "action": "find_ssrf_vectors", "params": {}},
                {"tool": "ffuf", "action": "fuzz_ssrf_payloads", "params": {}},
                {"tool": "cai", "action": "analyze_server_behavior", "params": {}},
                {"tool": "pentagi", "action": "escalate_to_rce", "params": {"confirm_safe": True}},
            ],
            target_categories=["ssrf", "rce", "command_injection"],
            estimated_time="90m",
            bounty_potential="critical"
        ),

        "race_condition_blitz": AttackChain(
            name="Race Condition Blitz",
            description="Time-of-check-time-of-use vulnerability detection",
            steps=[
                {"tool": "katana", "action": "identify_stateful_endpoints", "params": {}},
                {"tool": "burp_bapps", "action": "run_turbo_intruder", "params": {"race_detection": True, "concurrent": 30}},
                {"tool": "pentagi", "action": "analyze_timing_windows", "params": {}},
            ],
            target_categories=["race_condition", "toctou", "business_logic"],
            estimated_time="40m",
            bounty_potential="high"
        ),

        "recon_sniper": AttackChain(
            name="Recon Sniper",
            description="Targeted reconnaissance for high-value assets",
            steps=[
                {"tool": "subfinder", "action": "enumerate_subdomains", "params": {}},
                {"tool": "shodan", "action": "search_exposed_services", "params": {}},
                {"tool": "masscan", "action": "scan_critical_ports", "params": {"ports": "22,80,443,3306,5432,6379,9200"}},
                {"tool": "trufflehog", "action": "scan_leaked_secrets", "params": {}},
                {"tool": "pentagi", "action": "prioritize_targets", "params": {"by_bounty_potential": True}},
            ],
            target_categories=["info_disclosure", "exposed_services", "weak_credentials"],
            estimated_time="20m",
            bounty_potential="variable"
        )
    }

    @classmethod
    def get_chain(cls, name: str) -> AttackChain:
        return cls.CHAINS.get(name)

    @classmethod
    def get_chains_by_category(cls, category: str) -> List[AttackChain]:
        return [chain for chain in cls.CHAINS.values() if category in chain.target_categories]

    @classmethod
    def get_recommended_chains(cls, bbp_mode: str = "public_bbp") -> List[str]:
        """Get attack chains recommended for BBP mode."""
        recommendations = {
            "public_bbp": ["idor_gold_rush", "xss_blitz", "recon_sniper", "race_condition_blitz"],
            "private_contract": ["sqli_deep_dive", "ssrf_rce_hunter", "idor_gold_rush", "race_condition_blitz"],
            "enterprise_audit": ["ssrf_rce_hunter", "sqli_deep_dive", "recon_sniper"]
        }
        return recommendations.get(bbp_mode, recommendations["public_bbp"])

if __name__ == '__main__':
    import json
    chains = PentAGIBBPChains.get_recommended_chains("public_bbp")
    print(json.dumps({"recommended_chains": chains}, indent=2))
