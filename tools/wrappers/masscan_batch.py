"""
Masscan Batch Scanner
Ultra-fast asynchronous port scanning for large-scale reconnaissance.
Masscan is natively fast; batch wrapper adds workflow orchestration.
"""
from typing import List, Dict, Optional
import subprocess
import json
from datetime import datetime

try:
    from .batch_mixin import BatchScanMixin
except ImportError:
    from batch_mixin import BatchScanMixin

class MasscanBatchScanner(BatchScanMixin):
    """
    High-speed masscan wrapper optimized for internet-scale scanning.
    Uses masscan's native async capabilities; batches at workflow level.
    """

    def __init__(self, max_workers: int = 3):  # Lower workers for masscan (it's already parallel)
        super().__init__(max_workers=max_workers)
        self.tool_name = 'masscan'
        self.category = 'Network Scanning'

    def scan_single(
        self,
        target: str,
        ports: Optional[List[int]] = None,
        options: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """
        Execute masscan on target.
        Note: masscan requires root privileges.
        """
        options = options or {}

        # Build masscan command
        cmd = ['masscan', '-p', ','.join(map(str, ports or [80, 443, 8080]))]

        # Target
        cmd.extend(target.split())

        # Rate limiting (important for avoiding network bans)
        rate = options.get('rate', 1000)  # packets/sec
        cmd.extend(['--rate', str(rate)])

        # Output format
        cmd.extend(['-oJ', '-'])  # JSON to stdout

        # Exclude file if provided
        if options.get('exclude_file'):
            cmd.extend(['--excludefile', options['exclude_file']])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=options.get('timeout', 600)
            )

            return {
                'target': target,
                'command': ' '.join(cmd),
                'raw_output': result.stdout,
                'findings': self._parse_masscan_json(result.stdout) if result.stdout else [],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'target': target,
                'error': str(e),
                'findings': [],
                'timestamp': datetime.now().isoformat()
            }

    def _parse_masscan_json(self, json_output: str) -> List[Dict]:
        """Parse masscan JSON output."""
        findings = []

        for line in json_output.strip().split('\n'):
            if not line or line in ['[', ']']:
                continue

            # Remove trailing comma if present
            if line.endswith(','):
                line = line[:-1]

            try:
                data = json.loads(line)
                findings.append({
                    'type': 'open_port',
                    'severity': 'info',
                    'target': data.get('ip', 'unknown'),
                    'port': str(data.get('ports', [{}])[0].get('port', 'unknown')),
                    'protocol': 'tcp',
                    'timestamp': data.get('timestamp', ''),
                    'description': f"Port {data.get('ports', [{}])[0].get('port')} open on {data['ip']}"
                })
            except json.JSONDecodeError:
                continue

        return findings

    def scan_internet_wide(
        self,
        port_list: List[int],
        exclude_ranges: Optional[List[str]] = None,
        **kwargs
    ) -> Dict:
        """
        Internet-wide port scanning (requires proper authorization).

        Args:
            port_list: Ports to scan across internet
            exclude_ranges: CIDR ranges to exclude (highly recommended)

        Returns:
            Aggregated results
        """
        cmd = ['masscan', '-p', ','.join(map(str, port_list))]
        cmd.append('0.0.0.0/0')  # Entire internet

        # Exclusions (critical for avoiding trouble)
        if exclude_ranges:
            # Write to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for r in exclude_ranges:
                    f.write(f"{r}\n")
                cmd.extend(['--excludefile', f.name])

        cmd.extend(['--rate', '10000', '-oJ', '-'])

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        return {
            'scope': 'internet_wide',
            'ports': port_list,
            'findings': self._parse_masscan_json(result.stdout),
            'warning': 'Authorization required. Only scan infrastructure you own or have permission to scan.'
        }

# Convenience function
def quick_port_scan(targets: List[str], ports: List[int]) -> List[Dict]:
    """Quick parallel port scan."""
    scanner = MasscanBatchScanner()
    return scanner.scan_batch(targets, ports=ports, options={'rate': 1000})

if __name__ == '__main__':
    scanner = MasscanBatchScanner()
    # Example: Scan local network
    results = scanner.scan_batch(['10.0.0.0/24'], ports=[80, 443, 8080])
    print(f"Scanned: {len(results)} ranges")
