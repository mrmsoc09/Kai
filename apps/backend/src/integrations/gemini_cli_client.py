"""
Google Gemini CLI Client
Integration for long-context analysis tasks leveraging 1M+ token context window

Backend modes (K1_GEMINI_BACKEND_MODE env var):
  auto        — Try CLI binary first, fall back to direct API (default)
  cli         — Require gemini CLI binary (error if missing)
  api         — Use Google Generative AI SDK directly (developer API key)
  local_gemma — Run local Gemma model via Ollama (K1_LOCAL_GEMMA_MODEL)
  duet_ai     — Vertex AI / Duet AI paid subscription via ADC or service account
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from apps.backend.src.core.secret_manager import get_secret_manager, SecretManagerError

logger = logging.getLogger(__name__)


class GeminiTaskType(str, Enum):
    """Types of Gemini tasks"""
    LONG_CONTEXT_ANALYSIS = "long_context_analysis"
    CODEBASE_ANALYSIS = "codebase_analysis"
    DOCUMENT_SYNTHESIS = "document_synthesis"
    MULTI_FILE_REVIEW = "multi_file_review"
    PATTERN_DETECTION = "pattern_detection"


class GeminiBackendMode(str, Enum):
    """Backend execution mode for GeminiCLIClient."""
    AUTO = "auto"             # CLI → API fallback (default)
    CLI = "cli"               # Require gemini CLI binary
    API = "api"               # Google Generative AI SDK (developer key)
    LOCAL_GEMMA = "local_gemma"  # Local Gemma via Ollama
    DUET_AI = "duet_ai"       # Vertex AI / Duet AI paid subscription


@dataclass
class GeminiResult:
    """Result from Gemini task"""
    task_type: GeminiTaskType
    success: bool
    analysis: str
    summary: Optional[str] = None
    findings: List[Dict[str, Any]] = field(default_factory=list)
    context_size_tokens: int = 0
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    model_used: str = "gemini-2.0-flash"
    cost_cents: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GeminiCLIClient:
    """
    Google Gemini CLI for long-context analysis tasks.
    Leverages 1M+ token context window for whole-codebase analysis.

    Features:
    - Analyze entire codebases in single context
    - Multi-document synthesis
    - Pattern detection across large codebases
    - Long-form security reviews
    - Cross-file vulnerability detection
    """

    def __init__(
        self,
        cli_path: str = "gemini",
        api_key: Optional[str] = None,
        default_context_window: int = 1_000_000,
        timeout_seconds: int = 600,
        backend_mode: Optional[str] = None,
    ):
        """Initialize Gemini CLI client"""
        self.cli_path = cli_path
        if api_key:
            self.api_key = api_key
        else:
            try:
                self.api_key = get_secret_manager().get_required("GOOGLE_API_KEY")
            except SecretManagerError:
                self.api_key = None
        self.default_context_window = default_context_window
        self.timeout_seconds = timeout_seconds
        self.available = False

        # Backend mode: env var overrides constructor arg, then default AUTO
        raw_mode = (
            backend_mode
            or os.getenv("K1_GEMINI_BACKEND_MODE", GeminiBackendMode.AUTO)
        ).lower().replace("-", "_")
        try:
            self.backend_mode = GeminiBackendMode(raw_mode)
        except ValueError:
            logger.warning("Unknown K1_GEMINI_BACKEND_MODE=%r — using 'auto'", raw_mode)
            self.backend_mode = GeminiBackendMode.AUTO

        # Local Gemma model tag (used in LOCAL_GEMMA mode)
        # Default: gemma:7b (currently pulled in Ollama).
        # Set K1_LOCAL_GEMMA_MODEL=gemma4:8b once that tag is available.
        self.local_gemma_model = os.getenv("K1_LOCAL_GEMMA_MODEL", "gemma:7b")
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

        if not self.api_key and self.backend_mode not in (
            GeminiBackendMode.LOCAL_GEMMA,
        ):
            logger.warning("Google API key not found via secret manager.")
        else:
            self.available = True

        # Check if Gemini CLI is installed (only needed for CLI modes)
        if self.backend_mode in (GeminiBackendMode.AUTO, GeminiBackendMode.CLI):
            self._verify_installation()
        elif self.backend_mode == GeminiBackendMode.LOCAL_GEMMA:
            self._verify_ollama()
            self.available = True
        elif self.backend_mode == GeminiBackendMode.DUET_AI:
            self._verify_vertex()
        else:
            # API mode — needs api_key
            if self.api_key:
                self.available = True

    def _verify_installation(self) -> bool:
        """Verify Gemini CLI is installed and accessible"""
        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                self.available = self.available and True  # Require both CLI and API key
                version = result.stdout.strip()
                logger.info(f"✓ Gemini CLI available: {version}")
                return True
            else:
                logger.warning(f"Gemini CLI not responding correctly")
                return False

        except FileNotFoundError:
            logger.warning(f"Gemini CLI not found at: {self.cli_path}")
            logger.info("Install Gemini CLI from: https://ai.google.dev/gemini-api/docs/cli")

            # Fallback to API-only mode
            if self.api_key:
                logger.info("Will use Gemini API directly (no CLI)")
                self.use_api_fallback = True
                return True

            return False

        except Exception as e:
            logger.error(f"Error verifying Gemini CLI: {str(e)}")
            return False

    def _verify_ollama(self) -> bool:
        """Verify Ollama is running and the configured local model is available."""
        try:
            import requests as _req
            resp = _req.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if any(self.local_gemma_model in m for m in models):
                    logger.info(
                        "GeminiCLIClient: local model %r available via Ollama",
                        self.local_gemma_model,
                    )
                    return True
                logger.warning(
                    "GeminiCLIClient: model %r not found in Ollama (available: %s). "
                    "Pull with: ollama pull %s",
                    self.local_gemma_model,
                    ", ".join(models[:6]),
                    self.local_gemma_model,
                )
                return False
            return False
        except Exception as exc:
            logger.warning("GeminiCLIClient: Ollama check failed: %s", exc)
            return False

    def _verify_vertex(self) -> bool:
        """Verify Vertex AI / Duet AI credentials are available."""
        try:
            from google.cloud import aiplatform  # type: ignore
            project = os.getenv("GCP_PROJECT_ID")
            if not project:
                logger.warning(
                    "GeminiCLIClient: GCP_PROJECT_ID not set — Duet AI unavailable"
                )
                return False
            self.available = True
            logger.info(
                "GeminiCLIClient: Vertex AI / Duet AI wired (project=%s)", project
            )
            return True
        except ImportError:
            logger.warning(
                "GeminiCLIClient: google-cloud-aiplatform not installed — "
                "install with: pip install google-cloud-aiplatform"
            )
            return False
        except Exception as exc:
            logger.warning("GeminiCLIClient: Vertex AI check failed: %s", exc)
            return False

    async def _execute_via_local_ollama(
        self,
        documents: List[str],
        query: str,
        context_window: int,
        file_paths: bool,
    ) -> GeminiResult:
        """Execute via local Gemma model running in Ollama."""
        try:
            import requests as _req

            # Load document content
            doc_contents: List[Dict[str, str]] = []
            if file_paths:
                for path in documents:
                    try:
                        with open(path, "r", errors="replace") as f:
                            doc_contents.append({"path": path, "content": f.read()})
                    except OSError:
                        pass
            else:
                for i, content in enumerate(documents):
                    doc_contents.append({"path": f"document_{i}", "content": content})

            prompt = self._build_long_context_prompt(doc_contents, query)

            # Truncate to rough token budget (4 chars ≈ 1 token, 8192 token default)
            max_chars = context_window * 4
            if len(prompt) > max_chars:
                prompt = prompt[:max_chars] + "\n\n[...truncated for context window...]"

            payload = {
                "model": self.local_gemma_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": min(context_window, 8192)},
            }

            logger.info(
                "GeminiCLIClient: sending %d chars to Ollama model %s",
                len(prompt),
                self.local_gemma_model,
            )

            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _req.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=self.timeout_seconds,
                ),
            )

            if resp.status_code != 200:
                return GeminiResult(
                    task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                    success=False,
                    analysis="",
                    model_used=self.local_gemma_model,
                    error=f"Ollama returned HTTP {resp.status_code}",
                )

            data = resp.json()
            text = data.get("response", "")
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=True,
                analysis=text,
                model_used=self.local_gemma_model,
                context_size_tokens=data.get("eval_count", 0),
                cost_cents=0.0,
            )

        except Exception as exc:
            logger.error("GeminiCLIClient: Ollama execution error: %s", exc)
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                model_used=self.local_gemma_model,
                error=str(exc),
            )

    async def _execute_via_duet_ai(
        self,
        documents: List[str],
        query: str,
        context_window: int,
        file_paths: bool,
    ) -> GeminiResult:
        """Execute via Vertex AI (Duet AI paid subscription)."""
        try:
            from google.cloud import aiplatform  # type: ignore
            from vertexai.generative_models import GenerativeModel  # type: ignore
            import vertexai  # type: ignore

            project = os.getenv("GCP_PROJECT_ID")
            location = os.getenv("GCP_LOCATION", "us-central1")
            vertex_model = os.getenv("K1_VERTEX_MODEL", "gemini-2.5-pro")

            vertexai.init(project=project, location=location)
            model = GenerativeModel(vertex_model)

            # Load documents
            doc_contents: List[Dict[str, str]] = []
            if file_paths:
                for path in documents:
                    try:
                        with open(path, "r", errors="replace") as f:
                            doc_contents.append({"path": path, "content": f.read()})
                    except OSError:
                        pass
            else:
                for i, content in enumerate(documents):
                    doc_contents.append({"path": f"document_{i}", "content": content})

            prompt = self._build_long_context_prompt(doc_contents, query)

            logger.info(
                "GeminiCLIClient: sending %d chars to Vertex AI %s (project=%s)",
                len(prompt),
                vertex_model,
                project,
            )

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content(prompt),
            )

            text = response.text if hasattr(response, "text") else str(response)
            estimated_tokens = len(prompt) // 4
            cost_cents = (estimated_tokens / 1_000_000) * 7.5  # ~$0.075/1M input tokens

            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=True,
                analysis=text,
                model_used=vertex_model,
                context_size_tokens=estimated_tokens,
                cost_cents=cost_cents,
            )

        except ImportError as exc:
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                error=f"Vertex AI dependencies not installed: {exc}",
            )
        except Exception as exc:
            logger.error("GeminiCLIClient: Vertex AI execution error: %s", exc)
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                error=str(exc),
            )

    async def analyze_with_long_context(
        self,
        documents: List[str],
        query: str,
        context_window: Optional[int] = None,
        file_paths: bool = True
    ) -> GeminiResult:
        """
        Use Gemini's 1M token context for whole-codebase analysis.

        Args:
            documents: List of document paths or content strings
            query: Analysis query/instruction
            context_window: Token limit (default: 1M)
            file_paths: If True, documents are file paths; if False, raw content

        Returns:
            GeminiResult with analysis
        """
        if not self.available and not self.api_key:
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                error="Gemini client not available (missing CLI or API key)"
            )

        start_time = datetime.now(timezone.utc)
        context_window = context_window or self.default_context_window

        try:
            # Route based on backend_mode
            if self.backend_mode == GeminiBackendMode.LOCAL_GEMMA:
                result = await self._execute_via_local_ollama(
                    documents, query, context_window, file_paths
                )
            elif self.backend_mode == GeminiBackendMode.DUET_AI:
                result = await self._execute_via_duet_ai(
                    documents, query, context_window, file_paths
                )
            elif self.backend_mode == GeminiBackendMode.API:
                result = await self._execute_via_api(
                    documents, query, context_window, file_paths
                )
            elif self.backend_mode == GeminiBackendMode.CLI:
                result = await self._execute_via_cli(
                    documents, query, context_window, file_paths
                )
            else:
                # AUTO: CLI first, then API fallback
                if hasattr(self, "use_api_fallback") and self.use_api_fallback:
                    result = await self._execute_via_api(
                        documents, query, context_window, file_paths
                    )
                else:
                    result = await self._execute_via_cli(
                        documents, query, context_window, file_paths
                    )

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            result.execution_time_ms = execution_time
            return result

        except asyncio.TimeoutError:
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                error=f"Task timed out after {self.timeout_seconds} seconds"
            )
        except Exception as e:
            logger.error(f"Error in Gemini analysis: {str(e)}")
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                error=str(e)
            )

    async def _execute_via_cli(
        self,
        documents: List[str],
        query: str,
        context_window: int,
        file_paths: bool
    ) -> GeminiResult:
        """Execute via Gemini CLI"""

        # Build command
        command = [
            self.cli_path,
            "analyze",
            "--context-size", str(context_window),
            "--query", query
        ]

        # Add documents
        if file_paths:
            for doc_path in documents:
                command.extend(["--input", doc_path])
        else:
            # Save content to temp files
            import tempfile
            temp_files = []
            for i, content in enumerate(documents):
                temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
                temp_file.write(content)
                temp_file.close()
                temp_files.append(temp_file.name)
                command.extend(["--input", temp_file.name])

        # Set API key
        env = os.environ.copy()
        if self.api_key:
            env["GOOGLE_API_KEY"] = self.api_key

        logger.info(f"Executing Gemini CLI with {len(documents)} documents")

        # Execute
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds
            )

            # Clean up temp files
            if not file_paths:
                for temp_file in temp_files:
                    try:
                        os.unlink(temp_file)
                    except Exception:
                        pass

            if process.returncode != 0:
                return GeminiResult(
                    task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                    success=False,
                    analysis="",
                    error=stderr.decode('utf-8')
                )

            # Parse output
            output = stdout.decode('utf-8')
            return self._parse_cli_output(output, GeminiTaskType.LONG_CONTEXT_ANALYSIS)

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise

    async def _execute_via_api(
        self,
        documents: List[str],
        query: str,
        context_window: int,
        file_paths: bool
    ) -> GeminiResult:
        """Execute via Gemini API directly"""

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')

            # Load document content
            document_contents = []
            if file_paths:
                for doc_path in documents:
                    with open(doc_path, 'r') as f:
                        content = f.read()
                        document_contents.append({
                            'path': doc_path,
                            'content': content
                        })
            else:
                for i, content in enumerate(documents):
                    document_contents.append({
                        'path': f'document_{i}',
                        'content': content
                    })

            # Build prompt
            prompt = self._build_long_context_prompt(document_contents, query)

            # Generate response
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content(prompt)
            )

            # Calculate cost (Gemini 2.0 Flash pricing)
            # Input: $0.075/1M tokens, Output: $0.30/1M tokens
            # Estimate tokens (rough approximation)
            total_chars = sum(len(doc['content']) for doc in document_contents) + len(query)
            estimated_tokens = total_chars // 4  # Rough estimate
            cost_cents = (estimated_tokens / 1_000_000) * 0.075 * 100

            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=True,
                analysis=response.text,
                context_size_tokens=estimated_tokens,
                model_used="gemini-2.0-flash",
                cost_cents=cost_cents
            )

        except ImportError:
            logger.error("Google Generative AI library not installed. Install with: pip install google-generativeai")
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                error="google-generativeai library not installed"
            )
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            return GeminiResult(
                task_type=GeminiTaskType.LONG_CONTEXT_ANALYSIS,
                success=False,
                analysis="",
                error=str(e)
            )

    def _build_long_context_prompt(
        self,
        documents: List[Dict[str, str]],
        query: str
    ) -> str:
        """Build prompt for long-context analysis"""

        # Build document context
        context_parts = []
        for doc in documents:
            context_parts.append(f"=== {doc['path']} ===\n{doc['content']}\n")

        context = "\n".join(context_parts)

        prompt = f"""You are analyzing a large codebase/document set with the following query:

