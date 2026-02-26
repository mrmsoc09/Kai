from __future__ import annotations
"""CISA Known Exploited Vulnerabilities ingestion."""
import os, json, datetime as dt
ART_DIR = os.environ.get("K1_ART_INGEST_DIR", "/a0/usr/projects/main-startup-build/k1/artifacts/ingest")
os.makedirs(ART_DIR, exist_ok=True)
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

def _now_iso():
    return dt.datetime.utcnow().isoformat() + "Z"

def ingest(save_name: str = "cisa_kev.jsonl") -> str:
    out_path = os.path.join(ART_DIR, save_name)
    rows = []
    try:
        import requests
        r = requests.get(KEV_URL, timeout=20)
        r.raise_for_status()
        data = r.json()
        for item in data.get("vulnerabilities", []):
            rows.append({
                "cve_id": item.get("cveID"),
                "vendor": item.get("vendorProject"),
                "product": item.get("product"),
                "short_description": item.get("shortDescription"),
                "date_added": item.get("dateAdded"),
                "due_date": item.get("dueDate"),
                "required_action": item.get("requiredAction"),
                "_ingested_at": _now_iso(),
            })
    except Exception:
        rows = []
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return out_path
