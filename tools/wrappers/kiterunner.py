"""
Kiterunner Wrapper
api_security_scanning - Tier 2 tool.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class KiterunnerAgent:
    """Agent for api_security_scanning using kiterunner."""

    def __init__(self):
        self.name = 'kiterunner'
        self.category = 'api_security_scanning'
        self.tier = 2

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute kiterunner scan against target."""
        options = options or {}
        cmd = ['kr', 'scan', '-u', target]

        # Add timeout and other options
        timeout = options.get('timeout', 600)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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
        for line in stdout.split('\n'):
            if 'api' in stdout.lower() or 'endpoint' in stdout.lower():
                findings.append({'type': 'api_discovery', 'severity': 'info', 'description': 'API endpoint found'})
        return findings
