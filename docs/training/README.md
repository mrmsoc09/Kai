# KAISON AI — Synthetic Training Data Pipeline

Generate high-fidelity training data for Kai's 51 tool agents and 7 crew orchestration agents using real vulnerability disclosures from NVD, Exploit-DB, and HackerOne.

## Quick Start

```bash
# 1. Install gemini-cli
npm install -g @google/generative-ai-cli
gemini auth login

# 2. Generate one batch (110 examples) interactively
gemini --model gemini-2.5-pro \
  --tools google_search \
  -p "$(cat docs/training/gemini_synthetic_training_data_prompt.md)" \
  > docs/training/output/my_batch.jsonl

# 3. Generate multiple batches automatically
chmod +x docs/training/run_synthetic_training.sh
NUM_BATCHES=5 docs/training/run_synthetic_training.sh

# 4. Split into train/val/test
python3 docs/training/split_dataset.py \
  docs/training/output/combined_<batch_id>.jsonl \
  --ratio 0.8,0.1,0.1
```

---

## What Gets Generated

Each **batch** produces **110 JSONL lines**:

| Type | Count | Description |
|------|-------|-------------|
| Tool-chain examples | 100 | Single or multi-tool vulnerability discovery scenarios |
| Crew coordination | 10 | Multi-agent debate sequences (Hunter vs Skeptic AutoGen pattern) |

### Coverage per batch
- **12 specialist scenarios** (S1–S12) always included: subdomain takeover, JWT bypass, stored XSS, SSRF, leaked API keys, SQLi, GraphQL IDOR, nuclei CVE match, business logic, S3 misconfig, path traversal, multi-agent dedup conflict
- **All 9 pipeline phases** represented
- **30/40/30 difficulty split**: easy / medium / hard
- **15–20% false positives** (critical for FP calibration)
- **5%+ out-of-scope** examples (tests scope rejection logic)
- **Governance bands 0–3** distributed across examples

---

## Output Schema

Each JSONL line is a self-contained training example with these top-level keys:

```
id                  — unique training example ID
source_reference    — real-world source (NVD CVE, Exploit-DB ID, HackerOne report)
scenario            — target context, scope, phase
tool_chain          — ordered list of tool invocations with stdout/stderr samples
finding             — vulnerability details, CVSS, reproduction steps, remediation
agent_reasoning     — hypothesis → evidence chain → escalation decision
governance          — scope validation, band classification, approval status
metadata            — difficulty, tags, batch info
```

See `gemini_synthetic_training_data_prompt.md` for the complete schema definition.

---

## Batch Customization

Pass additional focus topics to shift the data distribution:

```bash
# Focus on API auth bypass
EXTRA="Focus exclusively on JWT/OAuth2 authentication bypass patterns from HackerOne 2024-2025."
gemini --model gemini-2.5-pro \
  -p "$(cat docs/training/gemini_synthetic_training_data_prompt.md)

$EXTRA" > output/api_auth_batch.jsonl

# Focus on a specific phase
EXTRA="Generate examples exclusively from phase_5_secrets and phase_6_vuln_scanning."
```

### Environment variables for `run_synthetic_training.sh`

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MODEL` | `gemini-2.5-pro` | Model to use |
| `NUM_BATCHES` | `5` | Number of batches to generate |
| `BATCH_SIZE` | `100` | Tool-chain examples per batch |

---

## Dataset Splits

After splitting, the `splits/` directory contains:

```
splits/<batch_name>/
  train.jsonl              — 80% stratified by severity + band
  val.jsonl                — 10%
  test.jsonl               — 10%
  crew_coordination.jsonl  — all crew dialogue examples
  false_positives.jsonl    — FP-only subset for calibration
  by_phase/                — per-pipeline-phase subsets
    phase_1_2_recon.jsonl
    phase_3_discovery.jsonl
    ...
  by_vuln_class/           — per-vulnerability-class subsets
    xss.jsonl
    sql_injection.jsonl
    ...
```

---

## Quality Gates

The prompt enforces 10 quality gates (G1–G10). Manually spot-check with:

```bash
# Pretty-print first example
head -1 output/combined_<batch>.jsonl | python3 -m json.tool

# Validate all lines are valid JSON
python3 -c "
import sys, json
errors = 0
with open(sys.argv[1]) as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line: continue
        try: json.loads(line)
        except: print(f'Line {i}: INVALID'); errors += 1
print(f'Done. {errors} errors.')
" output/combined_<batch>.jsonl

# Check severity distribution
python3 -c "
import sys, json, collections
counts = collections.Counter()
with open(sys.argv[1]) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        obj = json.loads(line)
        counts[obj.get('finding', {}).get('severity', 'N/A')] += 1
for k, v in counts.most_common():
    print(f'{k:15s} {v}')
" output/combined_<batch>.jsonl
```

---

## Integration with Kai Training Pipeline

Once data is generated and split:

1. **Fine-tuning** (if using Vertex AI or OpenAI fine-tuning): convert JSONL to the provider's conversation format
2. **Few-shot priming**: load `by_phase/<phase>.jsonl` examples into the crew agent's system prompt dynamically
3. **Novelty calibration**: use `novelty_score` field to calibrate the dedup engine's threshold
4. **FP calibration**: use `false_positives.jsonl` to tune `FalsePositiveDetector` heuristic weights

---

## Files

| File | Purpose |
|------|---------|
| `gemini_synthetic_training_data_prompt.md` | The main Gemini CLI prompt — paste or pipe to `gemini -p` |
| `run_synthetic_training.sh` | Batch runner with validation, stats, and rate limiting |
| `split_dataset.py` | Stratified train/val/test splitter with per-phase subsets |
| `output/` | Generated JSONL batches (git-ignored) |
| `splits/` | Post-split datasets (git-ignored) |

---

## Sources

- **NVD API**: `https://services.nvd.nist.gov/rest/json/cves/2.0`
- **Exploit-DB**: `https://www.exploit-db.com/search?type=webapps`
- **HackerOne Hacktivity**: `https://hackerone.com/hacktivity?querystring=disclosed`
