"""Gitleaks wrapper - detect secrets in git repos."""
import os
import time
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

        output_dir = os.environ.get(
            "GITLEAKS_OUTPUT_DIR",
            os.environ.get("K1_GITLEAKS_OUTPUT_DIR", "/tmp/gitleaks-output")
        )
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"gitleaks_{int(time.time())}.json")

        cmd = ['gitleaks', 'detect', '-s', repo_path, '-f', 'json', '-r', output_file]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode not in (0, 1):
                return GitleaksResult(
                    success=False,
                    errors=[f"gitleaks exited with code {r.returncode}", r.stderr.strip()]
                )
            with open(output_file, encoding="utf-8") as handle:
                leaks = json.load(handle)
            return GitleaksResult(success=True, leaks=leaks, total=len(leaks))
        except Exception as e:
            return GitleaksResult(success=False, errors=[str(e)])
