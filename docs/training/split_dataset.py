#!/usr/bin/env python3
"""
KAISON AI — Training Dataset Splitter
Splits a combined JSONL training file into train/val/test sets
and produces per-phase and per-severity stratified subsets.

Usage:
    python3 docs/training/split_dataset.py <combined.jsonl> [--ratio 0.8,0.1,0.1]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    examples = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                examples.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  ⚠️  Line {lineno}: invalid JSON — {e}", file=sys.stderr)
    return examples


def write_jsonl(path: Path, examples: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"  ✅  Wrote {len(examples):5d} examples → {path}")


def stratified_split(
    examples: list[dict],
    train_ratio: float,
    val_ratio: float,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Stratify by severity + governance_band to preserve distribution."""
    random.seed(seed)

    buckets: dict[str, list[dict]] = defaultdict(list)
    for ex in examples:
        severity = ex.get("finding", {}).get("severity", "unknown")
        band = ex.get("governance", {}).get("governance_band", "unknown")
        key = f"{severity}|{band}"
        buckets[key].append(ex)

    train, val, test = [], [], []
    for items in buckets.values():
        random.shuffle(items)
        n = len(items)
        n_train = max(1, int(n * train_ratio))
        n_val = max(1, int(n * val_ratio))
        train.extend(items[:n_train])
        val.extend(items[n_train : n_train + n_val])
        test.extend(items[n_train + n_val :])

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)
    return train, val, test


def main() -> None:
    parser = argparse.ArgumentParser(description="Split KAISON AI training JSONL")
    parser.add_argument("input", type=Path, help="Combined JSONL input file")
    parser.add_argument(
        "--ratio",
        default="0.8,0.1,0.1",
        help="train,val,test split ratios (default: 0.8,0.1,0.1)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    ratios = [float(r) for r in args.ratio.split(",")]
    if len(ratios) != 3 or abs(sum(ratios) - 1.0) > 0.01:
        sys.exit("❌  --ratio must be three comma-separated values summing to 1.0")

    train_r, val_r, _ = ratios
    out_dir = args.input.parent / "splits" / args.input.stem
    print(f"\n📂  Input  : {args.input}")
    print(f"📂  Output : {out_dir}/\n")

    examples = load_jsonl(args.input)
    if not examples:
        sys.exit("❌  No valid examples found in input file.")

    print(f"  Loaded {len(examples)} examples")

    # Separate crew coordination from tool-chain examples
    crew_examples = [e for e in examples if e.get("type") == "crew_coordination"]
    tool_examples = [e for e in examples if e.get("type") != "crew_coordination"]

    print(f"  Tool-chain examples  : {len(tool_examples)}")
    print(f"  Crew coordination    : {len(crew_examples)}\n")

    # Split tool-chain examples (stratified)
    train, val, test = stratified_split(tool_examples, train_r, val_r, seed=args.seed)

    write_jsonl(out_dir / "train.jsonl", train)
    write_jsonl(out_dir / "val.jsonl", val)
    write_jsonl(out_dir / "test.jsonl", test)
    write_jsonl(out_dir / "crew_coordination.jsonl", crew_examples)

    # Per-phase subsets (useful for phase-specific fine-tuning)
    phase_buckets: dict[str, list[dict]] = defaultdict(list)
    for ex in tool_examples:
        phase = ex.get("scenario", {}).get("phase", "unknown")
        phase_buckets[phase].append(ex)

    print(f"\n📊  Per-phase subsets:")
    for phase, items in sorted(phase_buckets.items()):
        write_jsonl(out_dir / "by_phase" / f"{phase}.jsonl", items)

    # Per-vulnerability-class subsets
    vuln_buckets: dict[str, list[dict]] = defaultdict(list)
    for ex in tool_examples:
        vuln_class = ex.get("finding", {}).get("vulnerability_class", "Unknown")
        vuln_buckets[vuln_class].append(ex)

    print(f"\n📊  Per-vuln-class subsets:")
    for vuln_class, items in sorted(vuln_buckets.items()):
        safe_name = vuln_class.lower().replace(" ", "_").replace("/", "_")
        write_jsonl(out_dir / "by_vuln_class" / f"{safe_name}.jsonl", items)

    # False-positive subset (high value for FP calibration)
    fp_examples = [e for e in tool_examples if e.get("finding", {}).get("is_false_positive")]
    if fp_examples:
        write_jsonl(out_dir / "false_positives.jsonl", fp_examples)

    print(f"\n✅  Dataset split complete → {out_dir}/")
    print(f"\n   train  : {len(train)}")
    print(f"   val    : {len(val)}")
    print(f"   test   : {len(test)}")
    print(f"   crew   : {len(crew_examples)}")
    print(f"   FP set : {len(fp_examples)}")


if __name__ == "__main__":
    main()
