"""
K1 Wordlist Generator — context-aware and AI-assisted wordlist generation.

Three generation modes:
  1. Context   — derives words from target domain, discovered endpoints, company info
  2. SecLists  — streams and merges from SecLists files with deduplication
  3. AI        — uses the configured LLM to generate domain-specific terms

All modes can be combined and output deduped, sorted lists.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WordlistRequest:
    """Parameters for a wordlist generation job."""
    # Target context
    target_domain: str = ""
    company_name: str = ""
    tech_stack: list[str] = field(default_factory=list)
    discovered_paths: list[str] = field(default_factory=list)
    discovered_params: list[str] = field(default_factory=list)
    custom_seeds: list[str] = field(default_factory=list)

    # Generation options
    phase: str = "discovery"            # recon|discovery|fuzzing|brute_force
    include_seclists: bool = True       # merge in relevant SecLists files
    include_mutations: bool = True      # leet speak, case variants, number appends
    include_ai: bool = False            # LLM-generated domain-specific terms
    ai_count: int = 200                 # max AI-generated words
    max_words: int = 50_000            # hard cap on output size
    dedupe: bool = True
    sort: bool = False

    # Output
    save_path: Optional[str] = None     # write to disk if set


@dataclass
class WordlistResult:
    words: list[str]
    total: int
    source_breakdown: dict[str, int]
    generation_time_ms: float
    save_path: Optional[str] = None
    truncated: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _domain_words(domain: str) -> list[str]:
    """Split domain into meaningful word fragments."""
    # Strip TLD and www prefix
    parts = re.sub(r"^(www\.|api\.|app\.|m\.)", "", domain).split(".")
    words: list[str] = []
    for part in parts:
        # Split camelCase, hyphenated, underscored
        tokens = re.split(r"[-_]", part)
        tokens += re.findall(r"[A-Z][a-z]+|[a-z]+", part)
        words += [t.lower() for t in tokens if len(t) > 1]
    return list(dict.fromkeys(words))  # dedupe preserve order


def _path_words(paths: list[str]) -> list[str]:
    """Extract word fragments from discovered URL paths."""
    words: set[str] = set()
    for p in paths:
        parts = re.split(r"[/\-_\.]", p.strip("/"))
        for part in parts:
            part = re.sub(r"\d+$", "", part)  # strip trailing numbers
            if 2 <= len(part) <= 30:
                words.add(part.lower())
    return sorted(words)


_MUTATIONS = [
    lambda w: w,
    lambda w: w.capitalize(),
    lambda w: w.upper(),
    lambda w: w + "s",
    lambda w: w + "1",
    lambda w: w + "123",
    lambda w: w + "!",
    lambda w: "." + w,
    lambda w: w + ".php",
    lambda w: w + ".html",
    lambda w: w + ".js",
    lambda w: w + ".json",
    lambda w: w + ".xml",
    lambda w: w + ".bak",
    lambda w: w + ".old",
    lambda w: w + "_backup",
    lambda w: w + "-dev",
    lambda w: w + "-admin",
    lambda w: "admin-" + w,
    lambda w: "api-" + w,
    lambda w: "v1/" + w,
    lambda w: "v2/" + w,
]

_LEET: dict[str, str] = {
    "a": "@", "e": "3", "i": "1", "o": "0", "s": "$", "t": "7"
}


def _apply_mutations(words: list[str], include_leet: bool = False) -> list[str]:
    result: list[str] = []
    for w in words:
        for mut in _MUTATIONS:
            result.append(mut(w))
        if include_leet and len(w) <= 10:
            leet = "".join(_LEET.get(c, c) for c in w.lower())
            if leet != w:
                result.append(leet)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SecLists streamer
# ─────────────────────────────────────────────────────────────────────────────

async def _stream_seclists(phase: str, tech_stack: list[str]) -> AsyncIterator[str]:
    """Yield lines from relevant SecLists files for the given phase/tech."""
    from .wordlist_manager import get_wordlist_manager
    wm = get_wordlist_manager()
    paths = wm.for_phase(phase, tech_stack=tech_stack)

    for p in paths:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        yield line
            await asyncio.sleep(0)  # yield event loop
        except OSError as exc:
            logger.warning("WordlistGenerator: could not read %s: %s", p, exc)


# ─────────────────────────────────────────────────────────────────────────────
# AI generation
# ─────────────────────────────────────────────────────────────────────────────

async def _ai_generate(request: WordlistRequest) -> list[str]:
    """Use the platform LLM to generate domain-specific wordlist terms."""
    try:
        from .gemini_orchestrator import get_gemini_orchestrator

        orch = get_gemini_orchestrator()
        if orch is None:
            return []

        tech_str = ", ".join(request.tech_stack) if request.tech_stack else "unknown"
        paths_str = "\n".join(request.discovered_paths[:30]) if request.discovered_paths else "none"

        prompt = f"""You are a security researcher generating a targeted wordlist for web application testing.

