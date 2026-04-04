# nuclei — Tool Overview

nuclei is a template-based vulnerability scanner by ProjectDiscovery. It runs curated detection templates against targets and reports confirmed matches.

## Most Important Agent Function
Intelligent template selection based on Phase 2 fingerprinting results. Running all templates blindly wastes time and triggers WAFs. Targeted templates based on detected technology maximize findings per minute.

## Output Format
JSON lines (with `-jsonl`) or plaintext.

## Pipeline Role
Phase 3+ active scanning. Templates selected based on tech stack from httpx. Input: live hosts with metadata.
