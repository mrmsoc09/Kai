"""
Burp Community File Bridge

Watches for Burp Suite Community Edition export files (via Logger++ BApp)
and ingests them into the KaisonOne platform for AI analysis.

Since Burp Community lacks a REST API, this uses file-system polling:
1. Burp Logger++ exports findings to a watched directory every N seconds
2. This bridge detects new files and parses them
3. Findings are normalized to KaisonOne format
4. CAI can analyze traffic patterns and suggest next actions

Setup:
1. Install Logger++ BApp in Burp Community
2. Configure Logger++ to auto-export to: output/burp_exports/
3. This bridge watches that directory and processes exports
"""

import asyncio
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent


@dataclass
class BurpFinding:
    """Normalized Burp Suite finding."""
    tool: str = "burp_community"
    url: str = ""
    host: str = ""
    port: int = 443
    protocol: str = "https"
    severity: str = "info"  # critical, high, medium, low, info
    confidence: str = "certain"  # certain, firm, tentative
    issue_name: str = ""
    issue_type: str = ""
    description: str = ""
    remediation: str = ""
    request: bytes = b""
    response: bytes = b""
    parameter: str = ""
    path: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def signature(self) -> str:
        """Unique identifier for deduplication."""
        key = f"{self.url}:{self.issue_name}:{self.parameter}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "tool": self.tool,
            "url": self.url,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "severity": self.severity,
            "confidence": self.confidence,
            "issue_name": self.issue_name,
            "issue_type": self.issue_type,
            "description": self.description,
            "remediation": self.remediation,
            "request_b64": self._bytes_to_b64(self.request),
            "response_b64": self._bytes_to_b64(self.response),
            "parameter": self.parameter,
            "path": self.path,
            "timestamp": self.timestamp,
            "signature": self.signature
        }
    
    @staticmethod
    def _bytes_to_b64(data: bytes) -> str:
        import base64
        return base64.b64encode(data).decode() if data else ""


class BurpExportParser:
    """Parser for Burp Suite export formats (XML, JSON)."""
    
    @staticmethod
    def parse_xml(file_path: Path) -> List[BurpFinding]:
        """Parse Burp XML export (from Logger++ or manual export)."""
        findings = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Burp issues are in <issue> elements
            for issue in root.findall('.//issue'):
                finding = BurpFinding()
                
                # Extract basic fields
                finding.url = BurpExportParser._get_text(issue, 'url')
                finding.host = BurpExportParser._get_text(issue, 'host')
                finding.port = int(BurpExportParser._get_text(issue, 'port', '443'))
                finding.protocol = BurpExportParser._get_text(issue, 'protocol', 'https')
                finding.severity = BurpExportParser._get_text(issue, 'severity', 'info').lower()
                finding.confidence = BurpExportParser._get_text(issue, 'confidence', 'certain').lower()
                finding.issue_name = BurpExportParser._get_text(issue, 'name')
                finding.issue_type = BurpExportParser._get_text(issue, 'type')
                finding.description = BurpExportParser._get_text(issue, 'issueBackground')
                finding.remediation = BurpExportParser._get_text(issue, 'remediationBackground')
                
                # Extract request/response
                request_elem = issue.find('requestresponse/request')
                if request_elem is not None:
                    finding.request = BurpExportParser._get_bytes(request_elem)
                
                response_elem = issue.find('requestresponse/response')
                if response_elem is not None:
                    finding.response = BurpExportParser._get_bytes(response_elem)
                
                # Extract parameter if present
                finding.parameter = BurpExportParser._get_text(issue, 'location')
                
                findings.append(finding)
                
        except ET.ParseError as e:
            print(f"[Burp Bridge] XML parse error: {e}")
        except Exception as e:
            print(f"[Burp Bridge] Error parsing {file_path}: {e}")
        
        return findings
    
    @staticmethod
    def parse_json(file_path: Path) -> List[BurpFinding]:
        """Parse JSON export format."""
        findings = []
        
        try:
            data = json.loads(file_path.read_text())
            
            # Handle Logger++ JSON format
            issues = data.get('issues', data.get('findings', []))
            
            for issue in issues:
                finding = BurpFinding()
                finding.url = issue.get('url', '')
                finding.host = issue.get('host', '')
                finding.port = issue.get('port', 443)
                finding.protocol = issue.get('protocol', 'https')
                finding.severity = issue.get('severity', 'info').lower()
                finding.confidence = issue.get('confidence', 'certain').lower()
                finding.issue_name = issue.get('name', issue.get('issue_name', ''))
                finding.issue_type = issue.get('type', '')
                finding.description = issue.get('description', '')
                finding.remediation = issue.get('remediation', '')
                finding.parameter = issue.get('parameter', issue.get('location', ''))
                
                # Decode base64 request/response
                import base64
                req_b64 = issue.get('request', issue.get('request_base64', ''))
                if req_b64:
                    finding.request = base64.b64decode(req_b64)
                
                resp_b64 = issue.get('response', issue.get('response_base64', ''))
                if resp_b64:
                    finding.response = base64.b64decode(resp_b64)
                
                findings.append(finding)
                
        except json.JSONDecodeError as e:
            print(f"[Burp Bridge] JSON parse error: {e}")
        except Exception as e:
            print(f"[Burp Bridge] Error parsing {file_path}: {e}")
        
        return findings
    
    @staticmethod
    def _get_text(element, tag: str, default: str = '') -> str:
        """Safely extract text from XML element."""
        elem = element.find(tag)
        return elem.text if elem is not None else default
    
    @staticmethod
    def _get_bytes(element) -> bytes:
        """Extract bytes from XML element, handling base64."""
        import base64
        text = element.text or ''
        # Burp stores requests/responses base64 encoded in CDATA
        if element.get('base64') == 'true':
            return base64.b64decode(text)
        return text.encode()


