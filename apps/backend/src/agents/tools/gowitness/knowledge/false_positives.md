# GoWitness False Positives

## Cosmetic Similarity
Different hosts can share the same theme and appear identical despite differing backend behavior.

## Redirect Confusion
Screenshots may capture final redirected destinations; ensure canonical URL tracking is preserved.

## Dynamic Content Drift
Titles and content may change between runs due to localization, A/B tests, or auth state.

## Mitigation
Correlate screenshots with HTTP metadata and repeated captures before assigning critical priority.
