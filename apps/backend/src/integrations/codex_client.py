"""
OpenAI Codex Client
Integration for code generation, PoC creation, and vulnerability fix generation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from apps.backend.src.core.secret_manager import get_secret_manager, SecretManagerError

logger = logging.getLogger(__name__)


class CodexTaskType(str, Enum):
    """Types of Codex tasks"""
    GENERATE_POC = "generate_poc"
    GENERATE_FIX = "generate_fix"
    GENERATE_CODE = "generate_code"
    COMPLETE_CODE = "complete_code"
    EXPLAIN_CODE = "explain_code"
    TRANSLATE_CODE = "translate_code"


@dataclass
class CodexResult:
    """Result from Codex task"""
    task_type: CodexTaskType
    success: bool
    generated_code: str
    explanation: Optional[str] = None
    test_cases: List[str] = field(default_factory=list)
    security_notes: List[str] = field(default_factory=list)
    error: Optional[str] = None
    model_used: str = "gpt-4"
    tokens_used: int = 0
    cost_cents: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CodexClient:
    """
    OpenAI Codex integration for PoC generation and code repair.

    Features:
    - Generate proof-of-concept exploit code
    - Generate secure fixes for vulnerabilities
    - Code generation from specifications
    - Code completion and translation
    - Security-focused code analysis
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 2000
    ):
        """Initialize Codex client"""
        if api_key:
            self.api_key = api_key
        else:
            try:
                self.api_key = get_secret_manager().get_required("OPENAI_API_KEY")
            except SecretManagerError:
                self.api_key = None
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.available = False

        if not self.api_key:
            logger.warning("OpenAI API key not found via secret manager.")
        else:
            self.available = True
            logger.info(f"✓ Codex client initialized with model: {model}")

        # Initialize OpenAI client
        try:
            import openai
            self.openai = openai
            if self.api_key:
                openai.api_key = self.api_key
        except ImportError:
            logger.error("OpenAI library not installed. Install with: pip install openai")
            self.available = False

    async def generate_poc(
        self,
        vulnerability_description: str,
        target_language: str,
        context: Optional[Dict[str, Any]] = None,
        ethical_mode: bool = True
    ) -> CodexResult:
        """
        Generate proof-of-concept exploit code.

        Args:
            vulnerability_description: Description of the vulnerability
            target_language: Programming language (python, javascript, bash, etc.)
            context: Additional context (target platform, libraries, etc.)
            ethical_mode: If True, adds disclaimer and remediation guidance

        Returns:
            CodexResult with PoC code and explanation
        """
        if not self.available:
            return CodexResult(
                task_type=CodexTaskType.GENERATE_POC,
                success=False,
                generated_code="",
                error="Codex client not available (missing API key or library)"
            )

        try:
            # Build prompt
            prompt = self._build_poc_prompt(
                vulnerability_description,
                target_language,
                context,
                ethical_mode
            )

            # Call OpenAI API
            response = await self._call_openai(prompt)

            # Parse response
            result = self._parse_poc_response(response, target_language, ethical_mode)

            return result

        except Exception as e:
            logger.error(f"Error generating PoC: {str(e)}")
            return CodexResult(
                task_type=CodexTaskType.GENERATE_POC,
                success=False,
                generated_code="",
                error=str(e)
            )

    async def generate_fix(
        self,
        vulnerable_code: str,
        vulnerability_type: str,
        language: str,
        context: Optional[Dict[str, Any]] = None
    ) -> CodexResult:
        """
        Generate secure fix for vulnerable code.

        Args:
            vulnerable_code: The code containing vulnerability
            vulnerability_type: Type of vulnerability (SQL injection, XSS, etc.)
            language: Programming language
            context: Additional context (framework, libraries, etc.)

        Returns:
            CodexResult with fixed code and explanation
        """
        if not self.available:
            return CodexResult(
                task_type=CodexTaskType.GENERATE_FIX,
                success=False,
                generated_code="",
                error="Codex client not available"
            )

        try:
            # Build prompt
            prompt = self._build_fix_prompt(
                vulnerable_code,
                vulnerability_type,
                language,
                context
            )

            # Call OpenAI API
            response = await self._call_openai(prompt)

            # Parse response
            result = self._parse_fix_response(response, language)

            return result

        except Exception as e:
            logger.error(f"Error generating fix: {str(e)}")
            return CodexResult(
                task_type=CodexTaskType.GENERATE_FIX,
                success=False,
                generated_code="",
                error=str(e)
            )

    async def generate_code(
        self,
        specification: str,
        language: str,
        include_tests: bool = True,
        include_docs: bool = True
    ) -> CodexResult:
        """Generate code from specification"""
        if not self.available:
            return CodexResult(
                task_type=CodexTaskType.GENERATE_CODE,
                success=False,
                generated_code="",
                error="Codex client not available"
            )

        try:
            prompt = self._build_generation_prompt(
                specification,
                language,
                include_tests,
                include_docs
            )

            response = await self._call_openai(prompt)
            result = self._parse_generation_response(response, language, include_tests)

            return result

        except Exception as e:
            logger.error(f"Error generating code: {str(e)}")
            return CodexResult(
                task_type=CodexTaskType.GENERATE_CODE,
                success=False,
                generated_code="",
                error=str(e)
            )

    async def complete_code(
        self,
        partial_code: str,
        language: str,
        completion_hint: Optional[str] = None
    ) -> CodexResult:
        """Complete partial code"""
        if not self.available:
            return CodexResult(
                task_type=CodexTaskType.COMPLETE_CODE,
                success=False,
                generated_code="",
                error="Codex client not available"
            )

        try:
            prompt = f"""Complete the following {language} code.
{f'Hint: {completion_hint}' if completion_hint else ''}

Code to complete:
```{language}
{partial_code}
```

Provide the completed code with explanation."""

            response = await self._call_openai(prompt)
            result = self._parse_completion_response(response, language)

            return result

        except Exception as e:
            logger.error(f"Error completing code: {str(e)}")
            return CodexResult(
                task_type=CodexTaskType.COMPLETE_CODE,
                success=False,
                generated_code="",
                error=str(e)
            )

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _build_poc_prompt(
        self,
        vulnerability_description: str,
        target_language: str,
        context: Optional[Dict[str, Any]],
        ethical_mode: bool
    ) -> str:
        """Build prompt for PoC generation"""

        ethical_disclaimer = ""
        if ethical_mode:
            ethical_disclaimer = """
IMPORTANT ETHICAL CONSIDERATIONS:
- This PoC is for authorized security testing only
- Include clear warnings and usage restrictions
- Provide remediation guidance
- Use harmless demonstration where possible
"""

        context_str = ""
        if context:
            context_str = f"\nContext:\n{json.dumps(context, indent=2)}"

        prompt = f"""{ethical_disclaimer}

Generate a proof-of-concept (PoC) demonstration for the following security vulnerability.

Vulnerability: {vulnerability_description}
Target Language: {target_language}
{context_str}

Requirements:
1. Create a safe, educational PoC that demonstrates the vulnerability
2. Include detailed comments explaining each step
3. Add clear warnings about authorized use only
4. Include remediation recommendations
5. Use placeholder values for sensitive data

Provide:
1. The PoC code with extensive comments
2. Usage instructions
3. Remediation guidance
4. Test cases to verify the fix

Format response as:
```{target_language}
[POC CODE]
```

## Explanation
[Detailed explanation]

## Remediation
[How to fix the vulnerability]

## Test Cases
[Test cases to verify the fix]
"""

        return prompt

    def _build_fix_prompt(
        self,
        vulnerable_code: str,
        vulnerability_type: str,
        language: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for fix generation"""

        context_str = ""
        if context:
            context_str = f"\nContext:\n{json.dumps(context, indent=2)}"

        prompt = f"""You are a security expert fixing code vulnerabilities.

Vulnerability Type: {vulnerability_type}
Language: {language}
{context_str}

Vulnerable Code:
```{language}
{vulnerable_code}
```

Generate a secure fix that:
1. Completely eliminates the {vulnerability_type} vulnerability
2. Maintains the original functionality
3. Follows security best practices
4. Includes input validation and sanitization
5. Uses secure libraries/functions where applicable

Provide:
1. The fixed code
2. Explanation of security improvements
3. Test cases to verify the fix
4. Additional security recommendations

Format response as:
```{language}
[FIXED CODE]
```

## Security Improvements
[What was changed and why]

## Test Cases
[Test cases to verify the fix]

## Additional Recommendations
[Other security improvements]
"""

        return prompt

    def _build_generation_prompt(
        self,
        specification: str,
        language: str,
        include_tests: bool,
        include_docs: bool
    ) -> str:
        """Build prompt for code generation"""

        prompt = f"""Generate {language} code based on the following specification.

Specification:
{specification}

Requirements:
- Clean, readable code following best practices
- Proper error handling
- Security considerations
- Type hints/annotations where applicable
{'- Comprehensive test cases' if include_tests else ''}
{'- Detailed documentation and comments' if include_docs else ''}

Provide the complete implementation."""

        return prompt

    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API with prompt"""

        import asyncio

        try:
            # Use asyncio to run sync OpenAI call
            loop = asyncio.get_event_loop()

            def sync_call():
                return self.openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert programmer and security researcher."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

            response = await loop.run_in_executor(None, sync_call)

            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "tokens": response.usage.total_tokens,
                "finish_reason": response.choices[0].finish_reason
            }

        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise

    def _parse_poc_response(
        self,
        response: Dict[str, Any],
        language: str,
        ethical_mode: bool
    ) -> CodexResult:
        """Parse PoC generation response"""

        content = response["content"]

        # Extract code block
        code = self._extract_code_block(content, language)

        # Extract sections
        explanation = self._extract_section(content, "Explanation")
        remediation = self._extract_section(content, "Remediation")
        test_cases_str = self._extract_section(content, "Test Cases")

        # Parse test cases
        test_cases = []
        if test_cases_str:
            test_cases = [tc.strip() for tc in test_cases_str.split('\n') if tc.strip()]

        # Security notes
        security_notes = []
        if ethical_mode:
            security_notes.append("FOR AUTHORIZED SECURITY TESTING ONLY")
            security_notes.append("Always obtain written permission before testing")

        if remediation:
            security_notes.append(f"Remediation: {remediation}")

        # Calculate cost (GPT-4 pricing)
        tokens = response.get("tokens", 0)
        cost_cents = (tokens / 1000) * 0.03 * 100  # ~$0.03/1K tokens

        return CodexResult(
            task_type=CodexTaskType.GENERATE_POC,
            success=True,
            generated_code=code,
            explanation=explanation,
            test_cases=test_cases,
            security_notes=security_notes,
            model_used=response.get("model", self.model),
            tokens_used=tokens,
            cost_cents=cost_cents
        )

    def _parse_fix_response(
        self,
        response: Dict[str, Any],
        language: str
    ) -> CodexResult:
        """Parse fix generation response"""

        content = response["content"]

        # Extract code block
        code = self._extract_code_block(content, language)

        # Extract sections
        improvements = self._extract_section(content, "Security Improvements")
        test_cases_str = self._extract_section(content, "Test Cases")
        recommendations = self._extract_section(content, "Additional Recommendations")

        # Parse test cases
        test_cases = []
        if test_cases_str:
            test_cases = [tc.strip() for tc in test_cases_str.split('\n') if tc.strip()]

        # Security notes
        security_notes = []
        if improvements:
            security_notes.append(improvements)
        if recommendations:
            security_notes.append(f"Recommendations: {recommendations}")

        # Calculate cost
        tokens = response.get("tokens", 0)
        cost_cents = (tokens / 1000) * 0.03 * 100

        return CodexResult(
            task_type=CodexTaskType.GENERATE_FIX,
            success=True,
            generated_code=code,
            explanation=improvements,
            test_cases=test_cases,
            security_notes=security_notes,
            model_used=response.get("model", self.model),
            tokens_used=tokens,
            cost_cents=cost_cents
        )

    def _parse_generation_response(
        self,
        response: Dict[str, Any],
        language: str,
        include_tests: bool
    ) -> CodexResult:
        """Parse code generation response"""

        content = response["content"]
        code = self._extract_code_block(content, language)

        test_cases = []
        if include_tests:
            test_cases_str = self._extract_section(content, "Test")
            if test_cases_str:
                test_cases = [tc.strip() for tc in test_cases_str.split('\n') if tc.strip()]

        tokens = response.get("tokens", 0)
        cost_cents = (tokens / 1000) * 0.03 * 100

        return CodexResult(
            task_type=CodexTaskType.GENERATE_CODE,
            success=True,
            generated_code=code,
            test_cases=test_cases,
            model_used=response.get("model", self.model),
            tokens_used=tokens,
            cost_cents=cost_cents
        )

    def _parse_completion_response(
        self,
        response: Dict[str, Any],
        language: str
    ) -> CodexResult:
        """Parse code completion response"""

        content = response["content"]
        code = self._extract_code_block(content, language)

        tokens = response.get("tokens", 0)
        cost_cents = (tokens / 1000) * 0.03 * 100

        return CodexResult(
            task_type=CodexTaskType.COMPLETE_CODE,
            success=True,
            generated_code=code,
            model_used=response.get("model", self.model),
            tokens_used=tokens,
            cost_cents=cost_cents
        )

    def _extract_code_block(self, content: str, language: str) -> str:
        """Extract code from markdown code block"""
        import re

        # Try to find code block with language specifier
        pattern = f"```{language}\\s*\\n(.*?)```"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        # Try generic code block
        pattern = "```\\s*\\n(.*?)```"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            return match.group(1).strip()

        # Return full content if no code block found
        return content.strip()

    def _extract_section(self, content: str, section_name: str) -> Optional[str]:
        """Extract section from markdown content"""
        import re

        pattern = f"##+ {section_name}\\s*\\n(.*?)(?=##|$)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return None


# Global instance
_codex_client: Optional[CodexClient] = None


def get_codex_client() -> CodexClient:
    """Get global Codex client instance"""
    global _codex_client
    if _codex_client is None:
        _codex_client = CodexClient()
    return _codex_client


def initialize_codex_client(
    api_key: Optional[str] = None,
    model: str = "gpt-4"
) -> CodexClient:
    """Initialize global Codex client"""
    global _codex_client
    _codex_client = CodexClient(api_key=api_key, model=model)
    logger.info("✓ Codex client initialized")
    return _codex_client
