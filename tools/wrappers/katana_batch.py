"""
Katana Batch Crawler
High-speed web crawler for JavaScript discovery and link extraction.
"""
from typing import List, Dict, Optional
import subprocess
import json
from datetime import datetime

try:
    from .batch_mixin import BatchScanMixin
except ImportError:
    from batch_mixin import BatchScanMixin

class KatanaBatchScanner(BatchScanMixin):
    """
    Parallel JavaScript and endpoint crawling across multiple targets.
    """

    def __init__(self, max_workers: int = 6):
        super().__init__(max_workers=max_workers)
        self.tool_name = 'katana'
        self.category = 'Content Discovery'

    def scan_single(
        self,
        target: str,
        ports: Optional[List[int]] = None,
        options: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """
        Single target crawl execution.
        """
        options = options or {}

        # Build katana command
        cmd = ['katana', '-u', target]

        # Crawl depth
        cmd.extend(['-d', str(options.get('depth', 3))])

        # Concurrency
        cmd.extend(['-c', str(options.get('concurrency', 10))])

        # Parallelism
        cmd.extend(['-p', str(options.get('parallelism', 10))])

        # JavaScript parsing
        if options.get('js_parse', True):
            cmd.append('-jc')

        # Endpoint extraction
        if options.get('endpoints', True):
            cmd.append('-ef')

        # Field detection
        if options.get('field_scope', True):
            cmd.append('-fs')

        # Output format (JSON)
        cmd.extend(['-j', '-o', '-'])

        # Timeout
        timeout = options.get('timeout', 180)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                'target': target,
                'command': ' '.join(cmd),
                'raw_output': result.stdout,
                'findings': self._parse_katana_json(result.stdout),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'target': target, 'error': str(e), 'findings': []}

    def _parse_katana_json(self, json_output: str) -> List[Dict]:
        """Parse katana JSON lines output."""
        findings = []
        for line in json_output.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                findings.append({
                    'type': 'crawled_endpoint',
                    'severity': 'info',
                    'url': data.get('url', ''),
                    'source': data.get('source', ''),
                    'tag': data.get('tag', ''),
                    'attribute': data.get('attribute', ''),
                    'description': f"Discovered: {data.get('url')}"
                })
            except json.JSONDecodeError:
                continue
        return findings

    def extract_js_endpoints(
        self,
        targets: List[str],
        depth: int = 3
    ) -> Dict[str, List[str]]:
        """
        Extract JavaScript endpoints from multiple targets.

        Returns:
            Dict mapping target to discovered JS endpoints
        """
        options = {
            'depth': depth,
            'js_parse': True,
            'endpoints': True,
            'timeout': 300
        }

        results = self.scan_batch(targets, options=options)

        # Organize by target
        endpoints_by_target = {}
        for r in results:
            if r['success']:
                target = r['target']
                endpoints = [f['url'] for f in r['results'].get('findings', [])]
                endpoints_by_target[target] = endpoints

        return endpoints_by_target

# Convenience function
def batch_crawl(targets: List[str], depth: int = 2) -> List[Dict]:
    """Quick parallel crawl of multiple targets."""
    scanner = KatanaBatchScanner()
    return scanner.scan_batch(targets, options={'depth': depth, 'js_parse': True})

if __name__ == '__main__':
    scanner = KatanaBatchScanner()
    results = scanner.extract_js_endpoints(['http://testphp.vulnweb.com'])
    for target, endpoints in results.items():
        print(f"{target}: {len(endpoints)} endpoints")
