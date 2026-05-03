"""
Nuclei Wrapper
Primary vulnerability scanner - CVE and misconfiguration detection.
"""
import subprocess
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class NucleiAgent:
    """Agent for vulnerability scanning using Nuclei."""

    def __init__(self):
        self.name = 'nuclei'
        self.category = 'vulnerability_scanning'
        self.tier = 1

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute Nuclei scan against target."""
        options = options or {}

        cmd = ['nuclei', '-u', target, '-json', '-o', '/tmp/nuclei_out.json']

        # Severity filter
        severity = options.get('severity', 'critical,high,medium')
        cmd.extend(['-s', severity])

        # Template tags
        if options.get('tags'):
            cmd.extend(['-tags', options['tags']])

        # Rate limiting
        cmd.extend(['-rl', str(options.get('rate_limit', 100))])

        # Timeout
        timeout = options.get('timeout', 3600)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            findings = self._parse_json_output('/tmp/nuclei_out.json')

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

    def _parse_json_output(self, output_file: str) -> List[Dict]:
        """Parse Nuclei JSON output."""
        findings = []
        try:
            with open(output_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        findings.append({
                            'type': data.get('template-id', 'unknown'),
                            'severity': data.get('info', {}).get('severity', 'unknown'),
                            'title': data.get('info', {}).get('name', 'Unknown'),
                            'description': data.get('info', {}).get('description', ''),
                            'url': data.get('matched-at', ''),
                            'engine': self.name
                        })
        except:
            pass
        return findings
