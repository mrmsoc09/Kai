#!/usr/bin/env bash
# ============================================================
# KAISON AI — Synthetic Training Data Generator
# Uses gemini-cli to produce JSONL training batches from real
# vulnerability disclosures (NVD, Exploit-DB, HackerOne).
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/gemini_synthetic_training_data_prompt.md"
OUTPUT_DIR="$SCRIPT_DIR/output"
BATCH_SIZE="${BATCH_SIZE:-100}"          # examples per batch
NUM_BATCHES="${NUM_BATCHES:-5}"          # number of batches to generate
MODEL="${GEMINI_MODEL:-gemini-2.5-pro}"

# ── Validate prerequisites ──────────────────────────────────
command -v gemini >/dev/null 2>&1 || {
  echo "❌  gemini-cli not found. Install: npm install -g @google/generative-ai-cli"
  exit 1
}
[[ -f "$PROMPT_FILE" ]] || { echo "❌  Prompt file not found: $PROMPT_FILE"; exit 1; }

mkdir -p "$OUTPUT_DIR"

# ── Optional: per-batch topic seeds ────────────────────────
TOPIC_SEEDS=(
  "Focus heavily on API authentication bypass and JWT flaws (CWE-287, CWE-345) from HackerOne 2023-2025 disclosures."
  "Focus on cloud misconfiguration: S3 bucket exposure, GCP IAM issues, Azure storage SAS token leaks from Exploit-DB and NVD."
  "Focus on injection vulnerabilities: SQLi (CWE-89), SSTI (CWE-1336), command injection (CWE-78) from recent CVEs."
  "Focus on client-side vulnerabilities: XSS (CWE-79), CSRF (CWE-352), open redirect (CWE-601), subdomain takeover."
  "Focus on secrets and supply chain: leaked API keys (CWE-798), dependency confusion, git history exposure from public repos."
)

# ── Generate batches ────────────────────────────────────────
BATCH_ID="batch_$(date +%Y%m%d_%H%M%S)"
COMBINED_FILE="$OUTPUT_DIR/combined_${BATCH_ID}.jsonl"

echo "🚀  Starting synthetic training data generation"
echo "   Model:   $MODEL"
echo "   Batches: $NUM_BATCHES × $BATCH_SIZE examples"
echo "   Output:  $OUTPUT_DIR"
echo ""

TOTAL=0
FAILED=0

for i in $(seq 1 "$NUM_BATCHES"); do
  BATCH_FILE="$OUTPUT_DIR/batch_${BATCH_ID}_$(printf '%02d' "$i").jsonl"
  TOPIC_IDX=$(( (i - 1) % ${#TOPIC_SEEDS[@]} ))
  TOPIC="${TOPIC_SEEDS[$TOPIC_IDX]}"

  echo "📦  Batch $i/$NUM_BATCHES — $TOPIC"

  FULL_PROMPT="$(cat "$PROMPT_FILE")

## ADDITIONAL FOCUS FOR THIS BATCH
$TOPIC
Batch number: $i of $NUM_BATCHES. Batch ID: ${BATCH_ID}_$(printf '%02d' "$i").
Generate exactly $BATCH_SIZE tool-chain examples plus 10 crew coordination examples = 110 total JSONL lines."

  if gemini \
      --model "$MODEL" \
      --tools google_search \
      -p "$FULL_PROMPT" \
      > "$BATCH_FILE" 2>/dev/null; then

    LINE_COUNT=$(wc -l < "$BATCH_FILE")
    # Validate JSONL — each line must parse as JSON
    VALID=0
    INVALID=0
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      if echo "$line" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        ((VALID++)) || true
        echo "$line" >> "$COMBINED_FILE"
      else
        ((INVALID++)) || true
      fi
    done < "$BATCH_FILE"

    echo "   ✅  $VALID valid / $INVALID invalid lines (raw: $LINE_COUNT)"
    TOTAL=$((TOTAL + VALID))
  else
    echo "   ❌  Batch $i failed"
    ((FAILED++)) || true
  fi

  # Respect Gemini rate limits between batches
  if [[ $i -lt $NUM_BATCHES ]]; then
    echo "   ⏳  Sleeping 15s (rate limit buffer)..."
    sleep 15
  fi
done

# ── Summary ─────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "✅  Generation complete"
echo "   Total valid examples : $TOTAL"
echo "   Failed batches       : $FAILED"
echo "   Combined output      : $COMBINED_FILE"
echo "══════════════════════════════════════════════"

# ── Quick stats ─────────────────────────────────────────────
if [[ -f "$COMBINED_FILE" ]] && command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "📊  Dataset statistics:"
  python3 - "$COMBINED_FILE" <<'PYEOF'
import sys, json, collections

path = sys.argv[1]
severity_counts = collections.Counter()
phase_counts = collections.Counter()
band_counts = collections.Counter()
fp_count = 0
total = 0

with open(path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        if "finding" in obj:
            severity_counts[obj["finding"].get("severity", "unknown")] += 1
            if obj["finding"].get("is_false_positive"):
                fp_count += 1
        if "scenario" in obj:
            phase_counts[obj["scenario"].get("phase", "unknown")] += 1
        if "governance" in obj:
            band_counts[obj["governance"].get("governance_band", "unknown")] += 1

print(f"  Total examples   : {total}")
print(f"  False positives  : {fp_count} ({fp_count/max(total,1)*100:.1f}%)")
print(f"\n  Severity distribution:")
for sev in ["critical","high","medium","low","informational"]:
    n = severity_counts.get(sev, 0)
    bar = "█" * (n // max(total // 40, 1))
    print(f"    {sev:14s} {n:4d}  {bar}")
print(f"\n  Governance bands:")
for band in sorted(band_counts):
    print(f"    {band:12s} {band_counts[band]:4d}")
print(f"\n  Top phases:")
for phase, count in phase_counts.most_common(5):
    print(f"    {phase:30s} {count:4d}")
PYEOF
fi

echo ""
echo "🎯  Next steps:"
echo "   1. Review sample: head -1 $COMBINED_FILE | python3 -m json.tool"
echo "   2. Split for fine-tuning: python3 docs/training/split_dataset.py $COMBINED_FILE"
echo "   3. Upload to training pipeline: see docs/training/README.md"