class BurpCommunityBridge(FileSystemEventHandler):
    """
    Watches for Burp Community exports and processes them.
    
    Usage:
        bridge = BurpCommunityBridge(watch_dir="output/burp_exports")
        bridge.start()
        # ... run Burp scans
        findings = bridge.get_processed_findings()
        bridge.stop()
    """
    
    def __init__(
        self,
        watch_dir: str = "output/burp_exports",
        processed_dir: str = "output/burp_exports/processed",
        callback: Optional[Callable[[List[BurpFinding]], None]] = None
    ):
        self.watch_dir = Path(watch_dir)
        self.processed_dir = Path(processed_dir)
        self.callback = callback
        self.observer: Optional[Observer] = None
        self.all_findings: List[BurpFinding] = []
        self.seen_signatures: set = set()
        self._running = False
        
        # Ensure directories exist
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start watching for Burp export files."""
        self._running = True
        self.observer = Observer()
        self.observer.schedule(self, str(self.watch_dir), recursive=False)
        self.observer.start()
        print(f"[Burp Bridge] Started watching: {self.watch_dir}")
        
        # Process any existing files
        self._process_existing_files()
    
    def stop(self):
        """Stop watching and cleanup."""
        self._running = False
        if self.observer:
            self.observer.stop()
            self.observer.join()
        print(f"[Burp Bridge] Stopped")
    
    def on_created(self, event):
        """Handle new file creation."""
        if not event.is_directory:
            self._process_file(Path(event.src_path))
    
    def _process_existing_files(self):
        """Process any files already in the watch directory."""
        for file_path in self.watch_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('processed_'):
                self._process_file(file_path)
    
    def _process_file(self, file_path: Path):
        """Parse and process a single export file."""
        print(f"[Burp Bridge] Processing: {file_path.name}")
        
        findings = []
        
        # Determine format and parse
        suffix = file_path.suffix.lower()
        try:
            if suffix == '.xml':
                findings = BurpExportParser.parse_xml(file_path)
            elif suffix in ['.json', '.burp_export']:
                findings = BurpExportParser.parse_json(file_path)
            else:
                print(f"[Burp Bridge] Unknown format: {suffix}")
                return
        except Exception as e:
            print(f"[Burp Bridge] Failed to parse {file_path}: {e}")
            return
        
        # Deduplicate
        new_findings = []
        for finding in findings:
            if finding.signature not in self.seen_signatures:
                self.seen_signatures.add(finding.signature)
                new_findings.append(finding)
        
        if new_findings:
            print(f"[Burp Bridge] {len(new_findings)} new findings ({len(findings)} total)")
            self.all_findings.extend(new_findings)
            
            # Save to normalized output
            self._save_findings(new_findings)
            
            # Notify callback if registered
            if self.callback:
                try:
                    self.callback(new_findings)
                except Exception as e:
                    print(f"[Burp Bridge] Callback error: {e}")
        
        # Move to processed directory
        processed_name = f"processed_{int(time.time())}_{file_path.name}"
        try:
            file_path.rename(self.processed_dir / processed_name)
        except Exception as e:
            print(f"[Burp Bridge] Failed to move file: {e}")
    
    def _save_findings(self, findings: List[BurpFinding]):
        """Save findings to normalized output directory."""
        output_dir = Path("output/normalized/burp_community")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(time.time())
        output_file = output_dir / f"burp_findings_{timestamp}.json"
        
        data = {
            "source": "burp_community",
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(findings),
            "findings": [f.to_dict() for f in findings]
        }
        
        output_file.write_text(json.dumps(data, indent=2))
        print(f"[Burp Bridge] Saved to: {output_file}")
    
    def get_processed_findings(self) -> List[BurpFinding]:
        """Return all processed findings."""
        return self.all_findings.copy()
    
    def get_findings_by_severity(self, severity: str) -> List[BurpFinding]:
        """Filter findings by severity."""
        return [f for f in self.all_findings if f.severity == severity.lower()]
    
    def clear_findings(self):
        """Clear all stored findings."""
        self.all_findings.clear()
        self.seen_signatures.clear()


# Integration with CAI for traffic analysis
class BurpCAIAnalyzer:
    """
    Analyzes Burp findings using CAI and suggests next actions.
    
    This bridges Burp's traffic capture with CAI's reasoning capabilities.
    """
    
    def __init__(self, cai_agent=None):
        self.cai_agent = cai_agent
    
    async def analyze_findings(self, findings: List[BurpFinding], target: str) -> Dict:
        """
        Use CAI to analyze Burp findings and suggest exploitation paths.
        """
        if not findings:
            return {"status": "no_findings"}
        
        # Build analysis prompt
        findings_summary = []
        for f in findings:
            findings_summary.append({
                "type": f.issue_name,
                "severity": f.severity,
                "confidence": f.confidence,
                "url": f.url,
                "parameter": f.parameter,
                "description": f.description[:200] if f.description else ""
            })
        
        context = {
            "burp_findings": findings_summary,
            "target": target,
            "tool": "burp_community"
        }
        
        try:
            from tools.wrappers.cai_autonomous_agent import CAIAutonomousAgent
            
            if not self.cai_agent:
                self.cai_agent = CAIAutonomousAgent()
            
            analysis = await self.cai_agent.execute(
                target=target,
                task="analyze vulnerability findings and suggest next steps",
                context=context,
                scope_config={"target_domains": [target]},
                enable_hil=True,
                timeout=300
            )
            
            return {
                "status": "success",
                "analysis": analysis,
                "suggestions": self._extract_suggestions(analysis)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _extract_suggestions(self, analysis) -> List[Dict]:
        """Extract actionable suggestions from CAI analysis."""
        suggestions = []
        
        for finding in analysis.findings:
            if finding.get("type") == "suggested_action":
                suggestions.append({
                    "action": finding.get("evidence", ""),
                    "confidence": finding.get("confidence", 0.5),
                    "reasoning": finding.get("raw_trace", {})
                })
        
        return suggestions


# Simple CLI test
if __name__ == "__main__":
    print("Burp Community Bridge Test")
    print("=" * 50)
    
    # Create test finding
    test_finding = BurpFinding(
        url="https://example.com/login",
        host="example.com",
        severity="high",
        confidence="firm",
        issue_name="SQL Injection",
        issue_type="sqli",
        description="Parameter 'user' appears vulnerable to SQL injection",
        parameter="user"
    )
    
    print(f"Test finding: {test_finding.to_dict()}")
    print(f"Signature: {test_finding.signature}")
    
    # Test bridge (without actually starting observer)
    bridge = BurpCommunityBridge()
    bridge.all_findings.append(test_finding)
    bridge.seen_signatures.add(test_finding.signature)
    
    print(f"\nStored findings: {len(bridge.get_processed_findings())}")
    print("Bridge ready for integration")