{query}

Below are all the documents in context:

{context}

Provide a comprehensive analysis addressing the query. Include:
1. Summary of findings
2. Specific examples with file references
3. Patterns or trends observed
4. Recommendations or action items

Analysis:"""

        return prompt

    def _parse_cli_output(
        self,
        output: str,
        task_type: GeminiTaskType
    ) -> GeminiResult:
        """Parse Gemini CLI output"""

        # Try to parse as JSON first
        try:
            data = json.loads(output)
            return GeminiResult(
                task_type=task_type,
                success=True,
                analysis=data.get('analysis', output),
                summary=data.get('summary'),
                findings=data.get('findings', []),
                context_size_tokens=data.get('context_size_tokens', 0),
                model_used=data.get('model', 'gemini-2.0-flash')
            )
        except json.JSONDecodeError:
            # Treat as plain text
            return GeminiResult(
                task_type=task_type,
                success=True,
                analysis=output,
                model_used='gemini-2.0-flash'
            )

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    async def analyze_codebase(
        self,
        codebase_path: str,
        query: str,
        file_patterns: Optional[List[str]] = None
    ) -> GeminiResult:
        """Analyze entire codebase with single query"""

        # Discover files
        codebase = Path(codebase_path)
        file_patterns = file_patterns or ["**/*.py", "**/*.js", "**/*.java", "**/*.go"]

        files = []
        for pattern in file_patterns:
            files.extend(codebase.glob(pattern))

        file_paths = [str(f) for f in files[:100]]  # Limit to 100 files

        logger.info(f"Analyzing {len(file_paths)} files from {codebase_path}")

        return await self.analyze_with_long_context(
            documents=file_paths,
            query=query,
            file_paths=True
        )

    async def detect_patterns(
        self,
        files: List[str],
        pattern_description: str
    ) -> GeminiResult:
        """Detect patterns across multiple files"""

        query = f"""Detect and analyze patterns matching: {pattern_description}

