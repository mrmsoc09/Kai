"""DalFox wrapper - XSS scanner."""
import subprocess, json
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class DalfoxResult:
    success: bool
    xss_findings: List[Dict] = field(default_factory=list)
    total: int = 0
    errors: List[str] = field(default_factory=list)

class DalfoxTool:
    @staticmethod
    def check() -> bool:
        try: return subprocess.run(['which','dalfox'], capture_output=True).returncode == 0
        except: return False
    
    @classmethod
    async def scan(cls, url: str) -> DalfoxResult:
        if not cls.check():
            return DalfoxResult(success=False, errors=["dalfox not installed"])
        cmd = ['dalfox', 'url', url, '--format', 'json']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            findings = [json.loads(l) for l in r.stdout.strip().split('\n') if l.strip() and l.startswith('{')]
            return DalfoxResult(success=True, xss_findings=findings, total=len(findings))
        except Exception as e:
            return DalfoxResult(success=False, errors=[str(e)])
