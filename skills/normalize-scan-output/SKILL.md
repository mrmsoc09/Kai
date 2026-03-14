# normalize-scan-output

Purpose: enforce normalized output shape for heterogeneous scanner results.

## Steps

1. Use parser mode mapping in `tool_adapters_bugbounty.py`:
   - `lines`
   - `jsonl`
   - `json_or_lines`
   - `nmap_xml`
2. Include provenance:
   - command
   - exit_code
   - attempts
3. Create evidence object:
   - `create_evidence_object(...)`
4. Ensure result can feed:
   - artifact/observation ingestion
   - correlation (`recon_correlation.py`)
