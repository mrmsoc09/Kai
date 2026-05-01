"""
FFUF Batch Directory Fuzzer
High-speed web content discovery with parallel target execution.
"""
from typing import List, Dict, Optional
import subprocess
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

try:
    from .batch_mixin import BatchScanMixin
except ImportError:
    from batch_mixin import BatchScanMixin

class FfufBatchScanner(BatchScanMixin):
    """
    Parallel web fuzzing for multiple targets.
    Optimized for BBP reconnaissance across large scopes.
    """

    def __init__(self, max_workers: int = 8):
        super().__init__(max_workers=max_workers)
        self.tool_name = 'ffuf'
        self.category = 'Content Discovery'

    def scan_single(
        self,
        target: str,
        ports: Optional[List[int]] = None,
        options: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """
        Single URL fuzz - executed in parallel by scan_batch().

        Args:
            target: Full URL to fuzz (e.g., http://target.com/FUZZ)
            options: Fuzzing options including wordlist

        Returns:
            Discovered paths/endpoints
        """
        options = options or {}

        # Build ffuf command
        cmd = ['ffuf', '-u', target, '-mc', '200,204,301,302,307,401,403,405']

        # Wordlist
        wordlist = options.get('wordlist', '/usr/share/wordlists/dirb/common.txt')
        cmd.extend(['-w', wordlist])

        # Threads
        cmd.extend(['-t', str(options.get('threads', 40))])

        # Extensions
        if options.get('extensions'):
            cmd.extend(['-e', ','.join(options['extensions'])])

        # Recursion
        if options.get('recursive'):
            cmd.extend(['-recursion', '-recursion-depth', str(options.get('depth', 2))])

        # Output format (JSON)
        cmd.extend(['-o', '-', '-of', 'json'])

        # Timeout
        timeout = options.get('timeout', 120)

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
                'findings': self._parse_ffuf_json(result.stdout) if result.returncode in [0, 1] else [],
                'timestamp': datetime.now().isoformat()
            }
        except subprocess.TimeoutExpired:
            return {'target': target, 'error': 'Fuzz timeout', 'findings': []}
        except Exception as e:
            return {'target': target, 'error': str(e), 'findings': []}

    def _parse_ffuf_json(self, json_output: str) -> List[Dict]:
        """Parse ffuf JSON output."""
        findings = []
        try:
            data = json.loads(json_output) if json_output.strip() else {'results': []}
            for result in data.get('results', []):
                findings.append({
                    'type': 'discovered_path',
                    'severity': 'info',
                    'url': result.get('url', ''),
                    'status': result.get('status', 0),
                    'size': result.get('length', 0),
                    'words': result.get('words', 0),
                    'lines': result.get('lines', 0),
                    'description': f"Status {result.get('status')} - {result.get('url')}"
                })
        except json.JSONDecodeError:
            pass
        return findings

    def discover_endpoints(
        self,
        base_urls: List[str],
        wordlist: str = '/usr/share/wordlists/dirb/common.txt',
        extensions: Optional[List[str]] = None,
        **kwargs
    ) -> Dict:
        """
        Batch directory discovery across multiple base URLs.

        Returns:
            Discovered endpoints aggregated by URL
        """
        # Prepare FUZZ URLs
        fuzz_urls = [f"{url.rstrip('/')}/FUZZ" for url in base_urls]

        options = {
            'wordlist': wordlist,
            'extensions': extensions or ['.php', '.txt', '.html', '.js', '.json'],
            'threads': 40
        }

        return self.scan_batch_fast(fuzz_urls, options=options)

# Convenience function
def batch_fuzz(targets: List[str], wordlist: str = '/usr/share/wordlists/dirb/common.txt') -> List[Dict]:
    """Quick parallel fuzz of multiple targets."""
    scanner = FfufBatchScanner()
    urls = [f"{t.rstrip('/')}/FUZZ" for t in targets]
    return scanner.scan_batch(urls, options={'wordlist': wordlist})

if __name__ == '__main__':
    scanner = FfufBatchScanner()
    results = scanner.discover_endpoints(['http://testphp.vulnweb.com'])
    print(f"Discovered {results.get('summary', {}).get('successful', 0)} endpoints")
