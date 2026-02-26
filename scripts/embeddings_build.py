#!/usr/bin/env python3
from __future__ import annotations
import os, json
from typing import List, Dict, Any
from k1.modules.vector.embedding import build_index

ART_DIR = "/a0/usr/projects/main-startup-build/k1/artifacts"
NVD_PATH = os.path.join(ART_DIR, 'ingest', 'nvd_recent.jsonl')
EMB_PATH = os.path.join(ART_DIR, 'embeddings.jsonl')


def _load_nvd_rows(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows

STUB = [
    {"cve_id": "CVE-2021-44228", "description": "Apache Log4j2 JNDI Lookup remote code execution (Log4Shell)", "cwes": ["CWE-20", "CWE-74"], "published": "2021-12-10T00:00:00Z"},
    {"cve_id": "CVE-2022-26134", "description": "Atlassian Confluence OGNL injection remote code execution", "cwes": ["CWE-94"], "published": "2022-06-02T00:00:00Z"},
    {"cve_id": "CVE-2019-7609", "description": "Kibana Timelion expression injection RCE", "cwes": ["CWE-94"], "published": "2019-03-28T00:00:00Z"},
    {"cve_id": "CVE-2020-14882", "description": "Oracle WebLogic Console RCE via unauthenticated login bypass", "cwes": ["CWE-306"], "published": "2020-11-01T00:00:00Z"},
    {"cve_id": "CVE-2017-5638", "description": "Apache Struts2 Jakarta Multipart parser OGNL injection RCE", "cwes": ["CWE-94"], "published": "2017-03-10T00:00:00Z"},
    {"cve_id": "CVE-2021-26855", "description": "Microsoft Exchange SSRF (ProxyLogon) leading to RCE chain", "cwes": ["CWE-918"], "published": "2021-03-02T00:00:00Z"},
    {"cve_id": "CVE-2018-11776", "description": "Apache Struts2 S2-057 namespace OGNL injection RCE", "cwes": ["CWE-94"], "published": "2018-08-22T00:00:00Z"}
]

if __name__ == '__main__':
    rows = _load_nvd_rows(NVD_PATH)
    if not rows:
        rows = STUB
    out = build_index(rows, text_fields=["cve_id", "description", "cwes"], out_jsonl=EMB_PATH)
    print(out)
