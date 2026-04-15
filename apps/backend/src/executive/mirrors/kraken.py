from __future__ import annotations

import hmac
import hashlib
import base64
import time
import requests
import os
from typing import Any, Dict, List, Optional


class KrakenReadOnlyMirror:
    """
    Read-Only mirror for Kraken Exchange.
    Used strictly for matching incoming credits to expected bounty payouts.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key or os.getenv("K1_KRAKEN_READ_ONLY_KEY")
        self.api_secret = api_secret or os.getenv("K1_KRAKEN_READ_ONLY_SECRET")
        self.base_url = "https://api.kraken.com"

    def _get_kraken_signature(self, urlpath: str, data: dict, secret: str) -> str:
        postdata = requests.compat.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())
        return sigdigest.decode()

    def _private_query(self, endpoint: str, data: dict = None) -> dict:
        if not self.api_key or not self.api_secret:
            return {"error": ["API keys missing"]}
            
        if data is None:
            data = {}
        
        urlpath = f"/0/private/{endpoint}"
        data['nonce'] = int(time.time() * 1000)
        
        headers = {
            'API-Key': self.api_key,
            'API-Sign': self._get_kraken_signature(urlpath, data, self.api_secret)
        }
        
        resp = requests.post((self.base_url + urlpath), headers=headers, data=data)
        return resp.json()

    def get_recent_ledgers(self) -> List[Dict[str, Any]]:
        """Fetch ledger entries to identify incoming bounty transfers."""
        res = self._private_query("Ledgers", {"type": "deposit"})
        if res.get("error"):
            return []
        return res.get("result", {}).get("ledger", {})

    def match_expected_payout(self, expected_amount: float, currency: str = "USD") -> Optional[Dict[str, Any]]:
        """Attempts to find a matching ledger entry for an expected bounty."""
        ledgers = self.get_recent_ledgers()
        for ledger_id, entry in ledgers.items():
            amount = float(entry.get("amount", 0.0))
            asset = entry.get("asset", "")
            # Basic matching logic (can be refined with timestamps)
            if abs(amount - expected_amount) < 0.01:
                return {"ledger_id": ledger_id, "amount": amount, "asset": asset}
        return None
