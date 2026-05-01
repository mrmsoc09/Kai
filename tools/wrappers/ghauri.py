"""
Ghauri Wrapper
Advanced SQL injection scanner - secondary to SQLMap for redundancy.
"""
import subprocess
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class GhauriAgent:
    """Agent for SQL injection detection using Ghauri."""

    def __init__(self):
        self.name = 'ghauri'
        self.category = 'sql_injection_scanning'
        self.tier = 1
        self.description = 'SQL injection scanner - fast inference-based detection'

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute Ghauri scan against target."""
        options = options or {}

        cmd = ['ghauri', '-u', target, '--batch',
               '--threads', str(options.get('threads', 10))]

        if options.get('level'):
            cmd.extend(['--level', str(options['level'])])
        if options.get('technique'):
            cmd.extend(['--technique', options['technique']])
        if options.get('dbms'):
            cmd.extend(['--dbms', options['dbms']])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=options.get('timeout', 600))
            findings = self._parse_output(result.stdout, result.stderr)

            return {
                'target': target, 'tool': self.name,
                'command': ' '.join(cmd), 'return_code': result.returncode,
                'findings': findings, 'raw_output': result.stdout,
                'timestamp': datetime.now().isoformat(),
                'success': len(findings) > 0 or result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {'target': target, 'tool': self.name, 'error': 'Scan timeout',
                   'findings': [], 'timestamp': datetime.now().isoformat(), 'success': False}
        except Exception as e:
            return {'target': target, 'tool': self.name, 'error': str(e),
                   'findings': [], 'timestamp': datetime.now().isoformat(), 'success': False}

    def _parse_output(self, stdout: str, stderr: str) -> List[Dict]:
        findings = []
        for line in stdout.split('\n'):
            if 'SQL Injection' in line or 'injectable' in line.lower():
                findings.append({
                    'type': 'sql_injection', 'severity': 'high',
                    'title': 'SQL Injection Detected',
                    'description': line.strip(), 'engine': self.name,
                    'evidence': stdout[:2000]
                })
        return findings
