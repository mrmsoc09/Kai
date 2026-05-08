"""
SQLMap Wrapper
Primary SQL injection detection and exploitation tool.
"""
import os
import subprocess
import sys
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Allow importing the shared validator framework from the backend source tree.
_backend_src = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend", "src")
)
if _backend_src not in sys.path:
    sys.path.insert(0, _backend_src)

from core.tool_adapters.validators import validate_tool_options  # noqa: E402

class SQLMapAgent:
    """Agent for SQL injection testing using SQLMap."""

    def __init__(self):
        self.name = 'sqlmap'
        self.category = 'sql_injection_scanning'
        self.tier = 1

    def scan(self, target: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute SQLMap scan against target."""
        options = dict(options or {})

        # Validate all caller-supplied arguments (including the target URL) before
        # constructing the command. Raises ValueError on any invalid input.
        options["target"] = target
        try:
            options = validate_tool_options("sqlmap", options)
        except ValueError as exc:
            return {
                "target": target, "tool": self.name, "error": str(exc),
                "findings": [], "timestamp": datetime.now().isoformat(), "success": False,
            }
        target = options.pop("target")

        cmd = ['sqlmap', '-u', target, '--batch', '--flush-session']

        # Level (1-5, higher = more thorough; already validated)
        cmd.extend(['--level', str(options.get('level', 3))])

        # Risk (1-3, higher = more dangerous tests; already validated)
        cmd.extend(['--risk', str(options.get('risk', 1))])

        # Threads (already validated)
        cmd.extend(['--threads', str(options.get('threads', 10))])

        # Output format
        cmd.extend(['--json-output', '/tmp/sqlmap_out.json'])

        # Cookie (already validated; safe to append directly)
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
