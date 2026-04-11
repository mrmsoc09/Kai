"""
Platform integration clients for HackerOne, Bugcrowd, and Intigriti.
Handles OAuth, API communication, and submission workflows.
"""

from __future__ import annotations

from .submission_handler import SubmissionHandler, get_platform_client, PlatformType
from .base_platform_client import (
    BasePlatformClient,
    SubmissionPayload,
    SubmissionResult,
)
from .hackerone_client import HackerOneClient
from .bugcrowd_client import BugcrowdClient
from .intigriti_client import IntigrityClient

__all__ = [
    "SubmissionHandler",
    "get_platform_client",
    "PlatformType",
    "BasePlatformClient",
    "SubmissionPayload",
    "SubmissionResult",
    "HackerOneClient",
    "BugcrowdClient",
    "IntigrityClient",
]
