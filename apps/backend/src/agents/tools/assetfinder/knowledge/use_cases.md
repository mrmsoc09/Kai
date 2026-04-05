# Assetfinder Use Cases

## Rapid Baseline Collection
Use assetfinder at campaign start to quickly seed the first target queue for dnsx/httpx.

## Delta Tracking
Run assetfinder periodically and diff with prior snapshots to detect newly exposed hosts.

## Large Program Coverage
Use it as one component in a three-tool passive set (`assetfinder`, `subfinder`, `amass`) to increase subdomain recall.

## Low-Noise Mode
For strict scope operations, keep `--subs-only` enabled and let policy checks reject anything outside authorized targets.

## Analyst Handoff
Provide a short list of high-value labels (admin/api/staging/internal) to prioritize manual review and follow-on scans.