Target domain: {request.target_domain}
Company/product name: {request.company_name or "unknown"}
Technology stack: {tech_str}
Scan phase: {request.phase}
Known paths (sample):
{paths_str}

Generate exactly {request.ai_count} wordlist entries — one per line — tailored to this target.
Include: directory names, file names (with extensions), API endpoint fragments, parameter names,
backup file patterns, admin paths, and tech-specific paths.
Output ONLY the words/paths, one per line. No numbering, no comments, no explanation."""

        result = await orch.execute(
            prompt,
            complexity_hint="low",
            timeout_seconds=60,
        )
        raw = result.get("output", "") or result.get("result", "")
        words = [
            line.strip().lstrip("/")
            for line in raw.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        return words[:request.ai_count]

    except Exception as exc:
        logger.warning("WordlistGenerator: AI generation failed: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Main generator
# ─────────────────────────────────────────────────────────────────────────────

async def generate_wordlist(request: WordlistRequest) -> WordlistResult:
    """
    Build a wordlist from context, SecLists, and optionally AI.

    Returns a WordlistResult with the deduplicated word list and stats.
    """
    t0 = time.monotonic()
    seen: set[str] = set()
    words: list[str] = []
    breakdown: dict[str, int] = {}

    def _add(source: str, batch: list[str]) -> None:
        added = 0
        for w in batch:
            w = w.strip()
            if not w or (request.dedupe and w in seen):
                continue
            if request.dedupe:
                seen.add(w)
            words.append(w)
            added += 1
            if len(words) >= request.max_words:
                break
        breakdown[source] = breakdown.get(source, 0) + added

    # 1. Custom seeds first (highest priority)
    if request.custom_seeds:
        _add("custom_seeds", request.custom_seeds)

    # 2. Context words from domain + company name
    ctx: list[str] = []
    if request.target_domain:
        ctx += _domain_words(request.target_domain)
    if request.company_name:
        ctx += _domain_words(request.company_name)
    if request.discovered_paths:
        ctx += _path_words(request.discovered_paths)
    if request.discovered_params:
        ctx += [p.lower() for p in request.discovered_params if p]
    _add("context", ctx)

    # 3. Mutations of context words
    if request.include_mutations and ctx:
        mutated = _apply_mutations(list(dict.fromkeys(ctx)))
        _add("mutations", mutated)

    # 4. SecLists
    if request.include_seclists and len(words) < request.max_words:
        sl_words: list[str] = []
        async for w in _stream_seclists(request.phase, request.tech_stack):
            sl_words.append(w)
            if len(words) + len(sl_words) >= request.max_words:
                break
        _add("seclists", sl_words)

    # 5. AI generation
    if request.include_ai and len(words) < request.max_words:
        ai_words = await _ai_generate(request)
        _add("ai", ai_words)

    truncated = len(words) >= request.max_words
    if request.sort:
        words.sort()

    # Save to disk if requested
    save_path: Optional[str] = None
    if request.save_path:
        out = Path(request.save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(words), encoding="utf-8")
        save_path = str(out)
        logger.info("WordlistGenerator: saved %d words to %s", len(words), save_path)

    return WordlistResult(
        words=words,
        total=len(words),
        source_breakdown=breakdown,
        generation_time_ms=(time.monotonic() - t0) * 1000,
        save_path=save_path,
        truncated=truncated,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: generate and save for a scan mission
# ─────────────────────────────────────────────────────────────────────────────

async def generate_mission_wordlist(
    mission_id: str,
    target_domain: str,
    phase: str,
    tech_stack: Optional[list[str]] = None,
    output_dir: Optional[str] = None,
) -> Path:
    """
    Generate a wordlist for a specific mission phase and save it.

    Returns the path to the saved wordlist file.
    """
    out_root = Path(
        output_dir
        or os.getenv("K1_WORKFLOW_OUTPUT_ROOT", "output")
    )
    save_path = out_root / "wordlists" / mission_id / f"{phase}.txt"

    req = WordlistRequest(
        target_domain=target_domain,
        tech_stack=tech_stack or [],
        phase=phase,
        include_seclists=True,
        include_mutations=True,
        include_ai=False,
        save_path=str(save_path),
        max_words=30_000,
    )
    result = await generate_wordlist(req)
    logger.info(
        "Mission %s phase %s: generated %d words (%s)",
        mission_id, phase, result.total, result.source_breakdown,
    )
    return save_path
