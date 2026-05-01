"""
Arjun Wrapper
parameter_discovery - Tier 1 essential tool.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class ArjunAgent:
    """Agent for parameter_discovery using arjun."""

    def __init__(self):
        self.name = 'arjun'
        self.category = 'parameter_discovery'
        self.tier = 1

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute arjun scan against target."""
        options = options or {}
        cmd = ['arjun', '-u', target, '-oJ', '/dev/stdout']

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
            for param in data.get('params', []):
                findings.append({'type': 'discovered_param', 'name': param, 'severity': 'info'})
        except:
            pass
        return findings
