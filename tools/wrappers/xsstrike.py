"""
XSStrike Wrapper
XSS detection - secondary to Dalfox for redundancy.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class XSStrikeAgent:
    """Agent for XSS detection using XSStrike."""

    def __init__(self):
        self.name = 'xsstrike'
        self.category = 'xss_scanning'
        self.tier = 1
        self.description = 'XSS scanner - multi-context analysis'

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute XSStrike scan against target."""
        options = options or {}
        cmd = ['xsstrike', '-u', target]

        if options.get('crawl'):
            cmd.append('--crawl')
        cmd.extend(['--threads', str(options.get('threads', 10))])

        if options.get('level'):
            cmd.extend(['--level', str(options['level'])])
        if options.get('blind_url'):
            cmd.extend(['--blind', options['blind_url']])
        if options.get('cookie'):
            cmd.extend(['--cookie', options['cookie']])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=options.get('timeout', 600))
            findings = self._parse_output(result.stdout, result.stderr)

            return {
                'target': target, 'tool': self.name,
                'command': ' '.join(cmd), 'return_code': result.returncode,
                'findings': findings, 'raw_output': result.stdout,
                'timestamp': datetime.now().isoformat(), 'success': len(findings) > 0
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
            if 'Vulnerable' in line or 'Vulnerability' in line or 'Reflected' in line:
                findings.append({
                    'type': 'cross_site_scripting', 'severity': 'high',
                    'title': 'XSS Detected', 'description': line.strip(),
                    'engine': self.name, 'evidence': stdout[:1500]
                })
        return findings
