"""Feroxbuster wrapper for content discovery."""
import subprocess, json
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class FeroxResult:
    success: bool
    urls: List[str] = field(default_factory=list)
    total: int = 0
    errors: List[str] = field(default_factory=list)

class FeroxTool:
    @staticmethod
    def check() -> bool:
        try: return subprocess.run(['which','feroxbuster'], capture_output=True).returncode == 0
        except: return False
    
    @classmethod
    async def scan(cls, url: str, wordlist: str, extensions: str = "php,html,txt") -> FeroxResult:
        if not cls.check():
            return FeroxResult(success=False, errors=["feroxbuster not installed"])
        
        cmd = ['feroxbuster', '-u', url, '-w', wordlist, '-x', extensions, 
               '--json', '-q', '--no-recursion']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            urls = []
            for line in r.stdout.split('\n'):
                if line.strip():
                    try: urls.append(json.loads(line).get('url'))
                    except: pass
            return FeroxResult(success=True, urls=urls, total=len(urls))
        except Exception as e:
            return FeroxResult(success=False, errors=[str(e)])
