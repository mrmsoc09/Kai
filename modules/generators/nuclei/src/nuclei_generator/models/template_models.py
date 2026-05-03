"""
Data models for Nuclei template generation.
Uses Pydantic v2 for validation and serialization.
"""

from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MatcherType(str, Enum):
    STATUS = "status"
    WORD = "word"
    REGEX = "regex"
    BINARY = "binary"
    DSL = "dsl"
    SIZE = "size"


class ExtractorType(str, Enum):
    REGEX = "regex"
    JSON = "json"
    KVAL = "kval"
    XPATH = "xpath"
    DSL = "dsl"


class TemplateMetadata(BaseModel):
    """Metadata block for Nuclei templates."""
    id: str = Field(..., pattern=r"^[a-zA-Z0-9\-_]+$")
    name: str
    author: str = "auto-generated"
    severity: Severity = Severity.HIGH
    description: str
    tags: List[str] = Field(default_factory=list)
    reference: List[str] = Field(default_factory=list)
    classification: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('tags', mode='before')
    @classmethod
    def split_tags(cls, v):
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(',')]
        return v


class HTTPRequest(BaseModel):
    """HTTP request specification."""
    method: str = "GET"
    path: List[str] = Field(default_factory=lambda: ["{{BaseURL}}"])
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    matchers_condition: str = "or"
    redirects: bool = True
    max_redirects: int = 3


class Matcher(BaseModel):
    """Nuclei matcher definition."""
    type: MatcherType
    part: Optional[str] = None  # body, header, etc.
    words: Optional[List[str]] = None
    regex: Optional[List[str]] = None
    status: Optional[List[int]] = None
    binary: Optional[List[str]] = None
    dsl: Optional[List[str]] = None
    condition: Optional[str] = "or"
    negative: bool = False


class Extractor(BaseModel):
    """Data extraction definition."""
    type: ExtractorType
    name: Optional[str] = None
    part: Optional[str] = None
    regex: Optional[List[str]] = None
    json: Optional[List[str]] = None
    kval: Optional[List[str]] = None
    xpath: Optional[List[str]] = None
    dsl: Optional[List[str]] = None
    group: Optional[int] = 1


class CVEData(BaseModel):
    """CVE information structure."""
    cve_id: str
    description: str
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    cpe_list: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    published_date: Optional[str] = None
    last_modified: Optional[str] = None


class NucleiTemplate(BaseModel):
    """Complete Nuclei template structure."""
    metadata: TemplateMetadata
    template_type: str = "http"  # http, dns, network, file, etc.
    request: Optional[HTTPRequest] = None
    matchers: List[Matcher] = Field(default_factory=list)
    extractors: List[Extractor] = Field(default_factory=list)
    payloads: Optional[Dict[str, List[str]]] = None
    stop_at_first_match: bool = False
    req_condition: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format suitable for YAML serialization."""
        data = {
            "id": self.metadata.id,
            "info": {
                "name": self.metadata.name,
                "author": self.metadata.author,
                "severity": self.metadata.severity.value,
                "description": self.metadata.description,
                "tags": self.metadata.tags,
                "reference": self.metadata.reference,
            }
        }
        
        if self.metadata.classification:
            data["info"]["classification"] = self.metadata.classification
            
        if self.metadata.metadata:
            data["info"]["metadata"] = self.metadata.metadata
            
        # Add HTTP specific blocks
        if self.template_type == "http" and self.request:
            data["http"] = [{
                "method": self.request.method,
                "path": self.request.path,
                "redirects": self.request.redirects,
                "max-redirects": self.request.max_redirects,
            }]
            
            if self.request.headers:
                data["http"][0]["headers"] = self.request.headers
            if self.request.body:
                data["http"][0]["body"] = self.request.body
                
            if self.matchers:
                data["http"][0]["matchers-condition"] = self.request.matchers_condition
                data["http"][0]["matchers"] = []
                for m in self.matchers:
                    matcher_dict = {"type": m.type.value}
                    if m.part:
                        matcher_dict["part"] = m.part
                    if m.words:
                        matcher_dict["words"] = m.words
                    if m.regex:
                        matcher_dict["regex"] = m.regex
                    if m.status:
                        matcher_dict["status"] = m.status
                    if m.binary:
                        matcher_dict["binary"] = m.binary
                    if m.dsl:
                        matcher_dict["dsl"] = m.dsl
                    if m.condition:
                        matcher_dict["condition"] = m.condition
                    if m.negative:
                        matcher_dict["negative"] = True
                    data["http"][0]["matchers"].append(matcher_dict)
                    
            if self.extractors:
                data["http"][0]["extractors"] = []
                for e in self.extractors:
                    ext_dict = {"type": e.type.value}
                    if e.name:
                        ext_dict["name"] = e.name
                    if e.part:
                        ext_dict["part"] = e.part
                    if e.regex:
                        ext_dict["regex"] = e.regex
                    if e.json:
                        ext_dict["json"] = e.json
                    if e.kval:
                        ext_dict["kval"] = e.kval
                    if e.xpath:
                        ext_dict["xpath"] = e.xpath
                    if e.group:
                        ext_dict["group"] = e.group
                    data["http"][0]["extractors"].append(ext_dict)
                    
        return data
