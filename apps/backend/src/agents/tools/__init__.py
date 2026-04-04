from .subfinder.agent import SubfinderAgent
from .amass.agent import AmassAgent
from .dnsx.agent import DnsxAgent
from .gau.agent import GauAgent
from .waybackurls.agent import WaybackurlsAgent
from .httpx_probe.agent import HttpxProbeAgent
from .naabu.agent import NaabuAgent
from .nuclei_scan.agent import NucleiScanAgent
from .dalfox.agent import DalfoxAgent
from .sqlmap.agent import SqlmapAgent
from .ssrfmap.agent import SsrfmapAgent
from .corsy.agent import CorsyAgent
from .crlfuzz.agent import CrlfuzzAgent
from .jwt_tool.agent import JwtToolAgent
from .kiterunner.agent import KiterunnerAgent

AGENT_REGISTRY = {
    "subfinder": SubfinderAgent,
    "amass": AmassAgent,
    "dnsx": DnsxAgent,
    "gau": GauAgent,
    "waybackurls": WaybackurlsAgent,
    "httpx_probe": HttpxProbeAgent,
    "naabu": NaabuAgent,
    "nuclei_scan": NucleiScanAgent,
    "dalfox": DalfoxAgent,
    "sqlmap": SqlmapAgent,
    "ssrfmap": SsrfmapAgent,
    "corsy": CorsyAgent,
    "crlfuzz": CrlfuzzAgent,
    "jwt_tool": JwtToolAgent,
    "kiterunner": KiterunnerAgent,
}

__all__ = [
    "SubfinderAgent",
    "AmassAgent",
    "DnsxAgent",
    "GauAgent",
    "WaybackurlsAgent",
    "HttpxProbeAgent",
    "NaabuAgent",
    "NucleiScanAgent",
    "DalfoxAgent",
    "SqlmapAgent",
    "SsrfmapAgent",
    "CorsyAgent",
    "CrlfuzzAgent",
    "JwtToolAgent",
    "KiterunnerAgent",
    "AGENT_REGISTRY",
]
