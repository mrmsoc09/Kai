"""
JWT_Tool Wrapper
JWT security testing - tier 2 authentication testing.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class JWTToolAgent:
    """Agent for JWT security testing."""

    def __init__(self):
        self.name = 'jwt_tool'
        self.category = 'jwt_security_testing'
        self.tier = 2
        self.description = 'JWT token security analyzer'

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze JWT token or endpoint for vulnerabilities."""
        options = options or {}
        if target.startswith('http'):
            return self._test_endpoint(target, options)
        else:
            return self._test_token(target, options)

    def _test_token(self, token: str, options: Dict) -> Dict:
        cmd = ['jwt_tool', token]
        if options.get('crack'):
            cmd.append('-C')
        if options.get('decode'):
            cmd.extend(['-d', '-S'])
        if options.get('tamper'):
            cmd.append('-X')

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=options.get('timeout', 300))
            findings = self._parse_token_output(result.stdout, result.stderr)

            return {
                'target': token[:50] + '...', 'tool': self.name,
                'command': 'jwt_tool <token>', 'mode': 'token_analyze',
                'findings': findings, 'timestamp': datetime.now().isoformat(),
                'success': len(findings) > 0
            }
        except Exception as e:
            return {'target': token[:50] + '...', 'tool': self.name,
                   'error': str(e), 'findings': [],
                   'timestamp': datetime.now().isoformat(), 'success': False}

    def _test_endpoint(self, endpoint: str, options: Dict) -> Dict:
        cmd = ['jwt_tool', '-u', endpoint]
        if options.get('nested_jwt'):
            cmd.append('-nj')

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=options.get('timeout', 600))
            findings = self._parse_endpoint_output(result.stdout, result.stderr)

            return {
                'target': endpoint, 'tool': self.name,
                'command': ' '.join(cmd), 'mode': 'endpoint_test',
                'findings': findings, 'timestamp': datetime.now().isoformat(),
                'success': len(findings) > 0
            }
        except Exception as e:
            return {'target': endpoint, 'tool': self.name, 'error': str(e),
                   'findings': [], 'timestamp': datetime.now().isoformat(), 'success': False}

    def _parse_token_output(self, stdout: str, stderr: str) -> List[Dict]:
        findings = []
        if 'None algorithm' in stdout or 'alg: none' in stdout.lower():
            findings.append({
                'type': 'jwt_none_algorithm', 'severity': 'critical',
                'title': 'JWT None Algorithm Vulnerability',
                'description': 'Token accepts none algorithm allowing signature bypass',
                'remediation': 'Reject tokens with none algorithm'
            })
        if 'Weak secret' in stdout or 'Cracked' in stdout:
            findings.append({
                'type': 'jwt_weak_secret', 'severity': 'high',
                'title': 'JWT Weak Secret',
                'description': 'Token uses weak or common signing secret',
                'remediation': 'Use strong (32+ char) random secrets'
            })
        return findings

    def _parse_endpoint_output(self, stdout: str, stderr: str) -> List[Dict]:
        findings = []
        if 'Vulnerable' in stdout:
            findings.append({
                'type': 'jwt_endpoint_vulnerable', 'severity': 'high',
                'title': 'JWT Endpoint Vulnerability',
                'description': 'JWT implementation shows security weaknesses',
                'evidence': stderr[:1000]
            })
        return findings
