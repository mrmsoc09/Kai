"""
Playbook execution hooks for evidence capture and monitoring.
Integrates with playbook runtime to capture proof-of-concept evidence.
"""

from __future__ import annotations

from .evidence_capturer import EvidenceCapturer, CapturedEvidence

__all__ = ["EvidenceCapturer", "CapturedEvidence"]
