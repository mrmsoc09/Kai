# waybackurls — Tool Overview

waybackurls specifically queries the Wayback Machine for archived URLs. Different from gau — waybackurls focuses on a single source but can go deeper on it.

## Output Format
One URL per line. With `-dates` flag: `YYYY-MM-DD URL` per line.

## Complementary to GAU
- GAU casts a wide net across multiple sources
- waybackurls goes deep on Wayback Machine specifically
- Run both, deduplicate, combine for maximum URL coverage

## Pipeline Role
Phase 2, parallel to gau. Combined output feeds paramspider and arjun in Phase 3.
