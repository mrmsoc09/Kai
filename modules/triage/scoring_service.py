from __future__ import annotations
import os, json, datetime as dt
from typing import List, Dict, Any, Tuple
from modules.vector.embedding import load_index, search
ART_DIR = "/a0/usr/projects/main-startup-build/k1/artifacts"
EMB_PATH = os.path.join(ART_DIR, "embeddings.jsonl")
EPSS_PATH = os.path.join(ART_DIR, "ingest", "epss_current.jsonl")
KEV_PATH = os.path.join(ART_DIR, "ingest", "cisa_kev.jsonl")

# Load EPSS and KEV maps (best-effort)

def _load_epss() -> Dict[str, float]:
    d: Dict[str, float] = {}
    try:
        with open(EPSS_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                o = json.loads(line)
                cid = (o.get('cve_id') or '').upper()
                if cid:
                    d[cid] = float(o.get('epss') or 0.0)
    except Exception:
        pass
    return d

def _load_kev() -> Dict[str, bool]:
    d: Dict[str, bool] = {}
    try:
        with open(KEV_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                o = json.loads(line)
                cid = (o.get('cve_id') or '').upper()
                if cid:
                    d[cid] = True
    except Exception:
        pass
    return d

EPSS = _load_epss()
KEV = _load_kev()

# Score: 0.5 * sim + 0.3 * epss + 0.2 * kev_flag

def triage_for_fingerprints(fps: List[Dict[str, Any]], topk: int = 25) -> List[Dict[str, Any]]:
    index = load_index(EMB_PATH)
    if not index:
        return []
    query_terms = []
    for fp in fps:
        t = (fp.get('tech') or '').strip()
        v = (fp.get('version') or '').strip()
        if t:
            query_terms.append(t)
        if v:
            query_terms.append(v)
    query = ' '.join(query_terms) or 'web app'
    hits = search(index, query, k=topk)
    out: List[Dict[str, Any]] = []
    for sim, rec in hits:
        cid = (rec.get('cve_id') or '').upper()
        epss = float(EPSS.get(cid, 0.0))
        kev = 1.0 if KEV.get(cid, False) else 0.0
        score = 0.5 * float(sim) + 0.3 * epss + 0.2 * kev
        out.append({
            'cve_id': rec.get('cve_id'),
            'sim': round(float(sim), 4),
            'epss': round(epss, 4),
            'kev': bool(kev),
            'score': round(score, 4),
            'description': rec.get('description'),
            'cwes': rec.get('cwes'),
            'published': rec.get('published'),
        })
    out.sort(key=lambda x: x['score'], reverse=True)
    return out
