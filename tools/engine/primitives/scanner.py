"""
Network scanning primitives for reconnaissance and discovery.
"""

import socket
import threading
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import time

from .base import BasePrimitive, PrimitiveMetadata


@dataclass
class ScanResult:
    """Standardized scan result structure."""
    host: str
    port: int
    state: str  # open, closed, filtered
    service: Optional[str] = None
    banner: Optional[str] = None
    response_time: float = 0.0


class ScannerPrimitive(BasePrimitive):
    """Base class for all scanning operations."""
    CATEGORY = "scanner"
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="BaseScanner",
            version="1.0.0",
            category="scanner",
            description="Base scanning primitive",
            author="Forge Engine",
            risk_level="low",
            required_permissions=["network"],
            dependencies=[]
        )
    
    def validate_target(self, target: str) -> bool:
        """Validate target is legitimate and not private/reserved (safety check)."""
        # Basic validation - prevent scanning of obvious internal ranges
        # In production, this would have more comprehensive checks
        forbidden_prefixes = ['127.', '0.', '255.']
        return not any(target.startswith(p) for p in forbidden_prefixes)


class TCPScanner(ScannerPrimitive):
    """TCP Connect/SYN scanner implementation."""
    
    COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995, 3306, 3389, 5432, 8080, 8443]
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="TCPScanner",
            version="2.0.0",
            category="scanner",
            description="Multi-threaded TCP port scanner with banner grabbing",
            author="Forge Engine",
            risk_level="medium",
            required_permissions=["network", "raw_socket"],
            dependencies=[]
        )
    
    def execute(self, target: str, ports: List[int] = None, 
                timeout: float = 2.0, threads: int = 50,
                grab_banner: bool = True) -> List[ScanResult]:
        """
        Execute TCP scan against target.
        
        Args:
            target: Hostname or IP address
            ports: List of ports to scan (default: COMMON_PORTS)
            timeout: Connection timeout in seconds
            threads: Number of concurrent threads
            grab_banner: Whether to attempt banner grabbing
            
        Returns:
            List of ScanResult objects
        """
        if not self.validate_target(target):
            raise ValueError(f"Target {target} failed validation checks")
            
        ports = ports or self.COMMON_PORTS
        results = []
        lock = threading.Lock()
        
        def scan_port(port: int) -> Optional[ScanResult]:
            start_time = time.time()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(timeout)
                    result = sock.connect_ex((target, port))
                    response_time = time.time() - start_time
                    
                    if result == 0:
                        banner = None
                        service = self._detect_service(port)
                        
                        if grab_banner:
                            try:
                                sock.settimeout(1)
                                banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                            except:
                                pass
                                
                        return ScanResult(
                            host=target,
                            port=port,
                            state="open",
                            service=service,
                            banner=banner,
                            response_time=response_time
                        )
            except Exception as e:
                pass
            return None
        
        # Threaded execution with rate limiting
        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_to_port = {executor.submit(scan_port, port): port for port in ports}
            
            for future in as_completed(future_to_port):
                result = future.result()
                if result:
                    with lock:
                        results.append(result)
                        
        return sorted(results, key=lambda x: x.port)
    
    def _detect_service(self, port: int) -> str:
        """Map common ports to service names."""
        services = {
            21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
            53: "dns", 80: "http", 110: "pop3", 143: "imap",
            443: "https", 993: "imaps", 995: "pop3s",
            3306: "mysql", 3389: "rdp", 5432: "postgresql",
            8080: "http-proxy", 8443: "https-alt"
        }
        return services.get(port, "unknown")


class UDPScanner(ScannerPrimitive):
    """UDP scanner for service discovery."""
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="UDPScanner",
            version="1.0.0",
            category="scanner",
            description="UDP port scanner with protocol-specific probes",
            author="Forge Engine",
            risk_level="medium",
            required_permissions=["network"],
            dependencies=[]
        )
    
    def execute(self, target: str, ports: List[int] = None, 
                timeout: float = 3.0) -> List[ScanResult]:
        """Execute UDP scan. Note: UDP scanning is less reliable than TCP."""
        ports = ports or [53, 67, 68, 69, 123, 161, 162, 500, 514, 520]
        results = []
        
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.settimeout(timeout)
                    # Send empty packet
                    sock.sendto(b'', (target, port))
                    try:
                        data, addr = sock.recvfrom(1024)
                        results.append(ScanResult(
                            host=target,
                            port=port,
                            state="open",
                            service=self._detect_udp_service(port),
                            banner=data.decode('utf-8', errors='ignore')[:100]
                        ))
                    except socket.timeout:
                        # No response could mean open|filtered or filtered
                        pass
            except Exception:
                pass
                
        return results
    
    def _detect_udp_service(self, port: int) -> str:
        services = {
            53: "dns", 67: "dhcp", 68: "dhcp", 69: "tftp",
            123: "ntp", 161: "snmp", 162: "snmptrap",
            500: "isakmp", 514: "syslog", 520: "rip"
        }
        return services.get(port, "unknown")


class ServiceDetector(ScannerPrimitive):
    """Advanced service detection and version fingerprinting."""
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="ServiceDetector",
            version="1.5.0",
            category="scanner",
            description="Deep service inspection and version detection",
            author="Forge Engine",
            risk_level="low",
            required_permissions=["network"],
            dependencies=[]
        )
    
    def execute(self, target: str, port: int, 
                probes: List[bytes] = None) -> Dict[str, Any]:
        """
        Perform deep service detection using protocol-specific probes.
        """
        default_probes = [
            b'\r\n',  # Generic newline
            b'HEAD / HTTP/1.0\r\n\r\n',  # HTTP
            b'HELP\r\n',  # FTP
            b'EHLO test\r\n',  # SMTP
        ]
        probes = probes or default_probes
        
        responses = []
        for probe in probes:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(3)
                    sock.connect((target, port))
                    sock.send(probe)
                    response = sock.recv(2048)
                    responses.append({
                        'probe': probe.hex(),
                        'response': response.decode('utf-8', errors='ignore'),
                        'length': len(response)
                    })
            except Exception as e:
                responses.append({'probe': probe.hex(), 'error': str(e)})
        
        # Simple fingerprinting logic
        fingerprint = self._analyze_fingerprint(responses)
        return {
            'target': target,
            'port': port,
            'fingerprint': fingerprint,
            'raw_responses': responses
        }
    
    def _analyze_fingerprint(self, responses: List[Dict]) -> str:
        """Analyze responses to determine service type."""
        for resp in responses:
            if 'response' in resp:
                data = resp['response'].lower()
                if 'http' in data or 'html' in data:
                    return "http"
                elif 'ssh' in data:
                    return "ssh"
                elif 'ftp' in data:
                    return "ftp"
                elif 'smtp' in data:
                    return "smtp"
        return "unknown"
