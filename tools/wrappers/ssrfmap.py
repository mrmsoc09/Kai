"""
SSRFMap Wrapper
Server-Side Request Forgery detection tool.
"""
import subprocess
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class SSRFMapAgent:
    """Agent for SSRF testing using SSRFmap."""

    def __init__(self):
        self.name = 'ssrfmap'
        self.category = 'ssrf_scanning'
        self.tier = 1

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute SSRFMap scan against target."""
        options = options or {}

        cmd = ['python3', '/usr/share/ssrfmap/ssrfmap.py', '-u', target]

        # Method
        if options.get('method'):
            cmd.extend(['-m', options['method']])

        # Data
        if options.get('data'):
            cmd.extend(['-d', options['data']])

        # Cookie
        if options.get('cookie'):
            cmd.extend(['-c', options['cookie']])

        # Level
        cmd.extend(['-l', str(options.get('level', 2))])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=options.get('timeout', 600))
            findings = self._parse_output(result.stdout, result.stderr)

            return {
                'target': target, 'tool': self.name,
                'command': ' '.join(cmd), 'return_code': result.returncode,
                'findings': findings, 'timestamp': datetime.now().isoformat(),
                'success': len(findings) > 0
            }
        except Exception as e:
            return {
                'target': target, 'tool': self.name, 'error': str(e),
                'findings': [], 'timestamp': datetime.now().isoformat(), 'success': False
            }

    def _parse_output(self, stdout: str, stderr: str) -> List[Dict]:
        """Parse SSRFMap output."""
        findings = []
        combined = stdout + stderr

        if 'ssrf' in combined.lower() or 'callback' in combined.lower():
            findings.append({
                'type': 'ssrf', 'severity': 'high',
                'title': 'Server-Side Request Forgery',
                'description': 'SSRF vector detected',
                'engine': self.name, 'evidence': stdout[:1500]
            })
        return findings
