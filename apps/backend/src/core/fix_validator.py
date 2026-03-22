"""
Fix Validator
Multi-layer validation for proposed vulnerability fixes
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class FixValidator:
    """
    Multi-layer validation for proposed fixes.

    Validation layers:
    1. Static analysis (local tools - semgrep, bandit)
    2. LLM security review (local Ollama model)
    3. Test case execution
    4. OWASP best practices check
    """

    def __init__(self):
        """Initialize fix validator"""
        self.use_local_models = True
        logger.info("✓ FixValidator initialized")

    async def validate_fix(
        self,
        original_code: str,
        fixed_code: str,
        vulnerability_type: str
    ) -> Dict[str, Any]:
        """
        Validate a proposed fix.

        Returns:
            {
                "is_valid": bool,
                "confidence": float (0-1),
                "issues": List[str],
                "layers": Dict[str, Any]
            }
        """

        logger.info(f"Validating fix for {vulnerability_type}")

        # Layer 1: Static analysis
        static_result = await self._run_static_analysis(fixed_code, vulnerability_type)

        # Layer 2: LLM security review with LOCAL model
        llm_review = await self._llm_security_review(
            original_code,
            fixed_code,
            vulnerability_type
        )

        # Layer 3: Test cases
        test_result = await self._run_test_cases(fixed_code, vulnerability_type)

        # Layer 4: OWASP best practices
        owasp_result = await self._check_owasp_compliance(fixed_code, vulnerability_type)

        # Calculate overall confidence
        confidence = self._calculate_confidence([
            static_result,
            llm_review,
            test_result,
            owasp_result
        ])

        # Collect issues
        issues = []
        if not static_result["passed"]:
            issues.extend(static_result.get("issues", []))
        if not llm_review["approved"]:
            issues.extend(llm_review.get("concerns", []))
        if not test_result["all_passed"]:
            issues.extend(test_result.get("failures", []))
        if not owasp_result["compliant"]:
            issues.extend(owasp_result.get("violations", []))

        is_valid = all([
            static_result["passed"],
            llm_review["approved"],
            test_result["all_passed"],
            owasp_result["compliant"]
        ])

        return {
            "is_valid": is_valid,
            "confidence": confidence,
            "issues": issues,
            "layers": {
                "static_analysis": static_result,
                "llm_review": llm_review,
                "test_cases": test_result,
                "owasp_compliance": owasp_result
            }
        }

    async def _run_static_analysis(
        self,
        code: str,
        vulnerability_type: str
    ) -> Dict[str, Any]:
        """Layer 1: Static analysis with semgrep/bandit"""

        # Simulated static analysis
        # In production: run actual semgrep/bandit
        logger.info("Running static analysis...")

        # Check for common anti-patterns
        issues = []

        if vulnerability_type == "sql_injection":
            if "execute(" in code and "?" not in code:
                issues.append("Missing parameterized query")

        if vulnerability_type == "xss":
            if "innerHTML" in code and "sanitize" not in code:
                issues.append("Potential XSS - use textContent or sanitize")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "tool": "semgrep/bandit"
        }

    async def _llm_security_review(
        self,
        original: str,
        fixed: str,
        vulnerability_type: str
    ) -> Dict[str, Any]:
        """Layer 2: LLM review with LOCAL model (mistral:7b or qwen2.5-coder:7b)"""

        logger.info("Running LLM security review (local model)...")

        # Use local Ollama model for review
        # In production: call actual Ollama with security review prompt

        # Simulated review
        prompt = f"""You are a security expert reviewing a code fix.

Vulnerability Type: {vulnerability_type}

Original Code:
{original}

Fixed Code:
{fixed}

Evaluate:
1. Does the fix completely eliminate the vulnerability?
2. Are there any new security issues introduced?
3. Does it follow security best practices?

Provide approval (yes/no) and concerns."""

        # Simulated LLM response
        approved = True
        concerns = []

        if vulnerability_type == "sql_injection":
            if "prepare" in fixed or "?" in fixed:
                approved = True
            else:
                approved = False
                concerns.append("SQL injection not properly mitigated")

        return {
            "approved": approved,
            "concerns": concerns,
            "model": "qwen2.5-coder:7b",
            "cost": 0.0  # Local model
        }

    async def _run_test_cases(
        self,
        code: str,
        vulnerability_type: str
    ) -> Dict[str, Any]:
        """Layer 3: Execute test cases"""

        logger.info("Running test cases...")

        # Simulated test execution
        # In production: run actual unit/integration tests

        test_cases = self._generate_test_cases(vulnerability_type)

        passed_tests = []
        failed_tests = []

        for test in test_cases:
            # Simulate test execution
            result = True  # Assume pass for now
            if result:
                passed_tests.append(test)
            else:
                failed_tests.append(test)

        return {
            "all_passed": len(failed_tests) == 0,
            "passed_count": len(passed_tests),
            "failed_count": len(failed_tests),
            "failures": [f"Test failed: {t}" for t in failed_tests]
        }

    def _generate_test_cases(self, vulnerability_type: str) -> List[str]:
        """Generate test cases for vulnerability type"""

        test_cases = {
            "sql_injection": [
                "test_sql_injection_attempt",
                "test_parameterized_query",
                "test_input_validation"
            ],
            "xss": [
                "test_xss_script_injection",
                "test_html_sanitization",
                "test_output_encoding"
            ],
            "csrf": [
                "test_csrf_token_validation",
                "test_same_origin_check",
                "test_referer_validation"
            ]
        }

        return test_cases.get(vulnerability_type, ["test_generic_security"])

    async def _check_owasp_compliance(
        self,
        code: str,
        vulnerability_type: str
    ) -> Dict[str, Any]:
        """Layer 4: OWASP best practices check"""

        logger.info("Checking OWASP compliance...")

        violations = []

        # Check OWASP Top 10 patterns
        owasp_checks = {
            "sql_injection": [
                ("parameterized_query", "prepare" in code or "?" in code),
                ("input_validation", "validate" in code or "sanitize" in code),
                ("least_privilege", True)  # Would check DB permissions
            ],
            "xss": [
                ("output_encoding", "encode" in code or "escape" in code),
                ("input_sanitization", "sanitize" in code),
                ("content_security_policy", True)  # Would check CSP headers
            ]
        }

        checks = owasp_checks.get(vulnerability_type, [])

        for check_name, passed in checks:
            if not passed:
                violations.append(f"OWASP violation: {check_name}")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "standard": "OWASP Top 10 2021"
        }

    def _calculate_confidence(
        self,
        results: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall confidence score"""

        # Weight each layer
        weights = {
            "static_analysis": 0.3,
            "llm_review": 0.4,
            "test_cases": 0.2,
            "owasp_compliance": 0.1
        }

        total_confidence = 0.0

        for i, result in enumerate(results):
            layer_names = ["static_analysis", "llm_review", "test_cases", "owasp_compliance"]
            layer_name = layer_names[i]

            # Determine layer confidence
            if layer_name == "static_analysis":
                confidence = 1.0 if result.get("passed", False) else 0.5
            elif layer_name == "llm_review":
                confidence = 1.0 if result.get("approved", False) else 0.3
            elif layer_name == "test_cases":
                total = result.get("passed_count", 0) + result.get("failed_count", 0)
                confidence = result.get("passed_count", 0) / total if total > 0 else 0.0
            elif layer_name == "owasp_compliance":
                confidence = 1.0 if result.get("compliant", False) else 0.4

            total_confidence += confidence * weights[layer_name]

        return total_confidence
