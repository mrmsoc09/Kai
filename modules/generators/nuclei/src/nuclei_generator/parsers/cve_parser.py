"""
CVE data parser and fetcher.
Integrates with NVD (National Vulnerability Database) API.
"""

import re
import time
import requests
from typing import Optional, Dict, Any
from ..models.template_models import CVEData, Severity


class CVEParser:
    """
    Fetches and parses CVE data from NVD API.
    Handles rate limiting and caching.
    """
    
    def __init__(self, api_key: Optional[str] = None, rate_limit: int = 6):
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        self.last_request_time = 0
        
    def fetch(self, cve_id: str) -> Optional[CVEData]:
        """
        Fetch CVE data from NVD API.
        
        Args:
            cve_id: CVE ID (e.g., CVE-2021-44228)
            
        Returns:
            CVEData object or None if not found
        """
        # Rate limiting
        self._apply_rate_limit()
        
        headers = {}
        if self.api_key:
            headers["apiKey"] = self.api_key
            
        params = {"cveId": cve_id}
        
        try:
            response = requests.get(
                self.base_url,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_response(data, cve_id)
            
        except requests.RequestException as e:
            print(f"Error fetching CVE {cve_id}: {e}")
            return None
    
    def _apply_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        import time
        min_interval = 10.0 / self.rate_limit  # 6 requests per 10 seconds default
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
    
    def _parse_response(self, data: Dict[str, Any], cve_id: str) -> Optional[CVEData]:
        """Parse NVD API response into CVEData."""
        vulnerabilities = data.get("vulnerabilities", [])
        if not vulnerabilities:
            return None
            
        vuln = vulnerabilities[0]
        cve = vuln.get("cve", {})
        
        # Extract description
        descriptions = cve.get("descriptions", [])
        description = ""
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break
        
        # Extract CVSS data
        metrics = cve.get("metrics", {})
        cvss_score = None
        cvss_vector = None
        
        # Prefer CVSS v3, fallback to v2
        for cvss_version in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
            if cvss_version in metrics:
                cvss_data = metrics[cvss_version][0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore")
                cvss_vector = cvss_data.get("vectorString")
                break
        
        # Extract CPEs (affected products)
        configurations = cve.get("configurations", [])
        cpe_list = []
        for config in configurations:
            nodes = config.get("nodes", [])
            for node in nodes:
                for match in node.get("cpeMatch", []):
                    if match.get("vulnerable", False):
                        cpe = match.get("criteria", "")
                        if cpe:
                            cpe_list.append(cpe)
        
        # Extract references
        references = []
        for ref in cve.get("references", []):
            url = ref.get("url", "")
            if url:
                references.append(url)
        
        # Dates
        published = cve.get("published")
        modified = cve.get("lastModified")
        
        return CVEData(
            cve_id=cve_id,
            description=description,
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            cpe_list=cpe_list,
            references=references,
            published_date=published,
            last_modified=modified
        )
    
    def parse_local(self, cve_data: Dict[str, Any]) -> CVEData:
        """
        Parse locally provided CVE data (e.g., from manual input).
        """
        return CVEData(
            cve_id=cve_data.get("cve_id", ""),
            description=cve_data.get("description", ""),
            cvss_score=cve_data.get("cvss_score"),
            cvss_vector=cve_data.get("cvss_vector"),
            cpe_list=cve_data.get("cpe_list", []),
            references=cve_data.get("references", []),
            published_date=cve_data.get("published_date"),
            last_modified=cve_data.get("last_modified")
        )
