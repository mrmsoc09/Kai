"""Nikto wrapper - web vulnerability scanner."""
import subprocess, json
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class NiktoResult:
    success: bool
    findings: List[Dict] = field(default_factory=list)
    total: int = 0
    errors: List[str] = field(default_factory=list)

class NiktoTool:
    @staticmethod
    def check() -> bool:
        try: return subprocess.run(['which','nikto'], capture_output=True).returncode == 0
        except: return False
    
    @classmethod
    async def scan(cls, url: str) -> NiktoResult:
        if not cls.check():
            return NiktoResult(success=False, errors=["nikto not installed"])
        cmd = ['nikto', '-h', url, '-Format', 'json', '-o', '/dev/stdout']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            data = json.loads(r.stdout) if r.stdout.strip() else {}
            findings = data.get('vulnerabilities', [])
            return NiktoResult(success=True, findings=findings, total=len(findings))
        except Exception as e:
            return NiktoResult(success=False, errors=[str(e)])
