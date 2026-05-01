"""Nmap wrapper for KaisonOne - network scanning."""
import subprocess
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class NmapResult:
    success: bool
    hosts: List[Dict] = field(default_factory=list)
    open_ports: Dict[str, List[int]] = field(default_factory=dict)
    services: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw_output: str = ""

class NmapTool:
    """KaisonOne tool wrapper for nmap network scanner."""

    @staticmethod
    def check_install() -> bool:
        try:
            result = subprocess.run(['which', 'nmap'], capture_output=True, check=True)
            return result.returncode == 0
        except:
            return False

    @classmethod
    async def scan(cls, target: str, ports: Optional[str] = None, 
                   script: Optional[str] = None, timing: int = 3) -> NmapResult:
        if not cls.check_install():
            return NmapResult(
                success=False, 
                errors=["nmap not installed. Install with: apt-get install nmap"]
            )

        cmd = ['nmap', '-oX', '-', f'-T{timing}']
        if ports:
            cmd.extend(['-p', ports])
        if script:
            cmd.extend(['--script', script])
        cmd.append(target)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return cls._parse_xml(result.stdout)
        except Exception as e:
            return NmapResult(success=False, errors=[str(e)])

    @classmethod
    def _parse_xml(cls, xml_output: str) -> NmapResult:
        try:
            root = ET.fromstring(xml_output)
            hosts, open_ports, services = [], {}, []

            for host in root.findall('host'):
                addr = host.findaddress/[@addrtype="ipv4"]')
                addr = addr.get('addr') if addr is not None else 'unknown'
                hosts.append({'address': addr, 'status': host.find('status').get('state') if host.find('status') is not None else 'unknown'})

                ports_elem = host.find('ports')
                if ports_elem is not None:
                    open_ports[addr] = []
                    for port in ports_elem.findall('port'):
                        state = port.find('state')
                        if state is not None and state.get('state') == 'open':
                            port_num = int(port.get('portid'))
                            open_ports[addr].append(port_num)

                            service = port.find('service')
                            if service is not None:
                                services.append({
                                    'host': addr, 'port': port_num,
                                    'name': service.get('name', 'unknown'),
                                    'version': service.get('version', '')
                                })

            return NmapResult(
                success=True, hosts=hosts, open_ports=open_ports,
                services=services, raw_output=xml_output[:5000]
            )
        except Exception as e:
            return NmapResult(success=False, errors=[f"Parse error: {e}"], raw_output=xml_output[:1000])

if __name__ == '__main__':
    import asyncio
    result = asyncio.run(NmapTool.scan('127.0.0.1', ports='80,443'))
    print(json.dumps({
        'success': result.success,
        'hosts': len(result.hosts),
        'open_ports': result.open_ports,
        'errors': result.errors
    }, indent=2))
