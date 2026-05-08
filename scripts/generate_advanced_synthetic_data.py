"""Advanced Synthetic Data Generator for Kai Platform

Generates comprehensive synthetic data including vulnerability chains, zero-days,
knowledge graphs, exploitability validation patterns, and advanced scanning scenarios.
"""

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional


class AdvancedSyntheticDataGenerator:
    """Generates comprehensive synthetic data for agent training and platform initialization."""

    def __init__(self, output_dir: str = "/home/k1-admin/Kai/synthetic_data"):
        self.output_dir = Path(output_dir)
        self.vuln_chains = self._define_vuln_chains()
        self.zero_days = self._define_zero_days()
        self.cve_database = self._define_cve_database()
        self.exploitability_patterns = self._define_exploitability_patterns()
        self.scanning_scenarios = self._define_scanning_scenarios()
        self.knowledge_graph_templates = self._define_knowledge_graph_templates()

    def _define_vuln_chains(self) -> List[Dict[str, Any]]:
        """Define comprehensive vulnerability chains with detailed steps."""
        return [
            {
                "name": "Web Application RCE Chain",
                "severity": "CRITICAL",
                "cwe": "CWE-78",
                "steps": [
                    {"type": "recon", "desc": "Discover web application endpoints", "tools": ["gau", "waybackurls"]},
                    {"type": "fingerprint", "desc": "Identify framework and version", "tools": ["nuclei", "whatweb"]},
                    {"type": "scan", "desc": "Find command injection vulnerability", "tools": ["sqlmap", "nuclei"]},
                    {"type": "validate", "desc": "Confirm exploitability with PoC", "tools": ["burp", "custom_script"]},
                    {"type": "exploit", "desc": "Execute remote code execution", "tools": ["metasploit", "custom_exploit"]},
                    {"type": "escalate", "desc": "Gain system-level access", "tools": ["privilege_escalation_modules"]}
                ],
                "prerequisites": ["Web server accessible", "Input validation bypass"],
                "indicators": ["Error messages", "Unexpected output", "Command execution traces"]
            },
            {
                "name": "API Authentication Bypass Chain",
                "severity": "HIGH",
                "cwe": "CWE-287",
                "steps": [
                    {"type": "recon", "desc": "Map API endpoints and authentication flows", "tools": ["postman", "burp"]},
                    {"type": "test", "desc": "Test authentication mechanisms", "tools": ["jwt_tool", "auth_bypass_scripts"]},
                    {"type": "bypass", "desc": "Exploit weak JWT implementation", "tools": ["jwt_tool", "custom_jwt_attacks"]},
                    {"type": "access", "desc": "Access protected resources", "tools": ["api_testing_tools"]},
                    {"type": "exfiltrate", "desc": "Extract sensitive data", "tools": ["data_extraction_scripts"]}
                ],
                "prerequisites": ["JWT tokens in use", "Weak secret keys"],
                "indicators": ["Invalid token acceptance", "Access to unauthorized endpoints"]
            },
            {
                "name": "Database Injection to RCE Chain",
                "severity": "CRITICAL",
                "cwe": "CWE-89",
                "steps": [
                    {"type": "discover", "desc": "Find database-driven inputs", "tools": ["sqlmap", "burp"]},
                    {"type": "inject", "desc": "Test SQL injection payloads", "tools": ["sqlmap", "manual_testing"]},
                    {"type": "enumerate", "desc": "Extract database structure and data", "tools": ["sqlmap"]},
                    {"type": "escalate", "desc": "Write webshell to filesystem", "tools": ["sqlmap", "custom_payloads"]},
                    {"type": "execute", "desc": "Execute system commands via webshell", "tools": ["webshell_clients"]}
                ],
                "prerequisites": ["SQL injection vulnerability", "File write permissions"],
                "indicators": ["SQL errors", "Data extraction", "File creation"]
            },
            {
                "name": "Cloud Misconfiguration Chain",
                "severity": "HIGH",
                "cwe": "CWE-284",
                "steps": [
                    {"type": "recon", "desc": "Enumerate cloud resources", "tools": ["cloud_enum", "dnsdumpster"]},
                    {"type": "scan", "desc": "Check for exposed services", "tools": ["masscan", "shodan"]},
                    {"type": "test", "desc": "Test misconfigured permissions", "tools": ["awscli", "az_cli"]},
                    {"type": "exploit", "desc": "Access sensitive data or resources", "tools": ["cloud_exploit_tools"]},
                    {"type": "pivot", "desc": "Move laterally within cloud environment", "tools": ["cloud_pivot_tools"]}
                ],
                "prerequisites": ["Cloud resources exposed", "Weak IAM policies"],
                "indicators": ["Public S3 buckets", "Open cloud databases", "Weak permissions"]
            },
            {
                "name": "Supply Chain Attack Chain",
                "severity": "CRITICAL",
                "cwe": "CWE-829",
                "steps": [
                    {"type": "analyze", "desc": "Map software supply chain", "tools": ["dependency_checkers", "sbom_tools"]},
                    {"type": "identify", "desc": "Find vulnerable dependencies", "tools": ["owasp_dependency_check", "snyk"]},
                    {"type": "exploit", "desc": "Compromise build pipeline", "tools": ["malicious_packages", "build_poisoning"]},
                    {"type": "deploy", "desc": "Deploy backdoored software", "tools": ["automated_deployment"]},
                    {"type": "activate", "desc": "Trigger malicious functionality", "tools": ["c2_servers"]}
                ],
                "prerequisites": ["Third-party dependencies", "Weak CI/CD security"],
                "indicators": ["Unexpected network connections", "Modified binaries", "Anomalous behavior"]
            }
        ]

    def _define_zero_days(self) -> List[Dict[str, Any]]:
        """Define zero-day vulnerability scenarios with detailed analysis."""
        return [
            {
                "name": "Zero-Day RCE in Popular Framework",
                "description": "Remote code execution in widely-used web framework through deserialization",
                "severity": "CRITICAL",
                "cve_candidate": "CVE-2026-XXXX",
                "affected_software": ["Framework X v2.1-3.0"],
                "indicators": ["Unusual deserialization patterns", "Memory corruption traces", "Unexpected process spawning"],
                "exploit_complexity": "MEDIUM",
                "detection_difficulty": "HIGH",
                "validation_steps": [
                    "Check framework version",
                    "Test deserialization endpoints",
                    "Monitor for memory anomalies",
                    "Validate input sanitization"
                ],
                "mitigation": "Update framework, implement input validation, monitor deserialization"
            },
            {
                "name": "Zero-Day Authentication Bypass",
                "description": "Logic flaw in SSO implementation allowing account takeover",
                "severity": "HIGH",
                "cve_candidate": "CVE-2026-YYYY",
                "affected_software": ["SSO Provider Y"],
                "indicators": ["Multiple login attempts from same session", "Account access without proper auth"],
                "exploit_complexity": "LOW",
                "detection_difficulty": "MEDIUM",
                "validation_steps": [
                    "Review authentication flow logic",
                    "Test session handling",
                    "Check token validation",
                    "Monitor for anomalous access patterns"
                ],
                "mitigation": "Implement proper session validation, add rate limiting, enable MFA"
            },
            {
                "name": "Zero-Day Memory Corruption in Device Firmware",
                "description": "Heap overflow in IoT device firmware leading to RCE",
                "severity": "CRITICAL",
                "cve_candidate": "CVE-2026-ZZZZ",
                "affected_software": ["IoT Device Firmware v1.x"],
                "indicators": ["Device crashes", "Unusual network traffic", "Memory exhaustion"],
                "exploit_complexity": "HIGH",
                "detection_difficulty": "HIGH",
                "validation_steps": [
                    "Firmware version analysis",
                    "Memory usage monitoring",
                    "Network traffic analysis",
                    "Crash dump examination"
                ],
                "mitigation": "Firmware update, network segmentation, anomaly detection"
            }
        ]

    def _define_cve_database(self) -> List[Dict[str, Any]]:
        """Define comprehensive CVE database for training."""
        return [
            {
                "cve_id": "CVE-2023-12345",
                "description": "SQL injection in login form",
                "severity": "HIGH",
                "cvss_score": 8.5,
                "cwe": "CWE-89",
                "affected_products": ["WebApp v1.0-2.1"],
                "exploitability": "EASY",
                "validation_patterns": [
                    "Test with SQL payloads",
                    "Check for error-based injection",
                    "Verify data extraction possible"
                ],
                "remediation": "Use prepared statements, input validation"
            },
            {
                "cve_id": "CVE-2023-23456",
                "description": "Buffer overflow in network service",
                "severity": "CRITICAL",
                "cvss_score": 9.8,
                "cwe": "CWE-119",
                "affected_products": ["NetworkService v3.0"],
                "exploitability": "MODERATE",
                "validation_patterns": [
                    "Send oversized packets",
                    "Monitor for crashes",
                    "Check memory corruption"
                ],
                "remediation": "Bounds checking, safe functions"
            },
            {
                "cve_id": "CVE-2023-34567",
                "description": "XSS in user profile page",
                "severity": "MEDIUM",
                "cvss_score": 6.1,
                "cwe": "CWE-79",
                "affected_products": ["CMS v2.0-3.1"],
                "exploitability": "EASY",
                "validation_patterns": [
                    "Inject script tags",
                    "Test attribute injection",
                    "Verify cookie theft possible"
                ],
                "remediation": "Output encoding, CSP headers"
            }
        ]

    def _define_exploitability_patterns(self) -> List[Dict[str, Any]]:
        """Define patterns for validating vulnerability exploitability."""
        return [
            {
                "pattern_name": "SQL_Injection_Validation",
                "description": "Validate SQL injection vulnerabilities",
                "validation_steps": [
                    {"step": "Error-based testing", "indicators": ["SQL syntax errors", "database errors"]},
                    {"step": "Union-based testing", "indicators": ["Column count determination", "data extraction"]},
                    {"step": "Time-based testing", "indicators": ["Response delays", "timing attacks"]},
                    {"step": "Boolean-based testing", "indicators": ["True/false responses", "conditional logic"]}
                ],
                "success_criteria": ["Data extraction possible", "Database structure readable", "System commands executable"],
                "false_positive_indicators": ["WAF blocks", "Input sanitization", "Parameterized queries"]
            },
            {
                "pattern_name": "XSS_Validation",
                "description": "Validate cross-site scripting vulnerabilities",
                "validation_steps": [
                    {"step": "Reflected XSS testing", "indicators": ["Script execution in response", "Cookie theft"]},
                    {"step": "Stored XSS testing", "indicators": ["Persistent script storage", "User impact"]},
                    {"step": "DOM-based testing", "indicators": ["Client-side execution", "DOM manipulation"]}
                ],
                "success_criteria": ["Script execution confirmed", "Data theft possible", "User interaction exploitable"],
                "false_positive_indicators": ["CSP blocks", "Input encoding", "XSS filters"]
            },
            {
                "pattern_name": "RCE_Validation",
                "description": "Validate remote code execution vulnerabilities",
                "validation_steps": [
                    {"step": "Command injection testing", "indicators": ["Command output in response", "System commands executed"]},
                    {"step": "Deserialization testing", "indicators": ["Object instantiation", "Code execution"]},
                    {"step": "Template injection testing", "indicators": ["Template parsing", "Code evaluation"]}
                ],
                "success_criteria": ["Arbitrary commands executed", "System access gained", "Data manipulation possible"],
                "false_positive_indicators": ["Sandboxing", "Command restrictions", "Input validation"]
            }
        ]

    def _define_scanning_scenarios(self) -> List[Dict[str, Any]]:
        """Define comprehensive scanning scenarios for training."""
        return [
            {
                "scenario_name": "Web_Application_Full_Scan",
                "description": "Complete web application vulnerability assessment",
                "target_type": "web_application",
                "phases": [
                    {
                        "phase": "reconnaissance",
                        "tools": ["subfinder", "assetfinder", "amass", "gau"],
                        "expected_findings": ["subdomains", "endpoints", "parameters"],
                        "success_metrics": ["Coverage > 80%", "False positive < 5%"]
                    },
                    {
                        "phase": "fingerprinting",
                        "tools": ["whatweb", "wappalyzer", "nuclei"],
                        "expected_findings": ["technologies", "versions", "frameworks"],
                        "success_metrics": ["Accuracy > 90%", "Detection rate > 85%"]
                    },
                    {
                        "phase": "vulnerability_scanning",
                        "tools": ["nuclei", "nikto", "owasp_zap"],
                        "expected_findings": ["sql_injection", "xss", "rce", "auth_bypass"],
                        "success_metrics": ["True positive > 80%", "False positive < 10%"]
                    },
                    {
                        "phase": "exploitation",
                        "tools": ["sqlmap", "metasploit", "burp_suite"],
                        "expected_findings": ["confirmed_vulnerabilities", "data_exfiltration", "system_access"],
                        "success_metrics": ["Exploit success > 70%", "Data extraction confirmed"]
                    }
                ]
            },
            {
                "scenario_name": "API_Security_Scan",
                "description": "Comprehensive API security assessment",
                "target_type": "api",
                "phases": [
                    {
                        "phase": "discovery",
                        "tools": ["postman", "burp_discover", "swagger_parser"],
                        "expected_findings": ["endpoints", "methods", "parameters"],
                        "success_metrics": ["API coverage > 90%", "Documentation accuracy > 80%"]
                    },
                    {
                        "phase": "authentication_testing",
                        "tools": ["jwt_tool", "oauth_test", "auth_bypass"],
                        "expected_findings": ["weak_auth", "token_manipulation", "session_flaws"],
                        "success_metrics": ["Auth bypass detection > 85%", "False positive < 5%"]
                    },
                    {
                        "phase": "authorization_testing",
                        "tools": ["horizontal_privesc", "vertical_privesc", "idor_test"],
                        "expected_findings": ["access_control_flaws", "privilege_escalation", "data_leaks"],
                        "success_metrics": ["AuthZ flaw detection > 80%", "Impact assessment accurate"]
                    }
                ]
            },
            {
                "scenario_name": "Network_Infrastructure_Scan",
                "description": "Network infrastructure vulnerability assessment",
                "target_type": "network",
                "phases": [
                    {
                        "phase": "port_scanning",
                        "tools": ["masscan", "nmap", "rustscan"],
                        "expected_findings": ["open_ports", "services", "versions"],
                        "success_metrics": ["Port discovery > 95%", "Service detection > 85%"]
                    },
                    {
                        "phase": "service_enumeration",
                        "tools": ["nmap_scripts", "banner_grabbing", "service_scanners"],
                        "expected_findings": ["service_versions", "configurations", "vulnerabilities"],
                        "success_metrics": ["Version accuracy > 90%", "Config detection > 75%"]
                    },
                    {
                        "phase": "vulnerability_assessment",
                        "tools": ["openvas", "nessus", "custom_scanners"],
                        "expected_findings": ["service_vulns", "misconfigurations", "weak_protocols"],
                        "success_metrics": ["Vuln detection > 80%", "False positive < 15%"]
                    }
                ]
            }
        ]

    def _define_knowledge_graph_templates(self) -> List[Dict[str, Any]]:
        """Define knowledge graph templates for vulnerability relationships."""
        return [
            {
                "graph_name": "Vulnerability_Relationships",
                "description": "Relationships between vulnerabilities, exploits, and mitigations",
                "nodes": [
                    {"type": "vulnerability", "properties": ["cve_id", "cwe", "severity", "cvss_score"]},
                    {"type": "exploit", "properties": ["exploit_id", "complexity", "reliability"]},
                    {"type": "mitigation", "properties": ["technique", "effectiveness", "implementation_cost"]},
                    {"type": "tool", "properties": ["name", "category", "effectiveness"]},
                    {"type": "technique", "properties": ["name", "category", "success_rate"]}
                ],
                "relationships": [
                    {"type": "EXPLOITS", "from": "exploit", "to": "vulnerability", "properties": ["success_rate", "conditions"]},
                    {"type": "MITIGATES", "from": "mitigation", "to": "vulnerability", "properties": ["coverage", "residual_risk"]},
                    {"type": "DETECTS", "from": "tool", "to": "vulnerability", "properties": ["accuracy", "false_positive_rate"]},
                    {"type": "USES", "from": "technique", "to": "exploit", "properties": ["frequency", "effectiveness"]}
                ]
            },
            {
                "graph_name": "Attack_Chains",
                "description": "Multi-step attack chains and their dependencies",
                "nodes": [
                    {"type": "attack_step", "properties": ["name", "category", "complexity"]},
                    {"type": "prerequisite", "properties": ["condition", "probability"]},
                    {"type": "indicator", "properties": ["type", "reliability", "false_positive_rate"]},
                    {"type": "impact", "properties": ["type", "severity", "scope"]}
                ],
                "relationships": [
                    {"type": "DEPENDS_ON", "from": "attack_step", "to": "prerequisite", "properties": ["requirement_type"]},
                    {"type": "INDICATES", "from": "indicator", "to": "attack_step", "properties": ["confidence", "context"]},
                    {"type": "CAUSES", "from": "attack_step", "to": "impact", "properties": ["probability", "severity"]},
                    {"type": "ENABLES", "from": "attack_step", "to": "attack_step", "properties": ["success_probability"]}
                ]
            },
            {
                "graph_name": "Exploitability_Validation",
                "description": "Validation patterns for determining exploitability",
                "nodes": [
                    {"type": "validation_pattern", "properties": ["name", "category", "reliability"]},
                    {"type": "test_case", "properties": ["input", "expected_output", "success_criteria"]},
                    {"type": "indicator", "properties": ["type", "strength", "context"]},
                    {"type": "false_positive", "properties": ["pattern", "frequency", "mitigation"]}
                ],
                "relationships": [
                    {"type": "CONTAINS", "from": "validation_pattern", "to": "test_case", "properties": ["priority", "sequence"]},
                    {"type": "DETECTS", "from": "validation_pattern", "to": "indicator", "properties": ["confidence", "conditions"]},
                    {"type": "CAUSES", "from": "false_positive", "to": "validation_pattern", "properties": ["frequency", "impact"]}
                ]
            }
        ]

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

    def generate_cve_database_entries(self, count: int = 50) -> List[Dict[str, Any]]:
        """Generate comprehensive CVE database entries."""
        entries = []
        for i in range(count):
            base_cve = random.choice(self.cve_database)
            entry = {
                "cve_id": f"CVE-202{random.randint(3,6)}-{random.randint(10000,99999)}",
                "description": base_cve["description"],
                "severity": base_cve["severity"],
                "cvss_score": base_cve["cvss_score"] + random.uniform(-1.0, 1.0),
                "cvss_vector": f"CVSS:3.1/AV:{random.choice(['N','A','L','P'])}/AC:{random.choice(['L','H'])}/PR:{random.choice(['N','L','H'])}/UI:{random.choice(['N','R'])}/S:{random.choice(['U','C'])}/C:{random.choice(['H','L','N'])}/I:{random.choice(['H','L','N'])}/A:{random.choice(['H','L','N'])}",
                "cwe": base_cve["cwe"],
                "affected_products": base_cve["affected_products"],
                "published_date": f"202{random.randint(0,3)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                "last_modified": f"202{random.randint(0,3)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                "exploitability": base_cve["exploitability"],
                "validation_patterns": base_cve["validation_patterns"],
                "remediation": base_cve["remediation"],
                "references": [
                    f"https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-202{random.randint(3,6)}-{random.randint(10000,99999)}",
                    f"https://nvd.nist.gov/vuln/detail/CVE-202{random.randint(3,6)}-{random.randint(10000,99999)}"
                ],
                "tags": random.sample([
                    "remote-code-execution", "sql-injection", "xss", "buffer-overflow",
                    "authentication-bypass", "privilege-escalation", "data-leak",
                    "denial-of-service", "csrf", "directory-traversal"
                ], random.randint(1, 3))
            }
            entries.append(entry)
        return entries

    def generate_exploitability_validation_scenarios(self, count: int = 30) -> List[Dict[str, Any]]:
        """Generate scenarios for validating vulnerability exploitability."""
        scenarios = []
        for i in range(count):
            pattern = random.choice(self.exploitability_patterns)
            vuln_type = pattern["pattern_name"].replace("_Validation", "").lower()

            scenario = {
                "scenario_id": f"exploit-val-{i:04d}",
                "vulnerability_type": vuln_type,
                "pattern_name": pattern["pattern_name"],
                "description": pattern["description"],
                "target_url": f"https://vulnerable{random.randint(1,100)}.example.com/{random.choice(['login', 'search', 'api', 'upload', 'profile'])}",
                "validation_steps": pattern["validation_steps"],
                "success_criteria": pattern["success_criteria"],
                "false_positive_indicators": pattern["false_positive_indicators"],
                "test_payloads": self._generate_test_payloads(vuln_type),
                "expected_responses": self._generate_expected_responses(vuln_type),
                "validation_result": random.choice(["EXPLOITABLE", "NOT_EXPLOITABLE", "UNCERTAIN"]),
                "confidence_score": random.uniform(0.1, 1.0),
                "automated_validation_possible": random.choice([True, False]),
                "manual_verification_required": random.choice([True, False]),
                "environmental_factors": random.sample([
                    "WAF present", "Input sanitization", "Rate limiting", "Sandbox environment",
                    "Debug mode enabled", "Outdated software", "Weak configurations"
                ], random.randint(0, 3))
            }
            scenarios.append(scenario)
        return scenarios

    def generate_scanning_training_scenarios(self, count: int = 20) -> List[Dict[str, Any]]:
        """Generate comprehensive scanning training scenarios."""
        scenarios = []
        for i in range(count):
            base_scenario = random.choice(self.scanning_scenarios)

            scenario = {
                "scenario_id": f"scan-train-{i:04d}",
                "scenario_name": f"{base_scenario['scenario_name']}_{i+1}",
                "description": base_scenario["description"],
                "target_type": base_scenario["target_type"],
                "target_scope": self._generate_target_scope(base_scenario["target_type"]),
                "phases": base_scenario["phases"],
                "total_estimated_time": f"{random.randint(1, 8)}h",
                "required_resources": {
                    "cpu_cores": random.randint(2, 16),
                    "memory_gb": random.randint(4, 32),
                    "network_bandwidth": f"{random.randint(10, 100)}Mbps"
                },
                "expected_findings_count": random.randint(5, 50),
                "success_metrics": base_scenario["phases"][0]["success_metrics"],  # Simplified
                "risk_assessment": random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
                "compliance_requirements": random.sample([
                    "PCI-DSS", "HIPAA", "GDPR", "SOX", "NIST", "ISO27001"
                ], random.randint(0, 3)),
                "automated_tools": [tool for phase in base_scenario["phases"] for tool in phase["tools"]],
                "manual_testing_required": random.choice([True, False]),
                "reporting_requirements": random.choice([
                    "Executive summary only",
                    "Technical details included",
                    "Full vulnerability report",
                    "Compliance-focused report"
                ])
            }
            scenarios.append(scenario)
        return scenarios

    def generate_knowledge_graph_data(self, count: int = 100) -> Dict[str, Any]:
        """Generate knowledge graph data for training."""
        graph_data = {
            "nodes": [],
            "relationships": []
        }

        # Generate nodes
        node_types = ["vulnerability", "exploit", "mitigation", "tool", "technique", "indicator", "impact"]
        for i in range(count):
            node_type = random.choice(node_types)
            node = {
                "id": f"node-{i:04d}",
                "type": node_type,
                "properties": self._generate_node_properties(node_type)
            }
            graph_data["nodes"].append(node)

        # Generate relationships
        for i in range(count * 2):  # More relationships than nodes
            rel_types = ["EXPLOITS", "MITIGATES", "DETECTS", "USES", "INDICATES", "CAUSES", "DEPENDS_ON"]
            from_node = random.choice(graph_data["nodes"])
            to_node = random.choice([n for n in graph_data["nodes"] if n != from_node])

            relationship = {
                "id": f"rel-{i:04d}",
                "type": random.choice(rel_types),
                "from": from_node["id"],
                "to": to_node["id"],
                "properties": {
                    "confidence": random.uniform(0.1, 1.0),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            }
            graph_data["relationships"].append(relationship)

        return graph_data

    def generate_agent_training_data(self, count: int = 200) -> List[Dict[str, Any]]:
        """Generate comprehensive training data for AI agents."""
        training_data = []

        for i in range(count):
            scenario_type = random.choice([
                "vulnerability_analysis", "exploit_validation", "risk_assessment",
                "remediation_planning", "threat_hunting", "incident_response"
            ])

            if scenario_type == "vulnerability_analysis":
                data = self._generate_vuln_analysis_training()
            elif scenario_type == "exploit_validation":
                data = self._generate_exploit_validation_training()
            elif scenario_type == "risk_assessment":
                data = self._generate_risk_assessment_training()
            elif scenario_type == "remediation_planning":
                data = self._generate_remediation_training()
            elif scenario_type == "threat_hunting":
                data = self._generate_threat_hunting_training()
            else:  # incident_response
                data = self._generate_incident_response_training()

            training_data.append({
                "id": f"agent-train-{i:04d}",
                "scenario_type": scenario_type,
                "input": data["input"],
                "expected_output": data["output"],
                "context": data.get("context", {}),
                "difficulty": random.choice(["beginner", "intermediate", "advanced"]),
                "domain": random.choice(["web_security", "network_security", "cloud_security", "application_security"])
            })

        return training_data

    def _generate_test_payloads(self, vuln_type: str) -> List[str]:
        """Generate test payloads for different vulnerability types."""
        payloads = {
            "sql": [
                "' OR '1'='1",
                "'; DROP TABLE users; --",
                "' UNION SELECT username, password FROM users --",
                "' AND SLEEP(5) --"
            ],
            "xss": [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "javascript:alert('XSS')",
                "<svg onload=alert('XSS')>"
            ],
            "rce": [
                "; ls -la",
                "| cat /etc/passwd",
                "$(whoami)",
                "`id`"
            ]
        }
        return payloads.get(vuln_type, ["generic payload"])

    def _generate_expected_responses(self, vuln_type: str) -> List[str]:
        """Generate expected responses for different vulnerability types."""
        responses = {
            "sql": [
                "You have an error in your SQL syntax",
                "mysql_fetch_array()",
                "ORA-01756",
                "Microsoft OLE DB Provider for SQL Server"
            ],
            "xss": [
                "<script>alert('XSS')</script>",
                "Script execution detected",
                "XSS filter triggered"
            ],
            "rce": [
                "uid=0(root) gid=0(root)",
                "total 64",
                "Command executed successfully"
            ]
        }
        return responses.get(vuln_type, ["Expected response"])

    def _generate_target_scope(self, target_type: str) -> Dict[str, Any]:
        """Generate target scope based on type."""
        scopes = {
            "web_application": {
                "urls": [f"https://app{random.randint(1,10)}.example.com" for _ in range(random.randint(1, 5))],
                "subdomains": [f"api.app{random.randint(1,10)}.example.com" for _ in range(random.randint(0, 3))],
                "endpoints": [f"/api/v{random.randint(1,3)}/{random.choice(['users', 'posts', 'admin'])}" for _ in range(random.randint(5, 20))]
            },
            "api": {
                "base_url": f"https://api{random.randint(1,10)}.example.com",
                "endpoints": [f"/v{random.randint(1,3)}/{random.choice(['auth', 'data', 'admin'])}" for _ in range(random.randint(10, 30))],
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "auth_types": ["JWT", "OAuth2", "API Key", "Basic Auth"]
            },
            "network": {
                "ip_ranges": [f"192.168.{random.randint(1,10)}.0/24" for _ in range(random.randint(1, 3))],
                "ports": random.sample(range(1, 65535), random.randint(10, 50)),
                "services": ["HTTP", "HTTPS", "SSH", "FTP", "SMTP", "DNS"]
            }
        }
        return scopes.get(target_type, {})

    def _generate_node_properties(self, node_type: str) -> Dict[str, Any]:
        """Generate properties for knowledge graph nodes."""
        properties = {
            "vulnerability": {
                "cve_id": f"CVE-202{random.randint(3,6)}-{random.randint(10000,99999)}",
                "severity": random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
                "cvss_score": random.uniform(1.0, 10.0)
            },
            "exploit": {
                "exploit_id": f"exploit_{random.randint(1000,9999)}",
                "complexity": random.choice(["LOW", "MEDIUM", "HIGH"]),
                "reliability": random.uniform(0.1, 1.0)
            },
            "mitigation": {
                "technique": random.choice(["Input validation", "Access control", "Encryption", "Monitoring"]),
                "effectiveness": random.uniform(0.5, 1.0),
                "cost": random.choice(["LOW", "MEDIUM", "HIGH"])
            },
            "tool": {
                "name": random.choice(["Nuclei", "SQLMap", "Burp Suite", "Metasploit", "Nmap"]),
                "category": random.choice(["Scanner", "Exploiter", "Analyzer", "Monitor"]),
                "accuracy": random.uniform(0.7, 0.99)
            },
            "technique": {
                "name": random.choice(["SQL Injection", "XSS", "Buffer Overflow", "Auth Bypass"]),
                "category": random.choice(["Injection", "Logic", "Memory", "Crypto"]),
                "success_rate": random.uniform(0.1, 0.9)
            }
        }
        return properties.get(node_type, {})

    def _generate_vuln_analysis_training(self) -> Dict[str, Any]:
        """Generate vulnerability analysis training data."""
        vuln_types = ["SQL Injection", "XSS", "RCE", "Auth Bypass", "Buffer Overflow"]
        vuln_type = random.choice(vuln_types)

        return {
            "input": f"Analyze this vulnerability finding: {vuln_type} detected on endpoint /api/login. CVSS Score: {random.uniform(4.0, 9.0):.1f}. What is the risk level and recommended immediate actions?",
            "output": f"This is a {random.choice(['HIGH', 'CRITICAL'])} risk {vuln_type} vulnerability. Immediate actions: 1) Isolate affected endpoint, 2) Implement input validation, 3) Monitor for exploitation attempts, 4) Plan remediation within {random.randint(1,7)} days.",
            "context": {
                "endpoint": "/api/login",
                "method": "POST",
                "parameters": ["username", "password"],
                "detection_method": "automated_scan"
            }
        }

    def _generate_exploit_validation_training(self) -> Dict[str, Any]:
        """Generate exploit validation training data."""
        return {
            "input": f"Validate if this SQL injection is exploitable: Parameter 'id' in URL /user?id=1. Payload tested: ' OR 1=1 --. Response shows user data. Confirm exploitability and suggest next steps.",
            "output": f"The SQL injection appears exploitable - the payload successfully bypassed authentication and returned unauthorized data. Next steps: 1) Extract database structure, 2) Attempt privilege escalation, 3) Assess data sensitivity, 4) Document findings for remediation.",
            "context": {
                "payload": "' OR 1=1 --",
                "response_indicators": ["user_data_returned", "no_error_messages"],
                "database_type": "MySQL"
            }
        }

    def _generate_risk_assessment_training(self) -> Dict[str, Any]:
        """Generate risk assessment training data."""
        return {
            "input": f"Assess risk for: Multiple critical vulnerabilities found in production web application. Includes RCE (CVSS 9.8), SQL injection (CVSS 8.5), and weak authentication (CVSS 7.2). System handles payment data and serves 10k daily users.",
            "output": f"CRITICAL risk assessment. Business impact: High financial loss potential, regulatory compliance violations, reputational damage. Technical impact: Complete system compromise possible. Priority: Immediate remediation required. Recommend: 1) Emergency patching, 2) Traffic monitoring, 3) Incident response team activation.",
            "context": {
                "business_criticality": "HIGH",
                "data_classification": "PCI_DSS",
                "user_impact": "10,000_daily_users"
            }
        }

    def _generate_remediation_training(self) -> Dict[str, Any]:
        """Generate remediation planning training data."""
        return {
            "input": f"Create remediation plan for Apache Struts RCE vulnerability (CVE-2017-5638) affecting 50 web servers. Current version: 2.3.31. Business constraint: Zero downtime allowed.",
            "output": f"Remediation plan: 1) Patch to Struts 2.3.32+ (addresses CVE), 2) Implement WAF rules as temporary mitigation, 3) Schedule rolling updates during low-traffic windows, 4) Test patches in staging, 5) Monitor for exploitation attempts, 6) Validate fix effectiveness. Timeline: 2 weeks.",
            "context": {
                "vulnerability": "CVE-2017-5638",
                "affected_systems": 50,
                "downtime_constraint": "ZERO_ALLOWED"
            }
        }

    def _generate_threat_hunting_training(self) -> Dict[str, Any]:
        """Generate threat hunting training data."""
        return {
            "input": f"Investigate suspicious activity: Unusual outbound connections from web server to known C2 IP ranges. Connections started after recent phishing campaign. Server logs show encoded PowerShell commands.",
            "output": f"High-confidence compromise indicators detected. Investigation steps: 1) Isolate affected server, 2) Collect memory forensics, 3) Analyze PowerShell execution logs, 4) Check for lateral movement, 5) Review phishing campaign correlation, 6) Implement containment measures.",
            "context": {
                "indicators": ["C2_connections", "encoded_powershell", "phishing_correlation"],
                "severity": "HIGH",
                "timeline": "recent_phishing_campaign"
            }
        }

    def _generate_incident_response_training(self) -> Dict[str, Any]:
        """Generate incident response training data."""
        return {
            "input": f"Active breach detected: External attacker gained admin access via SQL injection. Database contains customer PII. Attacker active for 48 hours. Respond according to NIST framework.",
            "output": f"Execute incident response: IDENTIFY: Confirm breach scope and data exposure. PROTECT: Isolate compromised systems, revoke credentials. DETECT: Enhance monitoring. RESPOND: Notify affected customers, preserve evidence. RECOVER: Restore from clean backups, validate integrity.",
            "context": {
                "breach_type": "sql_injection_to_admin_access",
                "data_exposed": "customer_PII",
                "dwell_time": "48_hours"
            }
        }

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
        # Generate all data types
        chains = self.generate_vuln_chains()
        zero_days = self.generate_zero_day_scenarios()
        cve_entries = self.generate_cve_database_entries()
        exploit_scenarios = self.generate_exploitability_validation_scenarios()
        scanning_scenarios = self.generate_scanning_training_scenarios()
        knowledge_graph = self.generate_knowledge_graph_data()
        agent_training = self.generate_agent_training_data()

        # Save vulnerability chains
        chains_file = self.output_dir / "advanced" / "vuln_chains.json"
        chains_file.parent.mkdir(exist_ok=True, parents=True)
        with open(chains_file, "w") as f:
            json.dump(chains, f, indent=2)

        # Save zero-day scenarios
        zero_file = self.output_dir / "advanced" / "zero_days.json"
        with open(zero_file, "w") as f:
            json.dump(zero_days, f, indent=2)

        # Save CVE database
        cve_file = self.output_dir / "advanced" / "cve_database.json"
        with open(cve_file, "w") as f:
            json.dump(cve_entries, f, indent=2)

        # Save exploitability validation scenarios
        exploit_file = self.output_dir / "advanced" / "exploitability_scenarios.json"
        with open(exploit_file, "w") as f:
            json.dump(exploit_scenarios, f, indent=2)

        # Save scanning training scenarios
        scanning_file = self.output_dir / "advanced" / "scanning_scenarios.json"
        with open(scanning_file, "w") as f:
            json.dump(scanning_scenarios, f, indent=2)

        # Save knowledge graph data
        graph_file = self.output_dir / "advanced" / "knowledge_graph.json"
        with open(graph_file, "w") as f:
            json.dump(knowledge_graph, f, indent=2)

        # Save agent training data
        agent_file = self.output_dir / "training" / "agent_training.json"
        with open(agent_file, "w") as f:
            json.dump(agent_training, f, indent=2)

        # Generate and save legacy training prompts for backward compatibility
        prompts = self.generate_training_prompts(chains, zero_days)
        train_file = self.output_dir / "training" / "advanced_training.json"
        with open(train_file, "w") as f:
            json.dump(prompts, f, indent=2)

        return {
            "chains_file": str(chains_file),
            "zero_days_file": str(zero_file),
            "cve_database_file": str(cve_file),
            "exploitability_scenarios_file": str(exploit_file),
            "scanning_scenarios_file": str(scanning_file),
            "knowledge_graph_file": str(graph_file),
            "agent_training_file": str(agent_file),
            "legacy_training_file": str(train_file),
            "chains_count": len(chains),
            "zero_days_count": len(zero_days),
            "cve_entries_count": len(cve_entries),
            "exploit_scenarios_count": len(exploit_scenarios),
            "scanning_scenarios_count": len(scanning_scenarios),
            "knowledge_graph_nodes": len(knowledge_graph["nodes"]),
            "knowledge_graph_relationships": len(knowledge_graph["relationships"]),
            "agent_training_count": len(agent_training),
            "legacy_prompts_count": len(prompts)
        }


if __name__ == "__main__":
    generator = AdvancedSyntheticDataGenerator()
    results = generator.save_all()
    print(f"Generated advanced synthetic data: {results}")