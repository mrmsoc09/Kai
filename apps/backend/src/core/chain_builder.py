from __future__ import annotations
from typing import List, Dict, Any
import itertools

# Placeholder algorithm: pairwise/triad combinations by shared asset and complementary controls
# Real system would use networkx and causal scoring.

def propose_chains(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    # naive grouping by asset
    by_asset = {}
    for f in findings:
        for a in f.get('assets', ['unknown']):
            by_asset.setdefault(a, []).append(f)
    for asset, fs in by_asset.items():
        for k in range(2, min(4, len(fs))+1):
            for combo in itertools.combinations(fs, k):
                sev = max(f.get('severity_score', 2) for f in combo) + (k-1)  # lift per link
                out.append({
                    'asset': asset,
                    'combo_size': k,
                    'chain_severity_score': sev,
                    'chain_members': [f.get('id') for f in combo]
                })
    # sort by severity score desc
    out.sort(key=lambda x: x['chain_severity_score'], reverse=True)
    return out[:50]
