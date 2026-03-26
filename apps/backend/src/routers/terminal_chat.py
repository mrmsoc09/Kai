from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import time
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.auth import ROLE_OPERATOR, require_roles

router = APIRouter(tags=["terminal"], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
ART_ROOT = REPO_ROOT / "artifacts" / "logs"
ART_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_OLLAMA_MODELS = ("qwen2.5-coder:7b", "llama3.1:8b", "gemma:7b")
MAX_CAPTURE_BYTES = 120_000


class TerminalProvider(str, Enum):
    CODEX = "codex"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class TerminalExecuteIn(BaseModel):
    provider: TerminalProvider
    prompt: str = Field(min_length=1, max_length=12_000)
    model: str | None = Field(default=None, max_length=128)
    timeout_seconds: int = Field(default=180, ge=5, le=600)


def _decode_output(raw: bytes) -> str:
    if not raw:
        return ""
    if len(raw) > MAX_CAPTURE_BYTES:
        raw = raw[:MAX_CAPTURE_BYTES] + b"\n...[truncated]"
    return raw.decode("utf-8", errors="replace")


def _command_for_request(
    payload: TerminalExecuteIn,
) -> tuple[list[str], dict[str, str], str | None, bytes]:
    """Return (command, env, model_used, stdin_bytes).

    The user-supplied prompt is NEVER placed in the command argument list to
    prevent argument-injection attacks. It is always delivered via stdin.
    """
    env = os.environ.copy()
    model_used: str | None = None
    stdin_data = payload.prompt.encode("utf-8")

    if payload.provider == TerminalProvider.CODEX:
        # codex reads the prompt from stdin when no positional argument is given.
        return (
            [
                "codex",
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--color",
                "never",
            ],
            env,
            None,
            stdin_data,
        )

    if payload.provider == TerminalProvider.GEMINI:
        # gemini reads the prompt from stdin when -p is omitted.
        return (
            [
                "gemini",
                "-o",
                "text",
            ],
            env,
            None,
            stdin_data,
        )

    model_used = (payload.model or os.getenv("K1_TERMINAL_DEFAULT_OLLAMA_MODEL", "llama3.1:8b")).strip()
    if model_used not in ALLOWED_OLLAMA_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Ollama model not allowed. Allowed models: {', '.join(ALLOWED_OLLAMA_MODELS)}",
        )

    ollama_host = os.getenv("K1_OLLAMA_BASE_URL", "").strip()
    if ollama_host and not env.get("OLLAMA_HOST"):
        env["OLLAMA_HOST"] = ollama_host

    # ollama reads the prompt from stdin when no positional text argument is given.
    return (["ollama", "run", model_used], env, model_used, stdin_data)


async def _execute_command(
    command: list[str],
    env: dict[str, str],
    timeout_seconds: int,
    stdin_data: bytes = b"",
) -> tuple[int, bool, str, str, int]:
    started = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(REPO_ROOT),
        env=env,
    )

    timed_out = False
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=stdin_data),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        timed_out = True
        process.kill()
        stdout, stderr = await process.communicate()

    duration_ms = int((time.monotonic() - started) * 1000)
    return (
        process.returncode if process.returncode is not None else 1,
        timed_out,
        _decode_output(stdout),
        _decode_output(stderr),
        duration_ms,
    )


@router.get("/terminal/providers")
async def terminal_providers() -> dict[str, Any]:
    return {
        "providers": {
            "codex": {"available": shutil.which("codex") is not None},
            "gemini": {"available": shutil.which("gemini") is not None},
            "ollama": {
                "available": shutil.which("ollama") is not None,
                "allowed_models": list(ALLOWED_OLLAMA_MODELS),
                "default_model": os.getenv("K1_TERMINAL_DEFAULT_OLLAMA_MODEL", "llama3.1:8b"),
            },
        }
    }


@router.post("/terminal/execute")
async def terminal_execute(payload: TerminalExecuteIn, request: Request) -> dict[str, Any]:
    command, env, model_used, stdin_data = _command_for_request(payload)
    tool_binary = command[0]

    if shutil.which(tool_binary) is None:
        raise HTTPException(status_code=503, detail=f"Provider CLI not found: {tool_binary}")

    return_code, timed_out, stdout, stderr, duration_ms = await _execute_command(
        command=command,
        env=env,
        timeout_seconds=payload.timeout_seconds,
        stdin_data=stdin_data,
    )

    ts = int(time.time() * 1000)
    audit = {
        "ts": ts,
        "provider": payload.provider.value,
        "model": model_used,
        "timeout_seconds": payload.timeout_seconds,
        "duration_ms": duration_ms,
        "return_code": return_code,
        "timed_out": timed_out,
        "client": request.client.host if request.client else "unknown",
        "prompt_preview": payload.prompt[:500],
        "stdout_preview": stdout[:800],
        "stderr_preview": stderr[:800],
    }
    (ART_ROOT / f"terminal_exec_{ts}.json").write_text(
        json.dumps(audit, indent=2),
        encoding="utf-8",
    )

    return {
        "provider": payload.provider.value,
        "model": model_used,
        "command": command,
        "return_code": return_code,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "ok": return_code == 0 and not timed_out,
    }


@router.get("/terminal/logs")
async def terminal_logs(limit: int = 50) -> dict[str, Any]:
    clipped = max(1, min(limit, 200))
    entries: list[dict[str, Any]] = []
    files = sorted(ART_ROOT.glob("terminal_exec_*.json"), reverse=True)[:clipped]
    for path in files:
        try:
            entries.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return {"logs": entries}
