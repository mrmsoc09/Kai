"""
Compatibility runner for Praison->CrewAI execution from Kai.

PraisonAI's legacy CrewAI path may pass raw OpenAI client objects to CrewAI
Agent construction. CrewAI expects model strings (or BaseLLM-compatible
objects), so Kai normalizes the handoff to canonical model strings.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Sequence

_PROVIDER_PREFIXES = (
    "openai/",
    "ollama/",
    "anthropic/",
    "google/",
    "groq/",
    "cohere/",
    "openrouter/",
)


def normalize_model_name(model: str | None) -> str:
    raw = (model or "").strip()
    if not raw:
        raw = (
            os.getenv("MODEL_NAME", "").strip()
            or os.getenv("OPENAI_MODEL_NAME", "").strip()
            or "openai/gpt-4o-mini"
        )
    lowered = raw.lower()
    if lowered.startswith(_PROVIDER_PREFIXES):
        return raw
    return f"openai/{raw}"


def patch_praison_llm_for_crewai() -> None:
    from praisonai.inc.models import PraisonAIModel

    def _crew_compatible_get_model(self) -> str:  # type: ignore[no-untyped-def]
        # CrewAI v1.x validates llm/function_calling_llm as string/BaseLLM.
        return normalize_model_name(getattr(self, "model", None))

    PraisonAIModel.get_model = _crew_compatible_get_model  # type: ignore[method-assign]


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if len(args) < 2:
        print(
            "usage: praison_crewai_compat_runner.py <yaml_path> <framework>",
            file=sys.stderr,
        )
        return 2

    yaml_path = args[0]
    framework = (args[1] or "").strip().lower()
    if framework == "crewai":
        patch_praison_llm_for_crewai()

    from praisonai.__main__ import main as praison_main

    sys.argv = ["praisonai", yaml_path, "--framework", framework]
    result = praison_main()
    if result is None:
        return 0
    try:
        return int(result)
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

