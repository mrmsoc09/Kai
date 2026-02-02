#!/usr/bin/env python3
import os, sys, json, yaml
from argparse import ArgumentParser

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
LIB_DIR = os.path.join(BASE, "data", "dorks", "google")

def main():
    p = ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--query")
    p.add_argument("--chain")
    args = p.parse_args()
    with open(os.path.join(LIB_DIR, "base.yaml"), "r") as f:
        base = yaml.safe_load(f)
    executed = []
    if args.chain:
        with open(os.path.join(LIB_DIR, "chains.yaml"), "r") as f:
            chains = yaml.safe_load(f)
        cdef = next((c for c in chains.get("chains", []) if c.get("name") == args.chain), None)
        if not cdef:
            print(json.dumps({"error": "chain not found"})); sys.exit(1)
        for step in cdef.get("steps", []):
            executed.append(step["query"].replace("{target}", args.target))
    elif args.query:
        executed.append(args.query.replace("{target}", args.target))
    else:
        for v in list(base.get("categories", {}).values())[:1]:
            for q in v:
                executed.append(q.replace("{target}", args.target))
    print(json.dumps({"mode":"plan","executed":executed}))

if __name__ == "__main__":
    main()
