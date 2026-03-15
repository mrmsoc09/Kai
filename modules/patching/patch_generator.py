"""LLM-based patch suggestion engine."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class PatchGenerator:
    """Generate patch suggestions for vulnerabilities."""

    # Vulnerability type to remediation templates
    REMEDIATION_TEMPLATES = {
        "sql_injection": {
            "type": "code",
            "description": "Use parameterized queries to prevent SQL injection",
            "code_examples": {
                "vulnerable": "query = f\"SELECT * FROM users WHERE id = {user_id}\"",
                "patched": "query = \"SELECT * FROM users WHERE id = %s\"\ncursor.execute(query, (user_id,))",
            },
            "steps": [
                "Replace string concatenation with parameterized queries",
                "Use prepared statements/parameterized queries in your ORM",
                "Add input validation as defense in depth",
                "Use stored procedures with parameters",
            ],
            "tools": ["SQLAlchemy ORM", "Prepared Statements", "Query Builders"],
        },
        "cross_site_scripting": {
            "type": "code",
            "description": "Sanitize and encode user input to prevent XSS attacks",
            "code_examples": {
                "vulnerable": "response = f\"<h1>{user_input}</h1>\"",
                "patched": "from html import escape\nresponse = f\"<h1>{escape(user_input)}</h1>\"",
            },
            "steps": [
                "Use templating engines with auto-escaping enabled",
                "HTML encode all user input in output",
                "Use CSP headers to restrict inline scripts",
                "Validate input on both client and server",
            ],
            "tools": ["Jinja2", "Django Templates", "html.escape", "bleach"],
            "headers": ["Content-Security-Policy: script-src 'self'"],
        },
        "remote_code_execution": {
            "type": "code",
            "description": "Remove or restrict code execution endpoints",
            "code_examples": {
                "vulnerable": "result = eval(user_code)",
                "patched": "# Use safe sandboxed execution or reject entirely\nraise SecurityError('Code execution not allowed')",
            },
            "steps": [
                "Remove eval(), exec(), and similar functions",
                "Use sandboxed execution environments if needed",
                "Disable dangerous functions/modules",
                "Use allowlist for allowed operations",
                "Implement strict input validation",
            ],
            "tools": ["Sandboxes", "Containers", "RestrictedPython"],
        },
        "authentication_bypass": {
            "type": "code",
            "description": "Implement proper authentication checks",
            "code_examples": {
                "vulnerable": "if request.user:\n    return user_data",
                "patched": "if request.user and request.user.is_authenticated:\n    if verify_session_token(request):\n        return user_data",
            },
            "steps": [
                "Implement multi-factor authentication (MFA)",
                "Use established authentication libraries (OAuth, OpenID)",
                "Add rate limiting on auth endpoints",
                "Implement proper session management",
                "Add account lockout after failed attempts",
            ],
            "tools": ["OAuth2", "OpenID Connect", "django-auth", "Flask-Login"],
        },
        "broken_access_control": {
            "type": "code",
            "description": "Implement proper authorization checks",
            "code_examples": {
                "vulnerable": "return get_resource(resource_id)",
                "patched": "if not user.has_permission('read', resource_id):\n    raise PermissionDenied()\nreturn get_resource(resource_id)",
            },
            "steps": [
                "Check authorization before every resource access",
                "Use role-based access control (RBAC)",
                "Use attribute-based access control (ABAC) for complex policies",
                "Verify ownership of resources",
                "Implement proper audit logging",
            ],
            "tools": ["django-guardian", "python-casbin", "Authzed"],
        },
        "directory_traversal": {
            "type": "code",
            "description": "Validate file paths to prevent directory traversal",
            "code_examples": {
                "vulnerable": "file_path = os.path.join(base_dir, user_path)\nwith open(file_path) as f:",
                "patched": "safe_path = os.path.normpath(os.path.join(base_dir, user_path))\nif not safe_path.startswith(base_dir):\n    raise ValueError('Path traversal attempt')\nwith open(safe_path) as f:",
            },
            "steps": [
                "Use os.path.normpath() to normalize paths",
                "Verify resolved path is within allowed directory",
                "Use allowlists for file access",
                "Disable directory listing",
                "Use file name mappings instead of direct paths",
            ],
            "tools": ["pathlib.Path", "os.path.realpath", "secure_filename"],
        },
        "information_disclosure": {
            "type": "config",
            "description": "Disable debug mode and error details in production",
            "steps": [
                "Disable debug mode in production (DEBUG=False)",
                "Remove sensitive information from error messages",
                "Implement proper logging without leaking data",
                "Hide framework versions in headers",
                "Remove default endpoints and admin panels",
            ],
            "configuration": {
                "before": "DEBUG = True\nDEBUG_PROPAGATE_EXCEPTIONS = True",
                "after": "DEBUG = False\nDEBUG_PROPAGATE_EXCEPTIONS = False",
            },
            "headers": [
                "Server: (custom/hidden)",
                "X-AspNet-Version: (removed)",
                "X-Powered-By: (removed)",
            ],
        },
        "insecure_deserialization": {
            "type": "code",
            "description": "Use safe serialization formats and validators",
            "code_examples": {
                "vulnerable": "data = pickle.loads(user_data)",
                "patched": "import json\ndata = json.loads(user_data)",
            },
            "steps": [
                "Avoid pickle, YAML, etc. for untrusted data",
                "Use JSON or other safe formats",
                "Validate schema before processing",
                "Use type checking and validators",
                "Implement allowlists for classes to deserialize",
            ],
            "tools": ["json", "pydantic", "marshmallow"],
        },
        "xml_external_entity": {
            "type": "code",
            "description": "Disable XML external entity processing",
            "code_examples": {
                "vulnerable": "tree = ET.parse(user_xml)",
                "patched": "parser = ET.XMLParser()\nparser.entity = {}\ntree = ET.parse(user_xml, parser)",
            },
            "steps": [
                "Disable external entity processing",
                "Disable DTD processing",
                "Use safe XML parsers",
                "Validate XML schema",
                "Use allowlists for XML features",
            ],
            "tools": ["lxml", "defusedxml"],
        },
        "default": {
            "type": "code",
            "description": "Review and remediate the vulnerability",
            "steps": [
                "Review the vulnerability details carefully",
                "Research known mitigations for this vulnerability type",
                "Implement appropriate security controls",
                "Test the patch thoroughly",
                "Document the changes",
            ],
        },
    }

    def __init__(self):
        """Initialize patch generator."""
        self.generated_patches: Dict[str, Dict[str, Any]] = {}

    def generate_patch(
        self,
        finding: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate patch suggestion for a finding.

        Returns:
            {
                'finding_id': str,
                'vulnerability_type': str,
                'patch_type': 'code'|'config'|'infrastructure'|'policy',
                'description': str,
                'remediation_steps': [str],
                'code_examples': {vulnerable: str, patched: str},
                'tools': [str],
                'headers': [str],
                'configuration': {before: str, after: str},
                'severity': str,
                'complexity': 'easy'|'medium'|'hard',
                'estimated_time_hours': int,
                'generated_at': ISO string,
            }
        """
        if context is None:
            context = {}

        vuln_type = finding.get("vulnerability_type", "default").lower()

        # Get template for this vulnerability type
        template = self.REMEDIATION_TEMPLATES.get(
            vuln_type,
            self.REMEDIATION_TEMPLATES["default"],
        )

        patch = {
            "finding_id": finding.get("id", "unknown"),
            "vulnerability_type": vuln_type,
            "patch_type": template.get("type", "code"),
            "description": template.get("description", "Review and remediate"),
            "remediation_steps": template.get("steps", []),
            "severity": finding.get("severity", "medium"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Add optional fields if present in template
        if "code_examples" in template:
            patch["code_examples"] = template["code_examples"]
        if "tools" in template:
            patch["tools"] = template["tools"]
        if "headers" in template:
            patch["headers"] = template["headers"]
        if "configuration" in template:
            patch["configuration"] = template["configuration"]

        # Estimate complexity and time
        patch["complexity"] = self._estimate_complexity(vuln_type)
        patch["estimated_time_hours"] = self._estimate_time(patch["complexity"])

        self.generated_patches[finding.get("id", "unknown")] = patch
        return patch

    def generate_batch_patches(
        self,
        findings: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate patches for multiple findings."""
        return [self.generate_patch(f, context) for f in findings]

    def prioritize_patches(
        self,
        patches: List[Dict[str, Any]],
        strategy: str = "impact",
    ) -> List[Dict[str, Any]]:
        """
        Prioritize patches by different strategies.

        Strategies:
        - impact: By severity (CRITICAL first)
        - effort: By complexity (easy first)
        - roi: Impact/effort ratio
        - time: By estimated time to fix
        """
        if strategy == "impact":
            severity_order = {
                "critical": 5,
                "high": 4,
                "medium": 3,
                "low": 2,
                "info": 1,
            }
            sorted_patches = sorted(
                patches,
                key=lambda x: severity_order.get(x.get("severity", "low"), 0),
                reverse=True,
            )

        elif strategy == "effort":
            effort_order = {"easy": 1, "medium": 2, "hard": 3}
            sorted_patches = sorted(
                patches,
                key=lambda x: effort_order.get(x.get("complexity", "medium"), 2),
            )

        elif strategy == "roi":
            # High impact, low effort first
            sorted_patches = sorted(
                patches,
                key=lambda x: (
                    -{"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}.get(
                        x.get("severity", "low"), 0
                    )
                )
                / {"easy": 1, "medium": 2, "hard": 3}.get(x.get("complexity", "medium"), 2),
            )

        elif strategy == "time":
            sorted_patches = sorted(
                patches,
                key=lambda x: x.get("estimated_time_hours", 8),
            )

        else:
            sorted_patches = patches

        return sorted_patches

    def get_patch_by_id(self, finding_id: str) -> Optional[Dict[str, Any]]:
        """Get generated patch by finding ID."""
        return self.generated_patches.get(finding_id)

    def estimate_patch_impact(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate impact of applying patch."""
        severity = patch.get("severity", "medium")
        complexity = patch.get("complexity", "medium")

        severity_impact = {
            "critical": 0.95,
            "high": 0.85,
            "medium": 0.70,
            "low": 0.50,
            "info": 0.20,
        }

        complexity_risk = {"easy": 0.05, "medium": 0.15, "hard": 0.30}

        risk_score = complexity_risk.get(complexity, 0.15)
        impact_score = severity_impact.get(severity, 0.50)
        confidence_score = 1.0 - risk_score

        return {
            "risk_score": risk_score,
            "impact_score": impact_score,
            "confidence_score": confidence_score,
            "net_benefit": impact_score * confidence_score - risk_score,
        }

    def _estimate_complexity(self, vuln_type: str) -> str:
        """Estimate patch complexity."""
        complexity_map = {
            "information_disclosure": "easy",
            "directory_traversal": "easy",
            "cross_site_scripting": "medium",
            "sql_injection": "medium",
            "broken_access_control": "medium",
            "authentication_bypass": "hard",
            "remote_code_execution": "hard",
            "insecure_deserialization": "hard",
            "xml_external_entity": "medium",
        }
        return complexity_map.get(vuln_type, "medium")

    def _estimate_time(self, complexity: str) -> int:
        """Estimate hours needed to patch."""
        time_map = {"easy": 1, "medium": 4, "hard": 8}
        return time_map.get(complexity, 4)

    def get_patch_stats(self) -> Dict[str, Any]:
        """Get statistics on generated patches."""
        if not self.generated_patches:
            return {
                "total_patches": 0,
                "by_complexity": {},
                "by_severity": {},
            }

        complexities = {}
        severities = {}
        total_time = 0

        for patch in self.generated_patches.values():
            complexity = patch.get("complexity", "medium")
            severity = patch.get("severity", "medium")

            complexities[complexity] = complexities.get(complexity, 0) + 1
            severities[severity] = severities.get(severity, 0) + 1
            total_time += patch.get("estimated_time_hours", 0)

        return {
            "total_patches": len(self.generated_patches),
            "by_complexity": complexities,
            "by_severity": severities,
            "total_estimated_hours": total_time,
            "average_hours_per_patch": (
                total_time / len(self.generated_patches)
                if self.generated_patches
                else 0
            ),
        }
