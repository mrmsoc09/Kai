# Gitleaks Advanced Techniques

## Ruleset Differences
Gitleaks uses hand-crafted regex rules. Trufflehog uses entropy detection and verification. Different coverage. Complementary approaches.

## High-Confidence Detection
Regex patterns for specific secret formats (AWS key patterns, JWT structure, etc). Lower false positive rate than entropy-based.

## Test Fixture Handling
Gitleaks filters test and mock files. Configure exclusions for test directories. Be aware gitleaks may still flag test data.

## Filesystem and Git History
Can scan both filesystem (--no-git) and full git history. Full history required for breach assessment.

## Output Format
JSON with rule ID, file path, commit, line number. All information except secret value.
