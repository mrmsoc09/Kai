# sqlmap — Tool Overview

sqlmap is the standard SQL injection detection tool. In automated BBP scanning, always run in **safe mode — detection only, never exploitation**.

## Safety Rules (Non-Negotiable in Automation)
- Safe mode flags: `--level=2 --risk=1 --batch`
- NEVER use `--level=3 --risk=3` in automation
- NEVER use `--dump` in automated scanning
- NEVER use `--os-shell` or `--os-cmd`

## Input Source
URLs with parameters from `gf sqli` output. Pre-qualified parameters produce better results.

## Output
Confirms injection type and database type. Report: URL + parameter + injection type + DB type. No data extraction.
