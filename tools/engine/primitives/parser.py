"""
Data parsing primitives for log analysis, packet inspection, and file forensics.
"""

import json
import re
import csv
import io
from typing import Dict, Any, List, Generator, Optional, Union
from datetime import datetime
from pathlib import Path

from .base import BasePrimitive, PrimitiveMetadata


class ParserPrimitive(BasePrimitive):
    """Base class for data parsing operations."""
    CATEGORY = "parser"
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="BaseParser",
            version="1.0.0",
            category="parser",
            description="Base parsing primitive",
            author="Forge Engine",
            risk_level="low",
            required_permissions=["file_read"],
            dependencies=[]
        )
    
    def parse(self, data: Union[str, bytes]) -> Any:
        """Main parsing entry point."""
        raise NotImplementedError


class LogParser(ParserPrimitive):
    """Multi-format log file parser with pattern matching."""
    
    COMMON_PATTERNS = {
        'apache': r'(?P<ip>\d+\.\d+\.\d+\.\d+) - - \[(?P<time>.*?)\] "(?P<method>\w+) (?P<path>.*?) (?P<protocol>.*?)" (?P<status>\d+) (?P<size>\d+)',
        'syslog': r'(?P<month>\w{3})\s+(?P<day>\d+)\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\w+)\s+(?P<process>.*?):\s+(?P<message>.*)',
        'ssh_auth': r'(?P<date>\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+sshd\[(?P<pid>\d+)\]:\s+(?P<message>.*)',
        'firewall': r'(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<action>\w+).*src=(?P<src_ip>\S+).*dst=(?P<dst_ip>\S+).*dport=(?P<dst_port>\d+)'
    }
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="LogParser",
            version="2.0.0",
            category="parser",
            description="Universal log parser with automatic format detection",
            author="Forge Engine",
            risk_level="low",
            required_permissions=["file_read"],
            dependencies=["regex"]
        )
    
    def execute(self, file_path: str, 
                pattern: str = "auto",
                filter_terms: List[str] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Parse log file and yield structured entries.
        
        Args:
            file_path: Path to log file
            pattern: Regex pattern name or 'auto' for detection
            filter_terms: Only return entries containing these terms
            
        Yields:
            Dict with parsed fields
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        # Auto-detect format from first line
        if pattern == "auto":
            with open(path, 'r', errors='ignore') as f:
                sample = f.readline()
                pattern = self._detect_format(sample)
        
        regex = re.compile(self.COMMON_PATTERNS.get(pattern, pattern))
        
        with open(path, 'r', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                # Filter check
                if filter_terms and not any(term in line for term in filter_terms):
                    continue
                
                match = regex.match(line)
                if match:
                    entry = match.groupdict()
                    entry['_line_num'] = line_num
                    entry['_raw'] = line
                    yield entry
                else:
                    # Yield unparsed line if no match
                    yield {
                        '_line_num': line_num,
                        '_raw': line,
                        '_unparsed': True
                    }
    
    def _detect_format(self, sample: str) -> str:
        """Auto-detect log format from sample line."""
        if 'sshd[' in sample:
            return 'ssh_auth'
        elif ' - - [' in sample:
            return 'apache'
        elif len(sample) > 15 and sample[3] == ' ' and sample[6] == ' ':
            return 'syslog'
        elif 'src=' in sample and 'dst=' in sample:
            return 'firewall'
        return 'syslog'  # Default fallback
    
    def analyze_patterns(self, file_path: str, 
                        time_window: int = 300) -> Dict[str, Any]:
        """
        Analyze log for attack patterns (brute force, scanning, etc.).
        """
        stats = {
            'total_lines': 0,
            'failed_logins': 0,
            'unique_ips': set(),
            'ip_attempts': {},
            'time_distribution': {}
        }
        
        for entry in self.execute(file_path, pattern="auto"):
            stats['total_lines'] += 1
            
            if 'ip' in entry:
                ip = entry['ip']
                stats['unique_ips'].add(ip)
                stats['ip_attempts'][ip] = stats['ip_attempts'].get(ip, 0) + 1
            
            if 'message' in entry:
                msg = entry['message'].lower()
                if 'failed' in msg or 'invalid' in msg or 'authentication failure' in msg:
                    stats['failed_logins'] += 1
        
        stats['unique_ips'] = list(stats['unique_ips'])
        stats['suspicious_ips'] = [ip for ip, count in stats['ip_attempts'].items() 
                                   if count > 10]
        
        return stats


class NetworkPacketParser(ParserPrimitive):
    """PCAP and network packet parsing primitive."""
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="NetworkPacketParser",
            version="1.0.0",
            category="parser",
            description="Network packet analysis and extraction",
            author="Forge Engine",
            risk_level="low",
            required_permissions=["file_read"],
            dependencies=["scapy"]
        )
    
    def execute(self, pcap_file: str, 
                filter_bpf: str = None) -> List[Dict[str, Any]]:
        """
        Parse PCAP file and extract packet information.
        
        Note: Requires scapy. Returns summary if scapy not available.
        """
        try:
            from scapy.all import rdpcap, IP, TCP, UDP
            
            packets = rdpcap(pcap_file)
            results = []
            
            for pkt in packets:
                if IP in pkt:
                    entry = {
                        'timestamp': float(pkt.time),
                        'src_ip': pkt[IP].src,
                        'dst_ip': pkt[IP].dst,
                        'protocol': 'IP',
                        'length': len(pkt)
                    }
                    
                    if TCP in pkt:
                        entry['protocol'] = 'TCP'
                        entry['src_port'] = pkt[TCP].sport
                        entry['dst_port'] = pkt[TCP].dport
                        entry['flags'] = str(pkt[TCP].flags)
                    elif UDP in pkt:
                        entry['protocol'] = 'UDP'
                        entry['src_port'] = pkt[UDP].sport
                        entry['dst_port'] = pkt[UDP].dport
                    
                    results.append(entry)
                    
            return results
            
        except ImportError:
            # Fallback without scapy
            return [{"note": "Scapy not installed", "file": pcap_file}]


class JSONAnalyzer(ParserPrimitive):
    """Structured JSON data analyzer for API responses and logs."""
    
    def _define_metadata(self) -> PrimitiveMetadata:
        return PrimitiveMetadata(
            name="JSONAnalyzer",
            version="1.0.0",
            category="parser",
            description="JSON data analysis and extraction",
            author="Forge Engine",
            risk_level="low",
            required_permissions=["file_read"],
            dependencies=[]
        )
    
    def execute(self, data: Union[str, Dict], 
                query: str = None) -> Dict[str, Any]:
        """
        Analyze JSON data with optional JMESPath-like querying.
        """
        if isinstance(data, str):
            if Path(data).exists():
                with open(data, 'r') as f:
                    obj = json.load(f)
            else:
                obj = json.loads(data)
        else:
            obj = data
        
        result = {
            'type': type(obj).__name__,
            'keys': [],
            'statistics': {}
        }
        
        if isinstance(obj, dict):
            result['keys'] = list(obj.keys())
            result['depth'] = self._calculate_depth(obj)
            result['statistics'] = {
                'total_keys': len(obj),
                'nested_objects': sum(1 for v in obj.values() if isinstance(v, dict)),
                'arrays': sum(1 for v in obj.values() if isinstance(v, list))
            }
        elif isinstance(obj, list):
            result['length'] = len(obj)
            if len(obj) > 0:
                result['item_types'] = list(set(type(item).__name__ for item in obj))
        
        # Simple path query (e.g., "user.name")
        if query:
            result['query_result'] = self._query_path(obj, query)
            
        return result
    
    def _calculate_depth(self, d: Dict, level: int = 1) -> int:
        """Calculate nesting depth of dictionary."""
        if not isinstance(d, dict) or not d:
            return level
        return max(self._calculate_depth(v, level + 1) 
                  for v in d.values() if isinstance(v, dict))
    
    def _query_path(self, obj: Any, path: str) -> Any:
        """Simple dot-notation path query."""
        keys = path.split('.')
        current = obj
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
