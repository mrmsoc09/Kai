"""
Models for Threat Intelligence Reports (STIX/TAXII aligned).
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator

from content_engine.models.base import BaseContent, ContentMetadata, Classification


class IndicatorType(str, Enum):
    IPV4 = "ipv4-addr"
    IPV6 = "ipv6-addr"
    DOMAIN = "domain-name"
    URL = "url"
    HASH_MD5 = "file-md5"
    HASH_SHA1 = "file-sha1"
    HASH_SHA256 = "file-sha256"
    EMAIL = "email-addr"
    MUTEX = "mutex"
    REGISTRY = "windows-registry-key"


class Indicator(BaseModel):
    """IOC (Indicator of Compromise)."""
    
    value: str
    type: IndicatorType
    description: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    confidence: int = Field(default=50, ge=0, le=100)
    malicious: bool = Field(default=True)
    context: Optional[str] = None


class TTP(BaseModel):
    """Tactics, Techniques, and Procedures."""
    
    mitre_id: Optional[str] = None  # e.g., T1566
    name: str
    description: str
    tactics: List[str] = Field(default_factory=list)


class ThreatActor(BaseModel):
    """Threat actor information."""
    
    name: str
    aliases: List[str] = Field(default_factory=list)
    sophistication: Optional[str] = None
    motivation: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None


class ThreatIntelMetadata(ContentMetadata):
    """Metadata for threat intelligence reports."""
    
    classification: Classification = Field(default=Classification.UNCLASSIFIED)
    threat_level: str = Field(default="Medium", pattern="^(Low|Medium|High|Critical)$")
    sectors: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    mitre_attack_version: Optional[str] = None


class ThreatIntelReport(BaseContent):
    """Threat intelligence report model."""
    
    metadata: ThreatIntelMetadata
    threat_actors: List[ThreatActor] = Field(default_factory=list)
    indicators: List[Indicator] = Field(default_factory=list)
    ttps: List[TTP] = Field(default_factory=list)
    victim_profile: Optional[str] = None
    impact_assessment: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    ioc_feed_url: Optional[str] = None
    stix_bundle: Optional[Dict[str, Any]] = None
