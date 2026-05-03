import subprocess, json
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class MasscanResult:
    success: bool
    hosts: Dict[str, List[int]] = field(default_factory=dict)
    total_open: int = 0
    scan_duration: float = 0.0
    errors: List[str] = field(default_factory=list)

class MasscanTool:
    @staticmethod
    def check_install() -> bool:
        try:
            r = subprocess.run(['which', 'masscan'], capture_output=True)
            return r.returncode == 0
        except:
            return False

    @classmethod
    async def scan(cls, target: str, ports: str = "0-65535", rate: int = 10000):
        if not cls.check_install():
            return MasscanResult(success=False, errors=["masscan not installed"])

        cmd = ['masscan', '-p', ports, '--rate', str(rate), '--wait', '0', target, '-oJ', '-']
        try:
            import time
            start = time.time()
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            return cls._parse_json(r.stdout, time.time() - start)
        except subprocess.TimeoutExpired:
            return MasscanResult(success=False, errors=["timeout"])

    @classmethod
    def _parse_json(cls, output: str, duration: float):
        hosts, total = {}, 0
        for line in output.split('
'):
            line = line.strip().rstrip(',')
            if not line or line in ['[', ']']:
                continue
            try:
                data = json.loads(line)
                ip = data.get('ip', 'unknown')
                port = data.get('ports', [{}])[0].get('port', 0)
                hosts.setdefault(ip, []).append(port)
                total += 1
            except:
                continue
        return MasscanResult(success=True, hosts=hosts, total_open=total, scan_duration=duration)
