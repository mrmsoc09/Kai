"""
Fuxploider Wrapper
File upload vulnerability testing - tier 2 business logic.
"""
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime

class FuxploiderAgent:
    """Agent for file upload security testing."""

    def __init__(self):
        self.name = 'fuxploider'
        self.category = 'file_upload_testing'
        self.tier = 2
        self.description = 'File upload bypass and exploitation tool'

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Test file upload endpoint for vulnerabilities."""
        options = options or {}
        cmd = ['python3', '/usr/share/fuxploider/fuxploider.py', '--url', target]

        if options.get('method'):
            cmd.extend(['--method', options['method'].upper()])
        if options.get('field'):
            cmd.extend(['--field', options['field']])

        extensions = options.get('extensions', ['php', 'phar', 'html', 'txt', 'jpg'])
        cmd.extend(['--extensions', ','.join(extensions)])

        if options.get('test_file'):
            cmd.extend(['--file', options['test_file']])
        if options.get('shell_check'):
            cmd.append('--shell-check')
        if options.get('shell_path'):
            cmd.extend(['--shell-path', options['shell_path']])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=options.get('timeout', 600))
            findings = self._parse_output(result.stdout, result.stderr, target)

            return {
                'target': target, 'tool': self.name,
                'command': ' '.join(cmd[:-2]) + ' [MASKED]',
                'return_code': result.returncode, 'findings': findings,
                'raw_output': result.stdout, 'timestamp': datetime.now().isoformat(),
                'success': len(findings) > 0
            }
        except subprocess.TimeoutExpired:
            return {'target': target, 'tool': self.name, 'error': 'Scan timeout',
                   'findings': [], 'timestamp': datetime.now().isoformat(), 'success': False}
        except Exception as e:
            return {'target': target, 'tool': self.name, 'error': str(e),
                   'findings': [], 'timestamp': datetime.now().isoformat(), 'success': False}

    def _parse_output(self, stdout: str, stderr: str, target: str) -> List[Dict]:
        findings = []
        for line in stdout.split('\n'):
            if 'Success' in line or 'bypass' in line.lower() or 'uploaded' in line.lower():
                findings.append({
                    'type': 'file_upload_bypass',
                    'severity': 'critical' if 'shell' in line.lower() or 'rce' in line.lower() else 'high',
                    'target': target, 'title': 'File Upload Restriction Bypass',
                    'description': line.strip(), 'engine': self.name,
                    'impact': 'May allow remote code execution via web shell',
                    'evidence': stdout[:2000]
                })
            if 'Double extension' in line or 'extension bypass' in line.lower():
                findings.append({
                    'type': 'file_upload_extension_bypass', 'severity': 'high',
                    'target': target, 'title': 'File Extension Bypass',
                    'description': 'Server accepts double or alternate extensions',
                    'engine': self.name
                })
        return findings
