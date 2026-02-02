"""Patch validation and applicability checking."""

from typing import Dict, Any, List, Optional, Tuple
import re


class PatchValidator:
    """Validate patches for correctness and applicability."""

    # Code pattern matchers for validation
    PATTERN_VALIDATORS = {
        "sql_injection": {
            "vulnerable_patterns": [
                r'f".*\{.*\}.*FROM',  # f-string with variable in FROM
                r'f".*\{.*\}.*WHERE',  # f-string in WHERE
                r'".*\+".*WHERE',  # String concatenation in WHERE
                r"query\s*=\s*['\"].*\+",  # Query concatenation
            ],
            "patched_patterns": [
                r"execute\(.*%s.*\)",  # Parameterized execution
                r"execute_async\(.*\?.*\)",  # Async parameterized
                r"query\.filter\(",  # ORM usage
                r"prepared_statement",  # Prepared statements
            ],
        },
        "cross_site_scripting": {
            "vulnerable_patterns": [
                r'{{.*\|safe',  # Jinja2 safe filter
                r"{{.*\|mark_safe",  # Django mark_safe
                r'innerHTML\s*=\s*',  # Direct innerHTML
                r"eval\(",  # eval() usage
            ],
            "patched_patterns": [
                r"{{.*}}",  # Auto-escaping (Jinja2/Django)
                r"html\.escape\(",  # HTML escaping
                r"bleach\.clean\(",  # Bleach sanitization
                r"Content-Security-Policy",  # CSP headers
            ],
        },
        "authentication_bypass": {
            "vulnerable_patterns": [
                r"if\s+request\.user:",  # Incomplete auth check
                r"if\s+is_authenticated:",  # Just checking auth
                r"skip_auth",  # Skip auth flag
                r"debug=True",  # Debug mode
            ],
            "patched_patterns": [
                r"@login_required",  # Decorator
                r"require_permission",  # Permission check
                r"@require_auth",  # Auth decorator
                r"verify_token",  # Token verification
            ],
        },
    }

    def __init__(self):
        """Initialize patch validator."""
        self.validation_results: Dict[str, Dict[str, Any]] = {}

    def validate_patch(
        self,
        patch: Dict[str, Any],
        code_context: Optional[str] = None,
        vulnerability_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate a patch suggestion.

        Checks:
        - Syntax correctness
        - Applicability to vulnerability type
        - Presence of common anti-patterns
        - Code quality
        """
        validation = {
            "patch_id": patch.get("finding_id", "unknown"),
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "confidence_score": 1.0,
        }

        # Check patch structure
        if not patch.get("remediation_steps"):
            validation["issues"].append("No remediation steps provided")
            validation["is_valid"] = False

        if not patch.get("description"):
            validation["issues"].append("No description provided")
            validation["is_valid"] = False

        # If code examples provided, validate syntax
        if "code_examples" in patch:
            code_validation = self._validate_code_examples(patch["code_examples"])
            if not code_validation["valid"]:
                validation["issues"].extend(code_validation["errors"])
                validation["is_valid"] = False
            else:
                validation["warnings"].extend(code_validation["warnings"])

        # Check against vulnerability type patterns
        vuln_type = vulnerability_type or patch.get("vulnerability_type", "")
        if code_context and vuln_type in self.PATTERN_VALIDATORS:
            pattern_validation = self._validate_patterns(
                code_context, vuln_type
            )
            validation["pattern_matches"] = pattern_validation

            if not pattern_validation["has_patches"]:
                validation["warnings"].append(
                    "Code may not contain vulnerable patterns - verify context"
                )
                validation["confidence_score"] *= 0.7

        # Estimate success probability
        issue_count = len(validation["issues"])
        if issue_count > 0:
            validation["confidence_score"] *= 0.5 ** issue_count

        validation["success_probability"] = validation["confidence_score"]

        self.validation_results[patch.get("finding_id", "unknown")] = validation
        return validation

    def validate_patch_applicability(
        self,
        patch: Dict[str, Any],
        codebase_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check if patch is applicable to the specific codebase.

        Considers:
        - Framework version compatibility
        - Language compatibility
        - Dependency requirements
        """
        applicability = {
            "patch_id": patch.get("finding_id", "unknown"),
            "is_applicable": True,
            "blockers": [],
            "warnings": [],
        }

        # Check language compatibility
        codebase_language = codebase_info.get("language", "").lower()
        patch_examples = patch.get("code_examples", {})

        if patch_examples:
            # Try to detect language from examples
            if "python" in str(patch_examples).lower() and codebase_language != "python":
                applicability["blockers"].append(
                    f"Patch is for Python, codebase is {codebase_language}"
                )
                applicability["is_applicable"] = False

        # Check framework compatibility
        patch_tools = patch.get("tools", [])
        codebase_frameworks = codebase_info.get("frameworks", [])

        compatible_tools = [t for t in patch_tools if t in codebase_frameworks]
        if not compatible_tools and patch_tools:
            applicability["warnings"].append(
                f"Recommended tools ({patch_tools}) not found in codebase"
            )

        # Check if patch requires tools not installed
        required_tools = patch.get("tools", [])
        installed_tools = codebase_info.get("installed_tools", [])

        missing_tools = [t for t in required_tools if t not in installed_tools]
        if missing_tools:
            applicability["warnings"].append(
                f"Patch requires: {missing_tools}"
            )

        applicability["is_applicable"] = len(applicability["blockers"]) == 0

        return applicability

    def validate_patch_compatibility(
        self,
        old_patch: Dict[str, Any],
        new_patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check if two patches can be applied together."""
        compatibility = {
            "patches": [
                old_patch.get("finding_id", "unknown"),
                new_patch.get("finding_id", "unknown"),
            ],
            "compatible": True,
            "conflicts": [],
            "warnings": [],
        }

        old_steps = old_patch.get("remediation_steps", [])
        new_steps = new_patch.get("remediation_steps", [])

        # Check for conflicting steps
        old_step_set = set(old_steps)
        new_step_set = set(new_steps)

        if old_step_set & new_step_set:
            compatibility["warnings"].append("Both patches include similar steps")

        # Check for library conflicts
        old_tools = set(old_patch.get("tools", []))
        new_tools = set(new_patch.get("tools", []))

        conflicting_tools = {
            ("sqlite3", "postgresql"),
            ("pip", "conda"),
            ("requests", "urllib"),
        }

        for tool1, tool2 in conflicting_tools:
            if tool1 in old_tools and tool2 in new_tools:
                compatibility["conflicts"].append(
                    f"Conflicting tools: {tool1} vs {tool2}"
                )
                compatibility["compatible"] = False

        return compatibility

    def _validate_code_examples(
        self, code_examples: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate code examples."""
        result = {"valid": True, "errors": [], "warnings": []}

        if "vulnerable" not in code_examples:
            result["warnings"].append("No vulnerable example provided")

        if "patched" not in code_examples:
            result["warnings"].append("No patched example provided")

        # Check Python syntax if present
        vulnerable = code_examples.get("vulnerable", "")
        patched = code_examples.get("patched", "")

        if vulnerable and self._is_python_code(vulnerable):
            if not self._check_python_syntax(vulnerable):
                result["errors"].append("Vulnerable example has Python syntax errors")
                result["valid"] = False

        if patched and self._is_python_code(patched):
            if not self._check_python_syntax(patched):
                result["errors"].append("Patched example has Python syntax errors")
                result["valid"] = False

        return result

    def _validate_patterns(
        self, code_context: str, vulnerability_type: str
    ) -> Dict[str, Any]:
        """Validate vulnerability patterns in code."""
        validators = self.PATTERN_VALIDATORS.get(vulnerability_type, {})
        result = {
            "vulnerable_matches": [],
            "patched_matches": [],
            "has_vulnerabilities": False,
            "has_patches": False,
        }

        vulnerable_patterns = validators.get("vulnerable_patterns", [])
        patched_patterns = validators.get("patched_patterns", [])

        for pattern in vulnerable_patterns:
            if re.search(pattern, code_context, re.IGNORECASE):
                result["vulnerable_matches"].append(pattern)
                result["has_vulnerabilities"] = True

        for pattern in patched_patterns:
            if re.search(pattern, code_context, re.IGNORECASE):
                result["patched_matches"].append(pattern)
                result["has_patches"] = True

        return result

    @staticmethod
    def _is_python_code(code: str) -> bool:
        """Detect if code is Python."""
        return any(
            keyword in code
            for keyword in ["import ", "def ", "class ", "import", "from "]
        )

    @staticmethod
    def _check_python_syntax(code: str) -> bool:
        """Check if Python code has valid syntax."""
        try:
            compile(code, "<string>", "exec")
            return True
        except SyntaxError:
            return False

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        if not self.validation_results:
            return {
                "total_validations": 0,
                "valid_patches": 0,
                "invalid_patches": 0,
            }

        valid_count = sum(
            1 for v in self.validation_results.values() if v.get("is_valid")
        )

        avg_confidence = (
            sum(v.get("confidence_score", 0) for v in self.validation_results.values())
            / len(self.validation_results)
            if self.validation_results
            else 0
        )

        return {
            "total_validations": len(self.validation_results),
            "valid_patches": valid_count,
            "invalid_patches": len(self.validation_results) - valid_count,
            "average_confidence": round(avg_confidence, 2),
        }
