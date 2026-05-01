"""
Nmap Batch Scanner
High-throughput network scanning with parallel target execution.
Uses BatchScanMixin for optimal resource utilization.
"""
from typing import List, Dict, Optional
import subprocess
import json
from datetime import datetime

try:
    from .batch_mixin import BatchScanMixin
except ImportError:
    from batch_mixin import BatchScanMixin

class NmapBatchScanner(BatchScanMixin):
    """
    Parallel nmap scanner for multiple targets.
    Optimized for large-scope network reconnaissance.
    """

    def __init__(self, max_workers: int = 10):
        super().__init__(max_workers=max_workers)
        self.tool_name = 'nmap'
        self.category = 'Network Scanning'

    def scan_single(
        self,
        target: str,
        ports: Optional[List[int]] = None,
        options: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """
        Single target scan - executed in parallel by scan_batch().

        Args:
            target: IP, hostname, or CIDR range for single target
            ports: Port list (default: top 1000)
            options: Additional nmap options

        Returns:
            Parsed nmap results for target
        """
        options = options or {}

        # Build nmap command
        cmd = ['nmap', '-sV', '--open']

        # Script selection based on context
        if options.get('service_detection'):
            cmd.append('-sC')  # Default scripts
        if options.get('aggressive'):
            cmd.extend(['-A', '-T4'])
        else:
            cmd.append('-T3')

        # Port specification
        if ports:
            cmd.extend(['-p', ','.join(map(str, ports))])
        elif options.get('top_ports'):
            cmd.extend(['--top-ports', str(options['top_ports'])])

        # Output format (XML for parsing)
        cmd.extend(['-oX', '-', target])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=options.get('timeout', 300)
            )

            return {
                'target': target,
                'command': ' '.join(cmd),
                'raw_output': result.stdout,
                'return_code': result.returncode,
                'findings': self._parse_nmap_xml(result.stdout) if result.returncode == 0 else [],
                'timestamp': datetime.now().isoformat()
            }
        except subprocess.TimeoutExpired:
            return {
                'target': target,
                'error': 'Scan timeout',
                'findings': [],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'target': target,
                'error': str(e),
                'findings': [],
                'timestamp': datetime.now().isoformat()
            }

    def _parse_nmap_xml(self, xml_output: str) -> List[Dict]:
        """Parse nmap XML output to structured findings."""
        import xml.etree.ElementTree as ET

        findings = []
        try:
            root = ET.fromstring(xml_output)
            for host in root.findall('host'):
                for port in host.findall('.//port'):
                    state = port.find('state')
                    service = port.find('service')

                    if state is not None and state.get('state') == 'open':
                        finding = {
                            'type': 'open_port',
                            'severity': 'info',
                            'target': host.find('address').get('addr') if host.find('address') is not None else 'unknown',
                            'port': port.get('portid'),
                            'protocol': port.get('protocol'),
                            'service': service.get('name') if service is not None else 'unknown',
                            'version': service.get('version') if service is not None else None,
                            'description': f"Port {port.get('portid')}/{port.get('protocol')} open"
                        }
                        findings.append(finding)
        except Exception as e:
            findings.append({
                'type': 'parse_error',
                'severity': 'low',
                'description': f'Failed to parse nmap output: {str(e)}'
            })

        return findings

    def scan_networks(
        self,
        networks: List[str],
        discover_hosts: bool = True,
        **kwargs
    ) -> Dict:
        """
        Batch scan multiple networks with host discovery.

        Args:
            networks: List of CIDR ranges (e.g., ['10.0.0.0/24', '192.168.1.0/24'])
            discover_hosts: If True, first discover live hosts, then scan ports

        Returns:
            Aggregated results with live hosts and open ports
        """
        if discover_hosts:
            # Step 1: Host discovery across all networks
            print(f"[*] Discovering live hosts in {len(networks)} networks...")
            host_discovery_opts = {'top_ports': 100, 'timeout': 60}

            # Use scan_batch_fast for discovery
            discovery = self.scan_batch_fast(networks, options=host_discovery_opts)

            # Extract live hosts
            live_hosts = []
            for scan in discovery.get('successful_scans', []):
                for finding in scan.get('results', {}).get('findings', []):
                    if finding.get('type') == 'open_port':
                        live_hosts.append(finding['target'])

            live_hosts = list(set(live_hosts))  # Deduplicate

            print(f"[+] Found {len(live_hosts)} live hosts")

            if not live_hosts:
                return discovery

            # Step 2: Full port scan on live hosts
            print(f"[*] Running full port scan on live hosts...")
            full_results = self.scan_batch_fast(live_hosts, **kwargs)

            # Merge results
            return {
                'discovery': discovery,
                'full_scan': full_results,
                'live_hosts': live_hosts,
                'summary': {
                    'networks_scanned': len(networks),
                    'live_hosts_found': len(live_hosts),
                    'total_open_ports': full_results.get('summary', {}).get('successful', 0)
                }
            }

        return self.scan_batch_fast(networks, **kwargs)

# Convenience function
def scan_hosts(targets: List[str], ports: Optional[List[int]] = None) -> List[Dict]:
    """Quick batch scan of multiple hosts."""
    scanner = NmapBatchScanner()
    return scanner.scan_batch(targets, ports=ports)

if __name__ == '__main__':
    # Example usage
    scanner = NmapBatchScanner()

    # Single batch scan
    results = scanner.scan_batch(
        targets=['scanme.nmap.org', 'example.com'],
        options={'top_ports': 100}
    )

    print(f"Scanned {len(results)} targets")
    for r in results:
        if r['success']:
            print(f"  {r['target']}: {len(r['results']['findings'])} open ports")
