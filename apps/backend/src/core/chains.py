from __future__ import annotations
from typing import List, Dict, Any, Tuple
import networkx as nx

SEV_WEIGHT = {
    'info': 0.5,
    'low': 1.0,
    'medium': 2.0,
    'high': 3.5,
    'critical': 5.0,
}

EDGE_BONUS = {
    'credential reuse': 1.5,
    'csrf→privilege': 1.2,
    'xss→session steal': 1.3,
    'lfi→rce': 2.0,
    's3→pii': 1.5,
}


def _sev_w(sev: str | None) -> float:
    return SEV_WEIGHT.get((sev or '').lower(), 1.0)


def build_chain(finds: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compose an attack graph and identify highest-impact chains.
    - Nodes: findings (id or title)
    - Edges: inferred by shared asset/scope and compatible attack semantics
    - Score: sum of node severities + edge bonuses; chain length and diversity boost
    """
    g = nx.DiGraph()
    # Add nodes
    for f in finds:
        nid = f.get('id') or f.get('title') or f"node-{id(f)}"
        g.add_node(nid, **{
            'title': f.get('title') or nid,
            'sev': (f.get('severity') or 'low').lower(),
            'scope': f.get('scope'),
            'impact': f.get('impact'),
            'category': f.get('category') or f.get('type') or 'generic',
        })
    # Infer edges
    nodes = list(g.nodes())
    for i, a in enumerate(nodes):
        for b in nodes[i+1:]:
            na = g.nodes[a]; nb = g.nodes[b]
            # shared scope or asset-like overlap
            shared = False
            sa, sb = (na.get('scope') or ''), (nb.get('scope') or '')
            if sa and sb and any(tok in sb for tok in sa.split()):
                shared = True
            if not shared and na.get('category') == nb.get('category'):
                shared = True
            if shared:
                # Direction heuristic: privilege escalation or data exfil flows
                bonus = 0.0
                if 'csrf' in (na.get('title','').lower()) and 'privilege' in (nb.get('impact','') or '').lower():
                    bonus = EDGE_BONUS.get('csrf→privilege', 1.0)
                    g.add_edge(a, b, bonus=bonus, reason='csrf→privilege')
                elif 'xss' in (na.get('title','').lower()) and 'session' in (nb.get('impact','') or '').lower():
                    bonus = EDGE_BONUS.get('xss→session steal', 1.1)
                    g.add_edge(a, b, bonus=bonus, reason='xss→session steal')
                else:
                    g.add_edge(a, b, bonus=1.0, reason='scope-link')
                # also bidirectional link if categories suggest alternative path
                if na.get('category') != nb.get('category'):
                    g.add_edge(b, a, bonus=1.0, reason='scope-link')
    # Score paths (limit length to avoid explosion)
    best: Tuple[float, List[str]] = (0.0, [])
    for s in g.nodes():
        # bounded DFS depth=5
        for t in g.nodes():
            if s == t:
                continue
            try:
                # consider simple paths up to cutoff
                for path in nx.all_simple_paths(g, s, t, cutoff=5):
                    score = 0.0
                    seen_cat = set()
                    for n in path:
                        w = _sev_w(g.nodes[n].get('sev'))
                        score += w
                        seen_cat.add(g.nodes[n].get('category'))
                    for i in range(len(path)-1):
                        e = g.get_edge_data(path[i], path[i+1]) or {}
                        score += float(e.get('bonus') or 1.0) * 0.5
                    # diversity bonus
                    score += max(0, len(seen_cat)-1) * 0.25
                    if score > best[0]:
                        best = (score, path)
            except nx.exception.NetworkXNoPath:
                continue
    out = {
        'nodes': [{ 'id': n, **g.nodes[n]} for n in g.nodes()],
        'edges': [{ 'src': u, 'dst': v, **(g.get_edge_data(u, v) or {}) } for u, v in g.edges()],
        'best_chain': { 'score': round(best[0], 3), 'path': best[1] },
    }
    # Classify severity of chain
    if best[0] >= 10:
        out['chain_severity'] = 'critical'
    elif best[0] >= 7:
        out['chain_severity'] = 'high'
    elif best[0] >= 4:
        out['chain_severity'] = 'medium'
    else:
        out['chain_severity'] = 'low'
    return out
