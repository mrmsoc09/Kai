# install-and-verify-tools

Purpose: install baseline runtime dependencies and verify catalog tool availability.

## Procedure

1. Prepare Python environment.
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt -r requirements-dev.txt`
2. Install host/tool dependencies.
   - `sudo bash install/bootstrap_ubuntu_22_04.sh`
3. Verify catalog install status.
   - `python3 scripts/verify_tool_registry_install.py`
4. Review verification report.
   - `output/reports/tool_install_verification.json`

## Acceptance Criteria

- no failures for default-enabled tools required by target workflow
- missing optional tools are documented before running production workflows

## Failure Handling

- if a binary is missing, install it with official package/go installer
- if install command exists but verification fails, run the verification command manually
- keep verification output attached to issue/PR notes
