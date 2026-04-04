# Faraday-Community False Positives

## Deduplication Risks
Over-aggressive matching may miss related-but-different findings.

## Confidence Inflation
Adding tools mechanically boosts confidence. Manual review still required.

## Tool Disagreement
One tool says critical, another says medium. Faraday keeps all fields (may conflict).

## Mitigation
Use master_findings.json as starting point, not final report. Manual review essential.
