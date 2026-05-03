"""
CspEvaluator Wrapper
csp_analysis - Tier 3 tool.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class CspEvaluatorAgent:
    """Agent for csp_analysis using csp_evaluator."""

    def __init__(self):
        self.name = 'csp_evaluator'
        self.category = 'csp_analysis'
        self.tier = 3

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute csp_evaluator scan against target."""
        options = options or {}
        cmd = ['csp-evaluator', '-u', target]

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
            if 'bypass' in stdout.lower() or 'weak' in stdout.lower():
                findings.append({'type': 'csp_weakness', 'severity': 'medium', 'description': 'CSP weakness found'})
        return findings
