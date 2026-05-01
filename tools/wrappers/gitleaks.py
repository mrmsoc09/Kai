"""Gitleaks wrapper - detect secrets in git repos."""
import subprocess, json
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class GitleaksResult:
    success: bool
    leaks: List[Dict] = field(default_factory=list)
    total: int = 0
    errors: List[str] = field(default_factory=list)

class GitleaksTool:
    @staticmethod
    def check() -> bool:
        try: return subprocess.run(['which','gitleaks'], capture_output=True).returncode == 0
        except: return False
    
    @classmethod
    async def scan(cls, repo_path: str) -> GitleaksResult:
        if not cls.check():
            return GitleaksResult(success=False, errors=["gitleaks not installed"])
        cmd = ['gitleaks', 'detect', '-s', repo_path, '-f', 'json', '-r', '/dev/stdout']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            leaks = json.loads(r.stdout) if r.stdout.strip() else []
            return GitleaksResult(success=True, leaks=leaks, total=len(leaks))
        except Exception as e:
            return GitleaksResult(success=False, errors=[str(e)])
