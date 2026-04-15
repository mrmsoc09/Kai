from __future__ import annotations

import os
import time
import hmac
import hashlib
import requests
from typing import Any, Dict, List, Optional


class CoinbaseReadOnlyMirror:
    """
    Read-Only mirror for Coinbase.
    Restricted to viewing transaction history for bounty matching.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key or os.getenv("K1_COINBASE_READ_ONLY_KEY")
        self.api_secret = api_secret or os.getenv("K1_COINBASE_READ_ONLY_SECRET")
        self.base_url = "https://api.coinbase.com/v2"

    def _get_headers(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time()))
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            self.api_secret.encode("utf-8"), 
            message.encode("utf-8"), 
            hashlib.sha256
        ).hexdigest()

        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-VERSION": "2021-01-11",
            "Content-Type": "application/json",
        }

    def get_accounts(self) -> List[Dict[str, Any]]:
        path = "/accounts"
        headers = self._get_headers("GET", path)
        resp = requests.get(self.base_url + path, headers=headers)
        return resp.json().get("data", [])

    def get_transactions(self, account_id: str) -> List[Dict[str, Any]]:
        path = f"/accounts/{account_id}/transactions"
        headers = self._get_headers("GET", path)
        resp = requests.get(self.base_url + path, headers=headers)
        return resp.json().get("data", [])

    def match_deposit(self, amount: float, currency: str = "USD") -> Optional[Dict[str, Any]]:
        accounts = self.get_accounts()
        for acc in accounts:
            if acc.get("currency", {}).get("code") == currency:
                txs = self.get_transactions(acc["id"])
                for tx in txs:
                    if tx.get("type") == "buy" or tx.get("type") == "request":
                        tx_amount = float(tx.get("amount", {}).get("amount", 0.0))
                        if abs(tx_amount - amount) < 0.01:
                            return tx
        return None
