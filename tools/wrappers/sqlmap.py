"""
SQLMap Wrapper
Primary SQL injection detection and exploitation tool.
"""
import subprocess
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class SQLMapAgent:
    """Agent for SQL injection testing using SQLMap."""

    def __init__(self):
        self.name = 'sqlmap'
        self.category = 'sql_injection_scanning'
        self.tier = 1

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute SQLMap scan against target."""
        options = options or {}

        cmd = ['sqlmap', '-u', target, '--batch', '--flush-session']

        # Level (1-5, higher = more thorough)
        cmd.extend(['--level', str(options.get('level', 3))])

        # Risk (1-3, higher = more dangerous tests)
        cmd.extend(['--risk', str(options.get('risk', 1))])

        # Threads
        cmd.extend(['--threads', str(options.get('threads', 10))])

        # Output format
        cmd.extend(['--json-output', '/tmp/sqlmap_out.json'])

        # Cookie
        if options.get('cookie'):
            cmd.extend(['--cookie', options['cookie']])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=options.get('timeout', 1800))
            findings = self._parse_output(result.stdout + result.stderr)

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

    def _parse_output(self, output: str) -> List[Dict]:
        """Parse SQLMap output."""
        findings = []
        if 'is vulnerable' in output.lower() or 'sql injection' in output.lower():
            findings.append({
                'type': 'sql_injection', 'severity': 'critical',
                'title': 'SQL Injection (SQLMap)', 'description': output[:2000],
                'engine': self.name
            })
        return findings
