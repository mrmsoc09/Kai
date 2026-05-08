# Real Scan Data for Training

This directory mirrors the synthetic data structure but contains parsed and chunked real scan data from Kai platform runs. Updated daily by intelligence engines.

## Directory Structure

- `targets/`: Real targets from scans
- `artifacts/`: Real artifacts (DNS, services, etc.)
- `observations/`: Real observations and findings
- `training/`: Chunked training data from real scans

## Update Process

- Intelligence engines parse completed workflows.
- Data is chunked into training samples.
- Updated via scheduled tasks (e.g., daily cron).

## Notes

- Ensure compliance: Only use authorized, anonymized data.
- Flagged as real data for training purposes.