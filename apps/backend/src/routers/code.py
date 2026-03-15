"""
Code Tasks API Router
Endpoints for code analysis, repair, PoC generation using CLI tools
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from ..integrations.claude_code_client import (
    get_claude_code_client,
    CodeTaskType,
    CodeContext
)
from ..integrations.codex_client import get_codex_client
from ..integrations.gemini_cli_client import get_gemini_client

router = APIRouter(prefix="/api/v1/code", tags=["code"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CodeAnalysisRequest(BaseModel):
    """Request for code analysis"""
    file_path: Optional[str] = None
    code_snippet: Optional[str] = None
    language: Optional[str] = None
    focus: Optional[str] = None


class CodeRepairRequest(BaseModel):
    """Request for vulnerability repair"""
    file_path: str
    vulnerability_description: str
    auto_apply: bool = True


class CodeGenerationRequest(BaseModel):
    """Request for code generation"""
    specification: str
    language: str
    output_file: Optional[str] = None
    include_tests: bool = True


class PoCGenerationRequest(BaseModel):
    """Request for PoC generation"""
    vulnerability_description: str
    target_language: str
    context: Optional[Dict[str, Any]] = None
    ethical_mode: bool = True


class FixGenerationRequest(BaseModel):
    """Request for fix generation"""
    vulnerable_code: str
    vulnerability_type: str
    language: str
    context: Optional[Dict[str, Any]] = None


class CodebaseAnalysisRequest(BaseModel):
    """Request for codebase analysis"""
    codebase_path: str
    query: str
    file_patterns: Optional[List[str]] = None


# ============================================================================
# Claude Code Endpoints
# ============================================================================

@router.post("/analyze")
async def analyze_code(request: CodeAnalysisRequest):
    """
    Analyze code for issues, vulnerabilities, and best practices.

    Uses Claude Code CLI for comprehensive code analysis.
    """
    try:
        client = get_claude_code_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Claude Code CLI not available"
            )

        if not request.file_path and not request.code_snippet:
            raise HTTPException(
                status_code=400,
                detail="Either file_path or code_snippet must be provided"
            )

        context = CodeContext(
            file_path=request.file_path,
            code_snippet=request.code_snippet,
            language=request.language
        )

        result = await client.execute_code_task(
            task_type=CodeTaskType.ANALYZE,
            instruction=request.focus or "Analyze for security, quality, and best practices",
            context=context
        )

        return {
            "success": result.success,
            "analysis": result.output,
            "changes_suggested": result.changes_made,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@router.post("/repair")
async def repair_vulnerability(request: CodeRepairRequest):
    """
    Repair a security vulnerability in code.

    Uses Claude Code CLI to automatically fix vulnerabilities.
    """
    try:
        client = get_claude_code_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Claude Code CLI not available"
            )

        result = await client.repair_vulnerability(
            file_path=request.file_path,
            vulnerability_description=request.vulnerability_description,
            auto_apply=request.auto_apply
        )

        return {
            "success": result.success,
            "output": result.output,
            "files_modified": result.files_modified,
            "changes_made": result.changes_made,
            "auto_applied": request.auto_apply,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Repair error: {str(e)}")


@router.post("/refactor")
async def refactor_code(
    file_path: str,
    refactoring_goal: str
):
    """Refactor code according to specified goal"""
    try:
        client = get_claude_code_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Claude Code CLI not available"
            )

        result = await client.refactor_code(
            file_path=file_path,
            refactoring_goal=refactoring_goal
        )

        return {
            "success": result.success,
            "output": result.output,
            "files_modified": result.files_modified,
            "changes_made": result.changes_made,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refactor error: {str(e)}")


@router.post("/explain")
async def explain_code(
    file_path: str,
    specific_section: Optional[str] = None
):
    """Explain what code does"""
    try:
        client = get_claude_code_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Claude Code CLI not available"
            )

        result = await client.explain_code(
            file_path=file_path,
            specific_section=specific_section
        )

        return {
            "success": result.success,
            "explanation": result.output,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation error: {str(e)}")


# ============================================================================
# Codex Endpoints
# ============================================================================

@router.post("/poc")
async def generate_poc(request: PoCGenerationRequest):
    """
    Generate proof-of-concept exploit code.

    Uses OpenAI Codex to create educational PoC demonstrations.
    """
    try:
        client = get_codex_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Codex not available (missing API key or library)"
            )

        result = await client.generate_poc(
            vulnerability_description=request.vulnerability_description,
            target_language=request.target_language,
            context=request.context,
            ethical_mode=request.ethical_mode
        )

        return {
            "success": result.success,
            "poc_code": result.generated_code,
            "explanation": result.explanation,
            "test_cases": result.test_cases,
            "security_notes": result.security_notes,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "cost_cents": result.cost_cents,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PoC generation error: {str(e)}")


@router.post("/fix")
async def generate_fix(request: FixGenerationRequest):
    """
    Generate secure fix for vulnerable code.

    Uses OpenAI Codex to create security patches.
    """
    try:
        client = get_codex_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Codex not available"
            )

        result = await client.generate_fix(
            vulnerable_code=request.vulnerable_code,
            vulnerability_type=request.vulnerability_type,
            language=request.language,
            context=request.context
        )

        return {
            "success": result.success,
            "fixed_code": result.generated_code,
            "explanation": result.explanation,
            "test_cases": result.test_cases,
            "security_notes": result.security_notes,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "cost_cents": result.cost_cents,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fix generation error: {str(e)}")


@router.post("/generate")
async def generate_code(request: CodeGenerationRequest):
    """
    Generate code from specification.

    Uses OpenAI Codex or Claude Code depending on complexity.
    """
    try:
        # Try Claude Code first if available
        claude_client = get_claude_code_client()
        if claude_client.available:
            result = await claude_client.generate_code(
                specification=request.specification,
                language=request.language,
                output_file=request.output_file
            )

            return {
                "success": result.success,
                "generated_code": result.output,
                "files_created": result.files_modified,
                "execution_time_ms": result.execution_time_ms,
                "tool_used": "claude_code",
                "error": result.error
            }

        # Fallback to Codex
        codex_client = get_codex_client()
        if not codex_client.available:
            raise HTTPException(
                status_code=503,
                detail="No code generation tools available"
            )

        result = await codex_client.generate_code(
            specification=request.specification,
            language=request.language,
            include_tests=request.include_tests
        )

        return {
            "success": result.success,
            "generated_code": result.generated_code,
            "test_cases": result.test_cases,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "cost_cents": result.cost_cents,
            "tool_used": "codex",
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code generation error: {str(e)}")


# ============================================================================
# Gemini CLI Endpoints
# ============================================================================

@router.post("/analyze-codebase")
async def analyze_codebase(request: CodebaseAnalysisRequest):
    """
    Analyze entire codebase with long-context analysis.

    Uses Google Gemini's 1M+ token context window.
    """
    try:
        client = get_gemini_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Gemini CLI not available"
            )

        result = await client.analyze_codebase(
            codebase_path=request.codebase_path,
            query=request.query,
            file_patterns=request.file_patterns
        )

        return {
            "success": result.success,
            "analysis": result.analysis,
            "summary": result.summary,
            "findings": result.findings,
            "context_size_tokens": result.context_size_tokens,
            "execution_time_ms": result.execution_time_ms,
            "model_used": result.model_used,
            "cost_cents": result.cost_cents,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Codebase analysis error: {str(e)}")


@router.post("/detect-patterns")
async def detect_patterns(
    files: List[str],
    pattern_description: str
):
    """Detect patterns across multiple files"""
    try:
        client = get_gemini_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Gemini CLI not available"
            )

        result = await client.detect_patterns(
            files=files,
            pattern_description=pattern_description
        )

        return {
            "success": result.success,
            "analysis": result.analysis,
            "findings": result.findings,
            "context_size_tokens": result.context_size_tokens,
            "model_used": result.model_used,
            "cost_cents": result.cost_cents,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pattern detection error: {str(e)}")


@router.post("/security-review")
async def multi_file_security_review(
    files: List[str],
    focus_areas: Optional[List[str]] = None
):
    """
    Perform security review across multiple files.

    Uses Gemini's long context to detect cross-file vulnerabilities.
    """
    try:
        client = get_gemini_client()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="Gemini CLI not available"
            )

        result = await client.multi_file_security_review(
            files=files,
            focus_areas=focus_areas
        )

        return {
            "success": result.success,
            "security_review": result.analysis,
            "findings": result.findings,
            "context_size_tokens": result.context_size_tokens,
            "execution_time_ms": result.execution_time_ms,
            "model_used": result.model_used,
            "cost_cents": result.cost_cents,
            "error": result.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Security review error: {str(e)}")


# ============================================================================
# Tool Status Endpoint
# ============================================================================

@router.get("/tools/status")
async def get_tools_status():
    """Get status of all code tools"""
    claude_client = get_claude_code_client()
    codex_client = get_codex_client()
    gemini_client = get_gemini_client()

    return {
        "tools": {
            "claude_code": {
                "available": claude_client.available,
                "capabilities": ["analyze", "repair", "refactor", "explain", "generate"]
            },
            "codex": {
                "available": codex_client.available,
                "capabilities": ["poc", "fix", "generate", "complete"]
            },
            "gemini": {
                "available": gemini_client.available,
                "capabilities": ["codebase_analysis", "pattern_detection", "security_review"]
            }
        },
        "available_count": sum([
            claude_client.available,
            codex_client.available,
            gemini_client.available
        ]),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
