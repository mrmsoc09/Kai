"""
Naabu Wrapper
network_port_scanning - Tier 1 essential tool.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class NaabuAgent:
    """Agent for network_port_scanning using naabu."""

    def __init__(self):
        self.name = 'naabu'
        self.category = 'network_port_scanning'
        self.tier = 1

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute naabu scan against target."""
        options = options or {}
        cmd = ['naabu', '-host', target, '-silent']

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
        for line in stdout.split('\n'):
            if ':' in line:
                host, port = line.split(':')
                findings.append({'type': 'open_port', 'host': host, 'port': port, 'severity': 'info'})
        return findings
