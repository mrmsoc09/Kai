"""
Program and VRP related schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ProgramStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    CLOSED = "closed"


class ProgramType(str, Enum):
    BUG_BOUNTY = "bug_bounty"
    VRP = "vrp"
    SECURITY_RESEARCH = "security_research"
    RESPONSIBLE_DISCLOSURE = "responsible_disclosure"


class ScopeItem(BaseModel):
    """Represents a scope item (domain, IP range, etc.)"""
    value: str
    type: str  # "domain", "ip", "url", "wildcard", "path"
    description: Optional[str] = None
    is_allowed: bool = True


class PayoutStructure(BaseModel):
    """Represents a payout structure for a program"""
    severity_level: str  # "critical", "high", "medium", "low", "info"
    min_payout: Optional[float] = None
    max_payout: Optional[float] = None
    typical_payout: Optional[float] = None
    currency: str = "USD"


class Program(BaseModel):
    """Represents a bug bounty or VRP program"""
    id: str
    name: str
    description: Optional[str] = None
    program_type: ProgramType
    status: ProgramStatus
    url: str
    platform: str  # "hackerone", "bugcrowd", "intigriti", "custom", etc.
    organization: Optional[str] = None

    # Scope
    allowed_scope: List[ScopeItem] = []
    excluded_scope: List[ScopeItem] = []
    scope_description: Optional[str] = None

    # Payouts
    payout_structure: List[PayoutStructure] = []
    min_payout: Optional[float] = None
    max_payout: Optional[float] = None
    average_payout: Optional[float] = None

    # Requirements
    requires_poc: bool = True
    requires_writeup: bool = False
    requires_responsible_disclosure: bool = True
    response_time_days: Optional[int] = None
    resolution_time_days: Optional[int] = None

    # Rules and restrictions
    allows_cross_team_collaboration: bool = False
    allows_public_disclosure: bool = False
    allows_competitor_employees: bool = True
    disallowed_vulnerability_types: List[str] = []

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_synced_at: Optional[datetime] = None
    success_count: int = 0
    total_payouts: float = 0.0
    average_response_time: Optional[float] = None

    # Contact
    contact_email: Optional[str] = None
    contact_url: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = {}


class ProgramSchema(BaseModel):
    """Schema for creating/updating programs"""
    name: str
    description: Optional[str] = None
    program_type: ProgramType = ProgramType.BUG_BOUNTY
    status: ProgramStatus = ProgramStatus.ACTIVE
    url: str
    platform: str
    organization: Optional[str] = None
    allowed_scope: List[Dict[str, str]] = []
    excluded_scope: List[Dict[str, str]] = []
    min_payout: Optional[float] = None
    max_payout: Optional[float] = None


class ProgramResponse(BaseModel):
    """Response for program queries"""
    success: bool
    data: Optional[Program] = None
    error: Optional[str] = None


class ProgramsListResponse(BaseModel):
    """Response for program list queries"""
    success: bool
    data: List[Program] = []
    total: int = 0
    error: Optional[str] = None


class ScrapeJob(BaseModel):
    """Represents a program scraping job"""
    id: str
    program_platform: str
    status: str  # "pending", "running", "completed", "failed"
    progress: int = 0
    total_items: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    programs_found: int = 0
    programs_updated: int = 0


class PayoutEstimate(BaseModel):
    """Payout estimate for a finding"""
    program_id: str
    program_name: str
    severity: str
    estimated_min: float
    estimated_max: float
    estimated_typical: float
    confidence: float  # 0-1
    reasoning: str
