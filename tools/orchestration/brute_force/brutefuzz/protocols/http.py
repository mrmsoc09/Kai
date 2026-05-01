"""HTTP/HTTPS protocol handler with advanced evasion"""
import asyncio
import aiohttp
import random
from typing import Optional, Dict, Any
from urllib.parse import urljoin, quote

from .base import BaseProtocolHandler, ProtocolResult


class HTTPProtocolHandler(BaseProtocolHandler):
    """
    High-performance HTTP/HTTPS handler with WAF evasion and session management
    """
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101"
    ]
    
    def __init__(self, target: str, port: Optional[int] = None, 
                 use_ssl: bool = True, method: str = "GET",
                 path: str = "/", headers: Optional[Dict] = None,
                 proxy: Optional[str] = None, **kwargs):
        super().__init__(target, port, use_ssl, **kwargs)
        self.method = method.upper()
        self.path = path
        self.base_url = f"{'https' if use_ssl else 'http'}://{target}:{port or (443 if use_ssl else 80)}"
        self.custom_headers = headers or {}
        self.proxy = proxy
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def connect(self) -> bool:
        """Initialize HTTP session with rotating headers"""
        headers = {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            **self.custom_headers
        }
        
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            enable_cleanup_closed=True,
            force_close=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=30)
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            connector=connector,
            timeout=timeout
        )
        return True
    
    async def execute(self, payload: str) -> ProtocolResult:
        """Execute HTTP request with payload"""
        if not self.session:
            await self.connect()
            
        # Construct URL with payload
        target_url = urljoin(self.base_url, self.path)
        
        # Insert payload (support for {PAYLOAD} placeholder or append)
        if "{PAYLOAD}" in target_url:
            target_url = target_url.replace("{PAYLOAD}", quote(payload))
        elif self.method == "GET":
            separator = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{separator}fuzz={quote(payload)}"
            
        try:
            start_time = asyncio.get_event_loop().time()
            
            if self.method == "POST":
                data = self.options.get("post_data", {}).copy()
                for key in data:
                    if data[key] == "{PAYLOAD}":
                        data[key] = payload
                        
                async with self.session.post(
                    target_url, 
                    data=data,
                    proxy=self.proxy,
                    allow_redirects=self.options.get("follow_redirects", True),
                    ssl=self.use_ssl
                ) as response:
                    return await self._process_response(response, start_time)
            else:
                async with self.session.get(
                    target_url,
                    proxy=self.proxy,
                    allow_redirects=self.options.get("follow_redirects", True),
                    ssl=self.use_ssl
                ) as response:
                    return await self._process_response(response, start_time)
                    
        except aiohttp.ClientResponseError as e:
            return ProtocolResult(
                success=False,
                blocked=e.status in [403, 429, 503],
                status_code=e.status
            )
        except Exception as e:
            return ProtocolResult(success=False, data=str(e))
    
    async def _process_response(self, response: aiohttp.ClientResponse, 
                               start_time: float) -> ProtocolResult:
        """Process HTTP response"""
        body = await response.text()
        response_time = asyncio.get_event_loop().time() - start_time
        
        # Detect blocking
        blocked = any(indicator in body.lower() for indicator in [
            "cloudflare", "captcha", "blocked", "waf", "forbidden", "rate limit"
        ])
        
        # Success detection (customizable)
        success_indicators = self.options.get("success_indicators", [])
        success = any(ind in body for ind in success_indicators) if success_indicators else response.status == 200
        
        return ProtocolResult(
            success=success,
            data=body[:1000],  # Truncate for memory
            blocked=blocked,
            status_code=response.status,
            headers=dict(response.headers),
            response_time=response_time
        )
    
    async def disconnect(self):
        if self.session:
            await self.session.close()
