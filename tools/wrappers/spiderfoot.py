"""
Spiderfoot Wrapper
osint_intelligence - Tier 1 essential tool.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class SpiderfootAgent:
    """Agent for osint_intelligence using spiderfoot."""

    def __init__(self):
        self.name = 'spiderfoot'
        self.category = 'osint_intelligence'
        self.tier = 1

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute spiderfoot scan against target."""
        options = options or {}
        cmd = ['spiderfoot', '-s', target, '-o', 'json']

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=options.get('timeout', 600))
            findings = self._parse_output(result.stdout, result.stderr)

            return {
                'target': target, 'tool': self.name,
                'command': ' '.join(cmd), 'findings': findings,
                'timestamp': datetime.now().isoformat(),
                'success': len(findings) > 0 or result.returncode == 0
            }
        except Exception as e:
            return {
                'target': target, 'tool': self.name, 'error': str(e),
                'findings': [], 'timestamp': datetime.now().isoformat(), 'success': False
            }

    def _parse_output(self, stdout: str, stderr: str) -> List[Dict]:
        findings = []
        try:
            import json
            data = json.loads(stdout)
            for item in data.get('data', []):
                findings.append({'type': item.get('type'), 'data': item.get('data'), 'severity': 'info'})
        except:
            pass
        return findings
