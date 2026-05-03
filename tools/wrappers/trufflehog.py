"""TruffleHog wrapper - detect secrets in code."""
import subprocess, json
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class TrufflehogResult:
    success: bool
    secrets: List[Dict] = field(default_factory=list)
    total: int = 0
    errors: List[str] = field(default_factory=list)

class TrufflehogTool:
    @staticmethod
    def check() -> bool:
        try: return subprocess.run(['which','trufflehog'], capture_output=True).returncode == 0
        except: return False
    
    @classmethod
    async def scan(cls, repo_path: str, branch: str = "main") -> TrufflehogResult:
        if not cls.check():
            return TrufflehogResult(success=False, errors=["trufflehog not installed"])
        cmd = ['trufflehog', 'filesystem', repo_path, '--branch', branch, '--json']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            secrets = [json.loads(l) for l in r.stdout.strip().split('\n') if l.strip()]
            return TrufflehogResult(success=True, secrets=secrets, total=len(secrets))
        except Exception as e:
            return TrufflehogResult(success=False, errors=[str(e)])
