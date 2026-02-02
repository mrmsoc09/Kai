
# BBP Programs Knowledge Bank (JSONL)
Each line is one JSON object with fields:
- id: stable slug (string)
- name: program name (string)
- platform: enum [direct, hackerone, bugcrowd,intigriti, yeswehack, disclosed]
- program_url: canonical landing page
- scope_url: explicit scope/rules page (may equal program_url)
- policy_url: full policy/terms/rules page
- submission_url: portal for submissions (if separate)
- payout_max_usd: number|null (max advertised)
- payout_notes: string notes on tiers
- acceptance_signal: string|null (e.g., H1 signal/impact proxy)
- acceptance_rate: number|null (0..1 if published)
- exploitability_tags: [web, api, mobile, cloud, iam, crypto, hardware, desktop]
- likelihood_notes: short rationale for exploitability likelihood
- data_sources: [urls]
- source_verified: bool (this entry populated from official/public page)
- source_checked_at: ISO8601
- priority_hint: high|medium|low (heuristic for planning queue)
- market: sector tag (e.g., cloud, consumer, fintech, enterprise)
