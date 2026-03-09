from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..models.enums import IntentionSourceEnum, IntentionTypeEnum, RiskPolicyClassEnum


class IntentionCreate(BaseModel):
    campaign_id: UUID | None = None
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    parent_intention_id: UUID | None = None
    source: IntentionSourceEnum
    intention_type: IntentionTypeEnum
    initiated_by: str = Field(..., min_length=1, max_length=255)
    declared_goal: str = Field(..., min_length=1, max_length=2000)
    declared_reason: str | None = Field(default=None, max_length=4000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    risk_class: RiskPolicyClassEnum | None = None
    risk_posture_changed: bool = False
    approval_required: bool = False
    approval_reason: str | None = Field(default=None, max_length=2000)
    context_json: dict = Field(default_factory=dict)


class IntentionUpdate(BaseModel):
    declared_goal: str | None = Field(default=None, min_length=1, max_length=2000)
    declared_reason: str | None = Field(default=None, max_length=4000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    risk_class: RiskPolicyClassEnum | None = None
    risk_posture_changed: bool | None = None
    approval_required: bool | None = None
    approval_reason: str | None = Field(default=None, max_length=2000)
    context_json: dict | None = None


class IntentionRead(BaseModel):
    id: UUID
    campaign_id: UUID | None = None
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    parent_intention_id: UUID | None = None
    source: IntentionSourceEnum
    intention_type: IntentionTypeEnum
    initiated_by: str
    declared_goal: str
    declared_reason: str | None = None
    policy_basis: str | None = None
    risk_class: RiskPolicyClassEnum | None = None
    risk_posture_changed: bool
    approval_required: bool
    approval_reason: str | None = None
    context_json: dict
    created_at: datetime
    updated_at: datetime
