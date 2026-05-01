"""FFuf wrapper for fuzzing and content discovery."""
import subprocess, json, tempfile, os
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class FfufResult:
    success: bool
    results: List[Dict] = field(default_factory=list)
    total_found: int = 0
    errors: List[str] = field(default_factory=list)

class FfufTool:
    @staticmethod
    def check() -> bool:
        try: return subprocess.run(['which','ffuf'], capture_output=True).returncode == 0
        except: return False
    
    @classmethod
    async def scan(cls, url: str, wordlist: str, extensions: str = "", 
                   threads: int = 40, method: str = "GET") -> FfufResult:
        if not cls.check():
            return FfufResult(success=False, errors=["ffuf not installed"])
        
        cmd = ['ffuf', '-u', url.replace('FUZZ','{}').format('FUZZ'), 
               '-w', wordlist, '-t', str(threads), '-X', method, '-o', '/dev/stdout', '-of', 'json']
        if extensions:
            cmd.extend(['-e', extensions])
        
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            data = json.loads(r.stdout)
            results = [{'url': x['url'], 'status': x['status'], 'size': x['length']} 
                      for x in data.get('results', [])]
            return FfufResult(success=True, results=results, total_found=len(results))
        except Exception as e:
            return FfufResult(success=False, errors=[str(e)])