For each occurrence, provide:
- File location
- Code snippet
- Pattern explanation
- Potential issues or improvements"""

        return await self.analyze_with_long_context(
            documents=files,
            query=query,
            file_paths=True
        )

    async def multi_file_security_review(
        self,
        files: List[str],
        focus_areas: Optional[List[str]] = None
    ) -> GeminiResult:
        """Perform security review across multiple files"""

        focus_str = ""
        if focus_areas:
            focus_str = f"\nFocus on: {', '.join(focus_areas)}"

        query = f"""Perform comprehensive security review across all provided files.
{focus_str}

Analyze for:
1. Cross-file vulnerabilities (authentication bypasses, data leakage)
2. Inconsistent security controls
3. OWASP Top 10 vulnerabilities
4. Logic flaws spanning multiple files
5. Missing security best practices

Provide detailed findings with file references and remediation guidance."""

        result = await self.analyze_with_long_context(
            documents=files,
            query=query,
            file_paths=True
        )

        result.task_type = GeminiTaskType.MULTI_FILE_REVIEW
        return result

    async def synthesize_documents(
        self,
        documents: List[str],
        synthesis_goal: str
    ) -> GeminiResult:
        """Synthesize information from multiple documents"""

        query = f"""Synthesize information from all provided documents to: {synthesis_goal}

Provide:
1. Comprehensive synthesis
2. Key insights from each document
3. Connections between documents
4. Conclusions and recommendations"""

        result = await self.analyze_with_long_context(
            documents=documents,
            query=query,
            file_paths=False  # Treat as content
        )

        result.task_type = GeminiTaskType.DOCUMENT_SYNTHESIS
        return result


# Global instance
_gemini_client: Optional[GeminiCLIClient] = None


def get_gemini_client() -> GeminiCLIClient:
    """Get global Gemini client instance"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiCLIClient()
    return _gemini_client


def initialize_gemini_client(
    cli_path: str = "gemini",
    api_key: Optional[str] = None,
    context_window: int = 1_000_000
) -> GeminiCLIClient:
    """Initialize global Gemini client"""
    global _gemini_client
    _gemini_client = GeminiCLIClient(
        cli_path=cli_path,
        api_key=api_key,
        default_context_window=context_window
    )
    logger.info("✓ Gemini CLI client initialized")
    return _gemini_client
