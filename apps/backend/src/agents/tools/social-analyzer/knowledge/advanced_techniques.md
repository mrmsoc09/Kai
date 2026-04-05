# Social-Analyzer Advanced Techniques

## Baseline Command
`social-analyzer --username candidate --metadata --output social.json`

## Complement Strategy
Use Sherlock for breadth (where accounts exist), then Social-Analyzer for depth (what those accounts reveal).

## Metadata Focus
Extract follower counts, bio text, outbound links, and platform indicators to improve prioritization confidence.

## Output Handling
Normalize JSON output into consistent schema fields for EvidenceAnalystAgent consumption.
