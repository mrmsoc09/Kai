from __future__ import annotations
"""EPSS current scores ingestion with offline-safe behavior."""
import os, csv, gzip, io, json, datetime as dt
ART_DIR = os.environ.get("K1_ART_INGEST_DIR", "/a0/usr/projects/main-startup-build/k1/artifacts/ingest")
os.makedirs(ART_DIR, exist_ok=True)
EPSS_URL = "https://epss.cyentia.com/epss_scores-current.csv.gz"

def _now_iso():
    return dt.datetime.utcnow().isoformat() + "Z"

def ingest(save_name: str = "epss_current.jsonl") -> str:
    out_path = os.path.join(ART_DIR, save_name)
    rows = []
    try:
        import requests
        r = requests.get(EPSS_URL, timeout=20)
        r.raise_for_status()
        buf = io.BytesIO(r.content)
        with gzip.GzipFile(fileobj=buf) as gz:
            text = gz.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            rows.append({
                "cve_id": row.get("cve"),
                "epss": float(row.get("epss", 0.0) or 0.0),
                "percentile": float(row.get("percentile", 0.0) or 0.0),
                "_ingested_at": _now_iso(),
            })
    except Exception:
        rows = []
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return out_path
