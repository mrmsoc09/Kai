from __future__ import annotations

from enum import Enum


class SeverityEnum(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingStatusEnum(str, Enum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    HIL_APPROVED = "HIL_APPROVED"
    SUBMITTED = "SUBMITTED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


class HILApprovalStatusEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ExecutionStatusEnum(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
