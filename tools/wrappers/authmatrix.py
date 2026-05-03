"""
Authmatrix Wrapper
authorization_testing - Tier 2 tool.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class AuthmatrixAgent:
    """Agent for authorization_testing using authmatrix."""

    def __init__(self):
        self.name = 'authmatrix'
        self.category = 'authorization_testing'
        self.tier = 2

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute authmatrix scan against target."""
        options = options or {}
        cmd = ['python3', '/usr/share/authmatrix/AuthMatrix.py', '-t', target]

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
            if 'idor' in stdout.lower() or 'access' in stdout.lower():
                findings.append({'type': 'idor', 'severity': 'critical', 'description': 'IDOR vulnerability found'})
        return findings
