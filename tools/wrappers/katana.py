"""Katana wrapper for JS crawling and endpoint discovery."""
import subprocess, json
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class KatanaResult:
    success: bool
    endpoints: List[str] = field(default_factory=list)
    js_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

class KatanaTool:
    @staticmethod
    def check() -> bool:
        try: return subprocess.run(['which','katana'], capture_output=True).returncode == 0
        except: return False
    
    @classmethod
    async def crawl(cls, url: str, depth: int = 3, js: bool = True) -> KatanaResult:
        if not cls.check():
            return KatanaResult(success=False, errors=["katana not installed"])
        
        cmd = ['katana', '-u', url, '-d', str(depth), '-c', '10']
        if js: cmd.append('-jc')
        
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            urls = r.stdout.strip().split('\n')
            endpoints = [u for u in urls if u.startswith('http')]
            js_files = [u for u in urls if '.js' in u]
            return KatanaResult(success=True, endpoints=endpoints, js_files=js_files)
        except Exception as e:
            return KatanaResult(success=False, errors=[str(e)])
