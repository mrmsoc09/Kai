
import json
from pathlib import Path
from typing import Dict, Any, List
import yaml
from .run_store import load_all_runs

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / 'artifacts' / 'graph'
LIB_CHAINS = ROOT / 'data' / 'dorks' / 'google' / 'chains.yaml'
KNOW_IDX = ROOT / 'artifacts' / 'knowledge' / 'index.json'


def build_graph() -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    runs = load_all_runs()
    seen = set()
    for r in runs:
        rid = r.get('run_id')
        if rid and rid not in seen:
            nodes.append({"id": rid, "type": "run", "label": rid})
            seen.add(rid)
        for q in (r.get('planned_queries') or []):
            qid = f"q:{abs(hash(q))}"
            if qid not in seen:
                nodes.append({"id": qid, "type": "query", "label": q})
                seen.add(qid)
            edges.append({"src": rid, "dst": qid, "rel": "produced"})
    try:
        ch = yaml.safe_load(LIB_CHAINS.read_text()) or {}
        for c in ch.get('chains', []) or []:
            cid = f"chain:{c.get('name')}"
            if cid not in seen:
                nodes.append({"id": cid, "type": "chain", "label": c.get('name')})
                seen.add(cid)
    except Exception:
        pass
    try:
        idx = json.loads(KNOW_IDX.read_text())
        for n in idx.get('notes', []) or []:
            nid = f"note:{n.get('id')}"
            if nid not in seen:
                nodes.append({"id": nid, "type": "note", "label": n.get('title') or n.get('id')})
                seen.add(nid)
    except Exception:
        pass
    g = {"nodes": nodes, "edges": edges}
    (ART / 'graph.json').write_text(json.dumps(g, ensure_ascii=False, indent=2))
    return g
