# Katana Advanced Techniques

## Default Pattern
`katana -u https://target.tld -jc -kf all -d 5 -json`

## GraphQL Detection
Tag endpoints containing `graphql` for dedicated GraphQL tooling (`graphql-cop`, schema probing workflows).

## JS Intelligence
JavaScript bundle URLs are high-priority because they often disclose hidden routes, tokens, or internal API references.

## Depth vs Breadth
Higher depth increases coverage but can multiply noise. Depth 5 is strong for broad app traversal without unbounded crawl spread.

## WAF Consideration
Lower `-rate-limit` in defensive environments to reduce blocking and preserve continuity.
