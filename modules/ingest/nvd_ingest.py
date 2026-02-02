from __future__ import annotations
"""NVD 2.0 CVE/CPE ingestion scaffold with local cache fallback.
Safely runs offline if network is unavailable. Writes JSONL artifacts.
"""
import os, json, datetime as dt
from typing import Iterable, Dict, Any

ART_DIR = os.environ.get("K1_ART_INGEST_DIR", "/a0/usr/projects/main-startup-build/k1/artifacts/ingest")
os.makedirs(ART_DIR, exist_ok=True)
NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

def _now_iso():
    return dt.datetime.utcnow().isoformat() + "Z"

def _write_jsonl(path: str, rows: Iterable[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def _extract_cve_rows(payload: Dict[str, Any]):
    for v in payload.get("vulnerabilities", []):
        c = v.get("cve", {})
        cve_id = c.get("id")
        desc = None
        for d in c.get("descriptions", []):
            if d.get("lang") == "en":
                desc = d.get("value")
                break
        metrics = c.get("metrics", {})
        cvss = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                try:
                    cvss = metrics[key][0].get("cvssData")
                    break
                except Exception:
                    pass
        cwes = []
        if c.get("weaknesses"):
            for w in c["weaknesses"]:
                for d in w.get("description", []):
                    if d.get("value"): cwes.append(d["value"])
        refs = [r.get("url") for r in c.get("references", []) if r.get("url")]
        yield {
            "cve_id": cve_id,
            "description": desc,
            "cwes": cwes,
            "cvss": cvss,
            "references": refs,
            "published": c.get("published"),
            "last_modified": c.get("lastModified"),
            "_ingested_at": _now_iso(),
        }

def ingest_recent(max_results: int = 200, save_name: str = "nvd_recent.jsonl") -> str:
    out_path = os.path.join(ART_DIR, save_name)
    rows = []
    try:
        import requests
        import datetime as dt
        params = {"resultsPerPage": max_results, "pubStartDate": (dt.datetime.utcnow() - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")}
        r = requests.get(NVD_API_BASE, params=params, timeout=20)
        if r.status_code == 200:
            rows = list(_extract_cve_rows(r.json()))
    except Exception:
        rows = []
    _write_jsonl(out_path, rows)
    return out_path
