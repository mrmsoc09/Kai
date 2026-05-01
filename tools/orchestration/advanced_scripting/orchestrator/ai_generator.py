"""
AI integration for autonomous script generation using Kimi k2.5.
"""
import json
import os
from typing import Dict, List, Optional, Tuple
import aiohttp
from dataclasses import dataclass

from .models import ScriptLanguage, Script
from .security import SecurityValidator


@dataclass
class GenerationRequest:
    description: str
    language: ScriptLanguage
    requirements: List[str]
    security_level: str = "strict"  # strict, standard, permissive
    include_comments: bool = True
    max_lines: int = 200


class ScriptGenerator:
    """AI-powered script generation using Kimi k2.5."""
    
    SYSTEM_PROMPT = """You are an expert security and automation engineer. 
Generate clean, secure, and efficient scripts based on user requirements.
Follow these guidelines:
1. Always validate inputs and sanitize data
2. Use secure defaults (no hardcoded secrets)
3. Include error handling and logging
4. Follow language-specific best practices
5. Add comments explaining security-critical sections
6. Never generate code that could be used maliciously
7. Prefer read-only operations unless explicitly requested otherwise"""

    LANGUAGE_PROMPTS = {
        ScriptLanguage.PYTHON: "Generate Python 3.9+ code. Use type hints where appropriate. Include docstrings.",
        ScriptLanguage.BASH: "Generate POSIX-compliant Bash scripts. Include set -euo pipefail. Validate all inputs.",
        ScriptLanguage.GO: "Generate Go 1.21+ code. Handle errors explicitly. Use context for timeouts."
    }
    
    def __init__(self, api_key: Optional[str] = None, model: str = "kimi-k2.5"):
        self.api_key = api_key or os.getenv("KIMI_API_KEY")
        self.model = model
        self.endpoint = "https://api.moonshot.cn/v1/chat/completions"
        self.validator = SecurityValidator()
    
    async def generate_script(self, request: GenerationRequest) -> Tuple[str, str, Dict]:
        """
        Generate script using AI.
        Returns: (code, explanation, metadata)
        """
        if not self.api_key:
            raise ValueError("API key not configured")
        
        prompt = self._build_prompt(request)
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 4096
            }
            
            async with session.post(
                self.endpoint, 
                headers=headers, 
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API error: {error_text}")
                
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Parse code and explanation
                code, explanation = self._parse_response(content, request.language)
                
                # Security check on generated code
                is_safe, violations = self.validator.validate_script(code, request.language)
                if not is_safe:
                    # Try to fix or warn
                    explanation += f"\n\nSecurity warnings:\n" + "\n".join(violations)
                
                metadata = {
                    "model": self.model,
                    "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                    "security_validated": is_safe,
                    "violations": violations if not is_safe else []
                }
                
                return code, explanation, metadata
    
    def _build_prompt(self, request: GenerationRequest) -> str:
        """Build detailed prompt for the AI."""
        lang_specific = self.LANGUAGE_PROMPTS.get(request.language, "")
        
        security_instructions = {
            "strict": "Avoid any file system modifications outside /tmp. No network calls. Read-only operations preferred.",
            "standard": "Normal security practices. Validate inputs. No execution of user input.",
            "permissive": "Standard security only. Allow file operations and network if required by task."
        }.get(request.security_level, "Standard security practices.")
        
        comments_instruction = "Include detailed comments" if request.include_comments else "Minimal comments"
        
        requirements_str = "\n".join(f"- {r}" for r in request.requirements)
        
        prompt = f"""{lang_specific}

Task Description:
{request.description}

Requirements:
{requirements_str}

Security Context: {security_instructions}

Constraints:
- Maximum {request.max_lines} lines
- {comments_instruction}
- Include error handling
- Return only the code and a brief explanation

Format your response as:
```[language]
[code]
```
Explanation: [Brief explanation of the code and security considerations]"""
        return prompt

    def _parse_response(self, content: str, language: ScriptLanguage) -> Tuple[str, str]:
        """Extract code and explanation from AI response."""
        # Extract code block
        code_start = content.find("```")
        if code_start == -1:
            return "", content

        # Move past the opening ```
        code_start_newline = content.find("\n", code_start)
        if code_start_newline == -1:
            return "", content
            
        code_end = content.find("```", code_start_newline)
        if code_end == -1:
            code = content[code_start_newline:].strip()
            explanation = ""
        else:
            code = content[code_start_newline:code_end].strip()
            explanation = content[code_end + 3:].strip()
            
        if explanation.startswith("Explanation:"):
            explanation = explanation[12:].strip()
            
        return code, explanation

    async def analyze_script(self, script_content: str, language: ScriptLanguage) -> Dict:
        """Analyze existing script for security and quality."""
        prompt = f"""Analyze this {language.value} script for:
1. Security vulnerabilities
2. Code quality issues
3. Performance bottlenecks
4. Best practice violations

Script:
```
{script_content}
```

Provide a JSON response with:
{{
    "security_score": 1-10,
    "quality_score": 1-10,
    "issues": [
        {{"severity": "high|medium|low", "description": "...", "line": number}}
    ],
    "recommendations": ["..."]
}}"""
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a code reviewer. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            async with session.post(self.endpoint, headers=headers, json=payload) as response:
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                
                try:
                    # Find JSON block
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    if json_start != -1 and json_end > json_start:
                        return json.loads(content[json_start:json_end])
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {
                        "security_score": 0,
                        "quality_score": 0,
                        "issues": [{"severity": "high", "description": "Failed to parse analysis", "line": 0}],
                        "recommendations": ["Manual review required"]
                    }
