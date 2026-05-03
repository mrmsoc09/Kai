"""
Restler Wrapper
api_fuzzing - Tier 2 tool.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class RestlerAgent:
    """Agent for api_fuzzing using restler."""

    def __init__(self):
        self.name = 'restler'
        self.category = 'api_fuzzing'
        self.tier = 2

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute restler scan against target."""
        options = options or {}
        cmd = ['Restler', 'fuzz', '-s', target]

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
            if 'bug' in stdout.lower() or 'error' in stdout.lower():
                findings.append({'type': 'api_bug', 'severity': 'high', 'description': 'API fuzzing found issue'})
        return findings
