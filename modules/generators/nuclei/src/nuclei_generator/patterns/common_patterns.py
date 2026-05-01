"""
Common vulnerability patterns library.
Pre-defined matchers for frequent vulnerability classes.
Architecture: Registry Pattern for dynamic pattern loading.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from ..models.template_models import Matcher, MatcherType, Extractor, ExtractorType


@dataclass
class VulnerabilityPattern:
    """Represents a detectable vulnerability pattern."""
    name: str
    description: str
    tags: List[str]
    matchers: List[Matcher]
    extractors: Optional[List[Extractor]] = None
    severity: str = "high"
    references: List[str] = field(default_factory=list)


class PatternLibrary:
    """
    Library of common vulnerability patterns.
    Extensible registry for custom detection logic.
    """
    
    def __init__(self):
        self._patterns: Dict[str, VulnerabilityPattern] = {}
        self._register_builtin_patterns()
    
    def register(self, pattern: VulnerabilityPattern):
        """Register a new pattern."""
        self._patterns[pattern.name] = pattern
    
    def get(self, name: str) -> Optional[VulnerabilityPattern]:
        """Retrieve pattern by name."""
        return self._patterns.get(name)
    
    def list_patterns(self) -> List[str]:
        """List all available pattern names."""
        return list(self._patterns.keys())
    
    def search_by_tag(self, tag: str) -> List[VulnerabilityPattern]:
        """Find patterns by tag."""
        return [p for p in self._patterns.values() if tag in p.tags]
    
    def _register_builtin_patterns(self):
        """Initialize built-in vulnerability patterns."""
        
        # SQL Injection Patterns
        self.register(VulnerabilityPattern(
            name="sqli_error_based",
            description="SQL Injection detection via database error messages",
            tags=["sqli", "injection", "database", "error-based"],
            severity="critical",
            matchers=[
                Matcher(
                    type=MatcherType.REGEX,
                    part="body",
                    regex=[
                        "SQL syntax.*?MySQL",
                        "Warning.*?\\Wmysqli?_",
                        "PostgreSQL.*?ERROR",
                        "Warning.*?\\Wpg_",
                        "Oracle.*?Driver",
                        "Microsoft SQL Server.*?ERROR",
                        "ODBC SQL Server Driver",
                        "SQLServer JDBC Driver",
                        "SqlException",
                        "SQLite/JDBCDriver",
                        "SQLite.Exception",
                        "System.Data.SQLite.SQLiteException",
                        "Warning.*?sqlite_",
                        "Warning.*?SQLite3::",
                        "\\[SQLITE_ERROR\\]",
                        "SQL error.*?POS",
                        "Warning.*?\\Wmssql_",
                        "Driver.*? SQL[\\-\\_\\*]*Server",
                        "OLE DB.*? SQL Server",
                        "\\bSQL\\bServer.*?Driver",
                        "Warning.*?\\Woci_",
                        "Warning.*?\\Wora_",
                        "Oracle error",
                        "Oracle.*?Driver",
                        "Warning.*?\\Wsybase_",
                        "Sybase message",
                        "Sybase.*?Server message"
                    ],
                    condition="or"
                )
            ],
            extractors=[
                Extractor(
                    type=ExtractorType.REGEX,
                    name="error",
                    part="body",
                    regex=["(SQL syntax.*?MySQL|PostgreSQL.*?ERROR|Oracle.*?error)"]
                )
            ]
        ))
        
        # Cross-Site Scripting (XSS)
        self.register(VulnerabilityPattern(
            name="xss_reflected",
            description="Reflected XSS detection",
            tags=["xss", "injection", "reflected"],
            severity="high",
            matchers=[
                Matcher(
                    type=MatcherType.DSL,
                    dsl=[
                        "status_code == 200",
                        "contains(body, '<script>alert(1)</script>') || contains(body, 'alert(1)')"
                    ],
                    condition="and"
                )
            ]
        ))
        
        # Local File Inclusion (LFI)
        self.register(VulnerabilityPattern(
            name="lfi_unix",
            description="Local File Inclusion - Unix path traversal",
            tags=["lfi", "traversal", "file-inclusion"],
            severity="high",
            matchers=[
                Matcher(
                    type=MatcherType.REGEX,
                    part="body",
                    regex=[
                        "root:.*?:0:0:",
                        "daemon:.*?:[0-9]+:[0-9]+:",
                        "for 16-bit app support",
                        "\\[boot loader\\]",
                        "\\[fonts\\]",
                        "root:x:0:0:",
                        "bin:x:1:1:",
                        "daemon:x:2:2:"
                    ],
                    condition="or"
                )
            ]
        ))
        
        # Remote Code Execution (RCE)
        self.register(VulnerabilityPattern(
            name="rce_basic",
            description="Remote Code Execution detection",
            tags=["rce", "code-execution", "injection"],
            severity="critical",
            matchers=[
                Matcher(
                    type=MatcherType.REGEX,
                    part="body",
                    regex=[
                        "uid=\\d+\\(\\w+\\) gid=\\d+\\(\\w+\\)",
                        "Microsoft Windows \\[Version",
                        "root@.*?#",
                        "www-data:",
                        "apache:",
                        "nginx:"
                    ],
                    condition="or"
                )
            ]
        ))
        
        # XML External Entity (XXE)
        self.register(VulnerabilityPattern(
            name="xxe_detection",
            description="XXE vulnerability detection",
            tags=["xxe", "xml", "injection", "ssrf"],
            severity="critical",
            matchers=[
                Matcher(
                    type=MatcherType.REGEX,
                    part="body",
                    regex=[
                        "root:.*?:0:0:",
                        "file:///etc/passwd",
                        "file:///c:/windows/win.ini",
                        "java\\.io\\.FileNotFoundException",
                        "java\\.net\\.",
                        "javax\\.xml\\.",
                        "org\\.xml\\.sax\\."
                    ],
                    condition="or"
                )
            ]
        ))
        
        # Server-Side Request Forgery (SSRF)
        self.register(VulnerabilityPattern(
            name="ssrf_detection",
            description="SSRF vulnerability detection",
            tags=["ssrf", "injection", "server-side"],
            severity="high",
            matchers=[
                Matcher(
                    type=MatcherType.REGEX,
                    part="body",
                    regex=[
                        "127\\.0\\.0\\.1",
                        "localhost",
                        "internal",
                        "169\\.254\\.169\\.254",  # AWS metadata
                        "metadata\\.google\\.internal",  # GCP metadata
                        "169\\.254\\.170\\.2"  # Azure metadata
                    ],
                    condition="or"
                )
            ]
        ))
        
        # Information Disclosure
        self.register(VulnerabilityPattern(
            name="info_disclosure",
            description="Sensitive information disclosure",
            tags=["info-disclosure", "exposure", "sensitive"],
            severity="medium",
            matchers=[
                Matcher(
                    type=MatcherType.REGEX,
                    part="body",
                    regex=[
                        "api[_-]?key\\s*[:=]\\s*['\"][a-zA-Z0-9]{16,}['\"]",
                        "password\\s*[:=]\\s*['\"][^'\"]{4,}['\"]",
                        "secret\\s*[:=]\\s*['\"][a-zA-Z0-9]{16,}['\"]",
                        "-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
                        "AKIA[0-9A-Z]{16}",  # AWS Access Key
                        "ghp_[a-zA-Z0-9]{36}",  # GitHub Token
                        "glpat-[a-zA-Z0-9\\-]{20}"  # GitLab Token
                    ],
                    condition="or"
                )
            ],
            extractors=[
                Extractor(
                    type=ExtractorType.REGEX,
                    name="api_key",
                    part="body",
                    regex=["[aA][pP][iI][_-]?[kK][eE][yY]\\s*[:=]\\s*['\"]([a-zA-Z0-9]{16,})['\"]"]
                )
            ]
        ))
        
        # Default Credentials
        self.register(VulnerabilityPattern(
            name="default_creds",
            description="Default credentials detection",
            tags=["default-creds", "auth", "weak-credentials"],
            severity="critical",
            matchers=[
                Matcher(
                    type=MatcherType.STATUS,
                    status=[200, 302]
                ),
                Matcher(
                    type=MatcherType.WORD,
                    part="body",
                    words=["dashboard", "admin", "welcome", "profile", "logout"],
                    condition="and"
                )
            ]
        ))
