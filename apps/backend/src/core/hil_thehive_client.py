from __future__ import annotations

import os
from typing import Optional

import requests


THEHIVE_URL = os.getenv("THEHIVE_URL", "http://localhost:9000")
THEHIVE_API_KEY = os.getenv("THEHIVE_API_KEY", "")


class TheHiveClient:
    def __init__(self, base_url: str = THEHIVE_URL, api_key: str = THEHIVE_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-Api-Key": api_key, "Content-Type": "application/json"})

    def ensure_case(self, title: str, summary: str) -> Optional[str]:
        url = f"{self.base_url}/api/v1/case"
        payload = {"title": title, "description": summary}
        response = self.session.post(url, json=payload, timeout=30)
        if response.status_code in (200, 201):
            data = response.json()
            return data.get("id") or data.get("_id")

        raise RuntimeError(
            f"TheHive case creation failed: {response.status_code} {response.text}"
        )
