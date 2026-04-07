#!/usr/bin/env python3
from __future__ import annotations
import argparse
from k1.modules.ingest.nvd_ingest import ingest_recent
from k1.modules.ingest.epss_ingest import ingest as ingest_epss
from k1.modules.ingest.kev_ingest import ingest as ingest_kev
from k1.modules.ingest.exploitdb_ingest import ingest as ingest_exdb
ACTIONS = {"nvd": ingest_recent, "epss": ingest_epss, "kev": ingest_kev, "exploitdb": ingest_exdb}

def main():
    ap = argparse.ArgumentParser(description="KAISON AI knowledge ingestion runner")
    ap.add_argument("what", choices=ACTIONS.keys())
    args = ap.parse_args()
    path = ACTIONS[args.what]()
    print(path)
if __name__ == "__main__":
    main()
