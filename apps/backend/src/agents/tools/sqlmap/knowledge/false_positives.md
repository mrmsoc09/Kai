# sqlmap — False Positives

## WAF-Induced FPs
Higher false positive rate on WAF-protected targets. WAF blocks may return responses that sqlmap misinterprets as injection indicators.

## Time-Based FPs
Time-based blind SQLi detection is prone to false positives due to network latency variations. Prefer boolean-based (`--technique B`) for reliability.

## Verification
Always verify SQLi findings manually or via vision validation before reporting. A WAF block that looks like a boolean response difference can fool automated detection.
