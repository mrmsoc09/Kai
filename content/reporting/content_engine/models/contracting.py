"""
Models for US Government Contracting Opportunities.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import Field, field_validator

from content_engine.models.base import BaseContent, ContentMetadata


class SolicitationType(str, Enum):
    RFP = "Request for Proposal"
    RFQ = "Request for Quote"
    RFI = "Request for Information"
    SOURCES_SOUGHT = "Sources Sought"
    PRESOLICITATION = "Presolicitation"
    AWARD = "Award Notice"


class ContractType(str, Enum):
    FIXED_PRICE = "Fixed Price"
    COST_PLUS = "Cost Plus"
    TIME_MATERIALS = "Time and Materials"
    IDIQ = "IDIQ"
    BPA = "BPA"


class ContractingMetadata(ContentMetadata):
    """Metadata for contracting opportunities."""
    
    solicitation_number: Optional[str] = None
    agency: str = Field(default="")
    sub_agency: Optional[str] = None
    office: Optional[str] = None
    naics_codes: List[str] = Field(default_factory=list)
    psc_codes: List[str] = Field(default_factory=list)
    contract_type: ContractType = Field(default=ContractType.FIXED_PRICE)
    set_aside: Optional[str] = None  # Small Business, 8(a), etc.
    contract_value: Optional[Decimal] = None
    place_of_performance: Optional[str] = None


class ContractingOpportunity(BaseContent):
    """Government contracting opportunity model."""
    
    metadata: ContractingMetadata
    solicitation_type: SolicitationType = Field(default=SolicitationType.RFP)
    description: str = Field(default="")
    requirements: List[str] = Field(default_factory=list)
    evaluation_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    deliverables: List[str] = Field(default_factory=list)
    period_of_performance: Optional[str] = None
    key_personnel: List[Dict[str, str]] = Field(default_factory=list)
    past_performance_reqs: List[str] = Field(default_factory=list)
    due_date: Optional[datetime] = None
    questions_due_date: Optional[datetime] = None
    proposal_instructions: Optional[str] = None
    clauses: List[str] = Field(default_factory=list)
    
    @field_validator("naics_codes")
    @classmethod
    def validate_naics(cls, v: List[str]) -> List[str]:
        return [code.strip() for code in v if code.strip()]
