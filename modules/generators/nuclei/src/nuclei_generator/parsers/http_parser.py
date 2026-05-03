"""
HTTP Request/Response parser.
Extracts structured data from raw HTTP traffic.
Supports Burp Suite, raw HTTP, and HAR formats.
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs


@dataclass
class HTTPInteraction:
    """Represents a complete HTTP request/response pair."""
    method: str
    url: str
    path: str
    headers: Dict[str, str]
    body: Optional[str]
    response_status: int
    response_headers: Dict[str, str]
    response_body: Optional[str]
    content_type: Optional[str] = None


class HTTPParser:
    """
    Parser for HTTP request/response pairs.
    Handles various input formats.
    """
    
    def __init__(self):
        self.content_type_indicators = {
            "json": ["application/json", "text/json"],
            "xml": ["application/xml", "text/xml", "application/soap+xml"],
            "form": ["application/x-www-form-urlencoded"],
            "multipart": ["multipart/form-data"],
            "html": ["text/html"],
            "text": ["text/plain"]
        }
    
    def parse_raw(self, raw_request: str, raw_response: str) -> HTTPInteraction:
        """
        Parse raw HTTP request and response strings.
        
        Args:
            raw_request: Raw HTTP request text
            raw_response: Raw HTTP response text
            
        Returns:
            HTTPInteraction object
        """
        req_method, req_path, req_headers, req_body = self._parse_request(raw_request)
        resp_status, resp_headers, resp_body = self._parse_response(raw_response)
        
        # Extract URL from Host header and path
        host = req_headers.get("Host", "localhost")
        scheme = "https" if req_headers.get("X-Forwarded-Proto") == "https" or \
                 req_headers.get("X-HTTPS") == "1" else "http"
        url = f"{scheme}://{host}{req_path}"
        
        content_type = resp_headers.get("Content-Type", "").split(";")[0].strip()
        
        return HTTPInteraction(
            method=req_method,
            url=url,
            path=req_path,
            headers=req_headers,
            body=req_body,
            response_status=resp_status,
            response_headers=resp_headers,
            response_body=resp_body,
            content_type=content_type
        )
    
    def parse_burp(self, burp_data: str) -> List[HTTPInteraction]:
        """
        Parse Burp Suite exported data (XML or base64 encoded).
        Simplified implementation for raw HTTP in Burp format.
        """
        interactions = []
        # Split by common Burp separators or parse XML if provided
        # This is a simplified version - full implementation would parse Burp XML
        parts = burp_data.split("======================================================")
        
        for part in parts:
            if "HTTP/" in part and "GET" in part or "POST" in part:
                lines = part.strip().split("\n")
                # Simple heuristic to split request/response
                try:
                    # Find response start (HTTP/1.1 or HTTP/2)
                    resp_start = None
                    for i, line in enumerate(lines):
                        if line.startswith("HTTP/"):
                            resp_start = i
                            break
                    
                    if resp_start:
                        req_text = "\n".join(lines[:resp_start])
                        resp_text = "\n".join(lines[resp_start:])
                        interactions.append(self.parse_raw(req_text, resp_text))
                except Exception:
                    continue
                    
        return interactions
    
    def parse_har(self, har_json: str) -> List[HTTPInteraction]:
        """Parse HTTP Archive (HAR) format."""
        data = json.loads(har_json)
        interactions = []
        
        entries = data.get("log", {}).get("entries", [])
        for entry in entries:
            request = entry.get("request", {})
            response = entry.get("response", {})
            
            url = request.get("url", "")
            parsed = urlparse(url)
            
            headers = {h["name"]: h["value"] for h in request.get("headers", [])}
            resp_headers = {h["name"]: h["value"] for h in response.get("headers", [])}
            
            # Handle postData
            body = None
            if "postData" in request:
                body = request["postData"].get("text")
            
            resp_body = response.get("content", {}).get("text")
            
            interactions.append(HTTPInteraction(
                method=request.get("method", "GET"),
                url=url,
                path=parsed.path + ("?" + parsed.query if parsed.query else ""),
                headers=headers,
                body=body,
                response_status=response.get("status", 0),
                response_headers=resp_headers,
                response_body=resp_body,
                content_type=response.get("content", {}).get("mimeType")
            ))
            
        return interactions
    
    def _parse_request(self, raw: str) -> Tuple[str, str, Dict[str, str], Optional[str]]:
        """Parse raw HTTP request."""
        lines = raw.strip().split("\r\n")
        if len(lines) < 1:
            lines = raw.strip().split("\n")
            
        # Parse request line
        request_line = lines[0]
        parts = request_line.split(" ")
        method = parts[0]
        path = parts[1] if len(parts) > 1 else "/"
        
        # Parse headers
        headers = {}
        body = None
        i = 1
        
        while i < len(lines):
            line = lines[i]
            if line == "":
                # Body starts next line
                if i + 1 < len(lines):
                    body = "\n".join(lines[i+1:])
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
            i += 1
            
        return method, path, headers, body
    
    def _parse_response(self, raw: str) -> Tuple[int, Dict[str, str], Optional[str]]:
        """Parse raw HTTP response."""
        lines = raw.strip().split("\r\n")
        if len(lines) < 1:
            lines = raw.strip().split("\n")
            
        # Parse status line
        status_line = lines[0]
        status = 0
        if " " in status_line:
            try:
                status = int(status_line.split(" ")[1])
            except (ValueError, IndexError):
                pass
        
        # Parse headers
        headers = {}
        body = None
        i = 1
        
        while i < len(lines):
            line = lines[i]
            if line == "":
                if i + 1 < len(lines):
                    body = "\n".join(lines[i+1:])
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
            i += 1
            
        return status, headers, body
    
    def extract_parameters(self, interaction: HTTPInteraction) -> Dict[str, List[str]]:
        """Extract query and body parameters."""
        params = {}
        
        # Query parameters
        parsed = urlparse(interaction.url)
        if parsed.query:
            params.update(parse_qs(parsed.query))
        
        # Body parameters (simple form parsing)
        if interaction.body:
            content_type = interaction.headers.get("Content-Type", "")
            if "application/x-www-form-urlencoded" in content_type:
                params.update(parse_qs(interaction.body))
            elif "application/json" in content_type:
                try:
                    json_params = json.loads(interaction.body)
                    if isinstance(json_params, dict):
                        for k, v in json_params.items():
                            params[k] = [str(v)]
                except json.JSONDecodeError:
                    pass
                    
        return params
    
    def detect_vulnerability_indicators(self, interaction: HTTPInteraction) -> List[str]:
        """
        Analyze response for common vulnerability indicators.
        Returns list of potential vulnerability types.
        """
        indicators = []
        body = interaction.response_body or ""
        headers = str(interaction.response_headers)
        
        # Error-based detection
        error_patterns = {
            "sql": ["sql syntax", "mysql error", "postgresql", "oracle error", "sql server"],
            "xss": ["<script>", "javascript:", "onerror=", "onload="],
            "rce": ["uid=", "gid=", "root:", "command not found"],
            "lfi": ["root:x:", "boot loader", "etc/passwd"],
            "xxe": ["xml error", "external entity", "DOCTYPE"],
        }
        
        combined = (body + headers).lower()
        for vuln_type, patterns in error_patterns.items():
            if any(pattern in combined for pattern in patterns):
                indicators.append(vuln_type)
                
        return indicators
