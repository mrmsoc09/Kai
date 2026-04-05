# Arjun Advanced Techniques

## Baseline Command
`arjun -u https://target.tld/api/v1/users --stable -oJ arjun.json`

## Endpoint Targeting
Prioritize authenticated/API/admin endpoints from prior discovery tools for highest ROI.

## Method Awareness
Capture whether parameters are observed under GET or POST contexts for accurate downstream payload strategy.

## Response-Diff Logic
Parameters that change content-length, status, or key markers should be prioritized; static/no-effect parameters are downgraded.
