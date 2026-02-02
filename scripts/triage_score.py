#!/usr/bin/env python3
from __future__ import annotations
import json
from k1.modules.triage.scoring_service import triage_for_fingerprints

SAMPLES = [
    [{"tech": "nginx", "version": "1.24.0"}],
    [{"tech": "kibana"}],
    [{"tech": "confluence"}],
]

if __name__ == '__main__':
    for s in SAMPLES:
        res = triage_for_fingerprints(s, topk=10)
        print(json.dumps({"fingerprints": s, "top": res[:3]}, ensure_ascii=False))
