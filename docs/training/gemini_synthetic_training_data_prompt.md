# Gemini CLI Prompt: Synthetic Training Data for KAISON AI Agents

> **Usage**:  
> ```bash
> gemini -p "$(cat docs/training/gemini_synthetic_training_data_prompt.md)" \
>   --model gemini-2.5-pro \
>   --output docs/training/output/synthetic_training_batch_$(date +%Y%m%d_%H%M%S).jsonl
> ```
>
> Or for interactive generation with web access enabled:
> ```bash
> gemini --model gemini-2.5-pro \
>   --tools google_search \
>   -p "$(cat docs/training/gemini_synthetic_training_data_prompt.md)"
> ```

---

## SYSTEM CONTEXT

You are a specialist AI trainer building a **high-fidelity synthetic dataset** for KAISON AI — an autonomous bug bounty hunting platform with 51 specialist tool agents, 7 crew orchestration agents, and a 9-phase vulnerability discovery pipeline. The agents must reason like senior penetration testers who have read thousands of real disclosures.

Your dataset will be used to:
1. **Fine-tune** specialist tool agents (tool selection, invocation, output interpretation)
2. **Few-shot prime** crew orchestration agents (multi-agent coordination, escalation, de-duplication)
3. **Train** the governance layer (scope validation, band classification, approval gate decisions)
4. **Calibrate** the novelty/deduplication engine (finding similarity scoring)

---

## PHASE 1 — REAL DATA RETRIEVAL (perform before synthesis)

Before generating synthetic examples, fetch and study **at least 20 real vulnerability disclosures** across all three sources below. Use your web access or knowledge of these sources:

### Source A — NVD (National Vulnerability Database)
- URL: `https://nvd.nist.gov/vuln/search`
- API: `https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=20&startIndex=0`
- Prioritize recent CVEs (2023–2025) across these CWE categories:
  - CWE-79 (XSS), CWE-89 (SQLi), CWE-22 (Path Traversal)
  - CWE-287 (Auth Bypass), CWE-200 (Info Disclosure), CWE-918 (SSRF)
  - CWE-502 (Deserialization), CWE-611 (XXE), CWE-434 (File Upload)
  - CWE-352 (CSRF), CWE-306 (Missing Auth), CWE-798 (Hardcoded Creds)

### Source B — Exploit-DB
- URL: `https://www.exploit-db.com/search?type=webapps`
- Pull entries with working PoC code — focus on:
  - Web application CVEs with HTTP request/response examples
  - API authentication bypasses
  - Server-side template injection (SSTI)
  - Remote code execution via deserialization or file upload
  - Subdomain takeover / dangling DNS

### Source C — HackerOne Public Disclosures
- URL: `https://hackerone.com/hacktivity?querystring=disclosed`
- Prioritize disclosed reports from major programs:
  - Shopify, GitHub, GitLab, Uber, Twitter/X, Yahoo, Airbnb, Dropbox
  - Reports with full HTTP request/response reproduction steps
  - CVSS 7.0+ (High and Critical)
  - Reports that show tool-assisted discovery (e.g., nuclei, burp, ffuf)

---

## PHASE 2 — SYNTHESIS RULES

Transform real vulnerability patterns into **synthetic but realistic** training examples. Apply these rules:

### Rule 1 — Anonymize targets
Replace real company names with fictional `.bugbounty-target.com`, `api.bugbounty-target.com`, `cdn.bugbounty-target.com` etc. Never reproduce exact private program details.

### Rule 2 — Preserve technical realism
Keep real HTTP headers, CVE IDs, CVSS scores, CWE classifications, tool flags, and reproduction steps. Synthesize variations of the payload, path, and parameter names.

### Rule 3 — Diversify difficulty
Each batch must include:
- 30% easy (single-tool finds, CVSS < 5.0)
- 40% medium (multi-tool correlation, CVSS 5.0–7.9)
- 30% hard (multi-phase, multi-agent coordination, CVSS ≥ 8.0)

### Rule 4 — Cover all 9 pipeline phases
Ensure roughly equal representation across:
1. Recon (subfinder, amass, assetfinder)
2. Fingerprinting (httpx, whatweb, wappalyzer)
3. Discovery (ffuf, gobuster, dirsearch, feroxbuster)
4. OSINT (theHarvester, spiderfoot, shodan, censys)
5. Dark Web / Secrets (trufflehog, gitleaks, git-secrets, gitrob)
6. Vulnerability Scanning (nuclei, nikto, wpscan, jaeles)
7. API Testing (arjun, kiterunner, swagger-inspector, graphqlmap)
8. Advanced/Exploitation (sqlmap, XSStrike, commix)
9. Aggregation / Reporting (finding correlation, deduplication, CVSS calibration)

### Rule 5 — Include negative examples
20% of examples should be **true negatives** — benign findings that agents should NOT escalate (e.g., `X-Frame-Options` missing on a static page with no sensitive data, informational nmap port scans that are expected, version disclosure of a patched component).

### Rule 6 — Governance band annotations
Every example MUST include a `governance_band` field:
- `band_0` — Passive, no authorization required
- `band_1` — Active probing, auto-approved within scope
- `band_2` — Intrusive scanning, requires human approval
- `band_3` — Exploitation, blocked unless explicitly enabled

---

## PHASE 3 — OUTPUT SCHEMA

Generate **exactly 100 training examples** per run. Output as **JSONL** (one JSON object per line). Each example MUST conform to this schema:

```json
{
  "id": "train_<uuid4>",
  "source_reference": {
    "type": "nvd|exploit_db|hackerone|synthetic",
    "id": "CVE-2024-XXXXX | EDB-XXXXX | HackerOne-XXXXXX | synthetic",
    "cwe": "CWE-79",
    "cvss_v3_score": 8.1,
    "cvss_v3_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"
  },
  "scenario": {
    "phase": "phase_3_discovery",
    "target": "app.bugbounty-target.com",
    "target_type": "web_application|api|mobile_backend|cloud_service",
    "program_type": "public_bbp|private_bbp|vdp",
    "scope_includes": ["*.bugbounty-target.com", "api.bugbounty-target.com"],
    "scope_excludes": ["admin.bugbounty-target.com", "legacy.bugbounty-target.com"],
    "context": "<1-2 sentence description of the reconnaissance already done and what triggered this phase>"
  },
  "tool_chain": [
    {
      "step": 1,
      "tool": "ffuf",
      "governance_band": "band_1",
      "rationale": "<why this tool was selected>",
      "command": "ffuf -u https://app.bugbounty-target.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt -mc 200,301,302,403 -t 40",
      "stdout_sample": "<realistic abbreviated stdout output, max 20 lines>",
      "stderr_sample": null,
      "exit_code": 0,
      "duration_seconds": 47
    }
  ],
  "finding": {
    "title": "<concise vulnerability title>",
    "description": "<2-3 sentence technical description>",
    "vulnerability_class": "XSS|SQLi|SSRF|Path Traversal|Auth Bypass|IDOR|RCE|Info Disclosure|Misconfiguration|Hardcoded Secret|Subdomain Takeover|Open Redirect|CSRF|XXE|Deserialization|Business Logic|None",
    "severity": "critical|high|medium|low|informational",
    "cvss_score": 8.1,
    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    "is_false_positive": false,
    "false_positive_reason": null,
    "reproduction_steps": [
      "Step 1: <HTTP request or tool command>",
      "Step 2: <observation>",
      "Step 3: <confirmation of impact>"
    ],
    "http_request": "GET /api/v1/users?id=../../../etc/passwd HTTP/1.1\nHost: app.bugbounty-target.com\nAuthorization: Bearer <token>",
    "http_response_snippet": "HTTP/1.1 200 OK\nContent-Type: application/json\n\n{\"data\": \"root:x:0:0:...\"}",
    "affected_component": "REST API /api/v1/users endpoint",
    "attack_vector": "Network",
    "impact": {
      "confidentiality": "High|Low|None",
      "integrity": "High|Low|None",
      "availability": "High|Low|None"
    },
    "remediation": "<1-3 concrete technical remediation steps>",
    "cve_references": ["CVE-2024-XXXXX"],
    "cwe": "CWE-22"
  },
  "agent_reasoning": {
    "crew": "recon_crew|osint_crew|vuln_crew|api_testing_crew|governance_crew",
    "initial_hypothesis": "<what the agent suspected before running the tool>",
    "evidence_chain": "<how each tool output contributed to the conclusion>",
    "confidence_score": 0.92,
    "escalation_decision": "submit|investigate_further|mark_false_positive|request_human_review",
    "escalation_rationale": "<why this decision was made>",
    "similar_finding_ids": [],
    "novelty_score": 0.87
  },
  "governance": {
    "in_scope": true,
    "scope_decision_rationale": "<how scope was validated>",
    "governance_band": "band_1",
    "approval_required": false,
    "approval_requested": false,
    "kill_switch_triggered": false
  },
  "metadata": {
    "difficulty": "easy|medium|hard",
    "training_tags": ["multi-tool", "false-positive", "scope-edge-case", "band-2-approval", "api", "auth"],
    "generated_at": "2026-05-30T00:00:00Z",
    "generator_model": "gemini-2.5-pro",
    "batch_id": "<uuid4>"
  }
}
```

---

## PHASE 4 — SPECIALIST SCENARIOS (mandatory coverage per batch)

Every batch of 100 examples MUST include at least one example from each of these specialist scenarios:

### S1 — Subdomain Takeover
- Source pattern: dangling CNAME to deprovisioned AWS S3/GitHub Pages/Heroku
- Tools: subfinder → dnsx → nuclei (takeover templates)
- Band: 1 (discovery passive), escalate to band_2 if claiming the asset

### S2 — JWT Authentication Bypass
- Source pattern: `alg:none` or weak HMAC secret (HackerOne pattern)
- Tools: kiterunner (API enumeration) → manual JWT decode → nuclei (jwt-weak-secret)
- Band: 1 (probe), must log exact JWT payload and modified claim

### S3 — Stored XSS via File Upload
- Source pattern: SVG/HTML file with embedded `<script>` served as `text/html`
- Tools: feroxbuster (find upload endpoint) → manual HTTP request → XSStrike
- Band: 2 (active exploitation requires human approval)

### S4 — SSRF via Webhook / Callback URL
- Source pattern: user-controlled URL parameter proxied server-side
- Tools: httpx (discover), arjun (param discovery), manual Burp/curl with SSRF canary
- Band: 2 (requires OOB infrastructure)

### S5 — Leaked API Key in Public Git History
- Source pattern: `.env`, `config.py`, `docker-compose.yml` committed then deleted
- Tools: gitleaks / trufflehog / git-secrets on cloned repo
- Band: 0 (passive OSINT — read-only git log)

### S6 — SQL Injection via REST API Parameter
- Source pattern: unsanitized `ORDER BY`, `LIMIT`, or filter param
- Tools: arjun → sqlmap (GET/POST mode)
- Band: 2 (sqlmap writes to DB — intrusive)

### S7 — GraphQL Introspection + IDOR
- Source pattern: exposed `__schema` + object ID enumeration
- Tools: graphqlmap → manual introspection → custom Python script
- Band: 1 (read-only introspection), band_2 if modifying data

### S8 — Nuclei Template Match — Critical CVE
- Source pattern: nuclei fires on a known CVE template (e.g., Log4Shell, Spring4Shell, MOVEit)
- Tools: httpx (alive check) → nuclei (CVE template)
- Band: 1 (nuclei detection is probe-level), escalate to human immediately (CVSS ≥ 9.0)

### S9 — Business Logic — Price Manipulation
- Source pattern: negative quantity, integer overflow in cart/checkout
- Tools: manual HTTP replay (Burp) + arjun
- Band: 2 (transactional data modification)

### S10 — Misconfigured S3 Bucket via Recon
- Source pattern: public bucket listing or unauthenticated PutObject
- Tools: amass (discover bucket hostnames) → aws cli / s3scanner
- Band: 0 (listing only), band_2 (write test)

### S11 — Path Traversal in API File Download
- Source pattern: `/api/download?file=../../../../etc/passwd`
- Tools: ffuf (directory brute) → arjun (param discovery) → manual curl
- Band: 2 (reading server files is intrusive)

### S12 — Multi-Agent Coordination — Conflicting Findings
- Scenario: Two agents independently discover what appears to be the same XSS but on different endpoints with different severity assessments. The novelty/dedup engine must resolve the conflict.
- Expected output: dedup decision, merged finding, or separate findings with cross-references

---

## PHASE 5 — CREW ORCHESTRATION SCENARIOS

Generate **10 additional multi-turn dialogue examples** representing full crew coordination sequences. Format:

```json
{
  "id": "crew_train_<uuid4>",
  "type": "crew_coordination",
  "crew": "primary_vuln_crew",
  "target": "*.bugbounty-target.com",
  "turns": [
    {
      "agent": "LeadPentesterAgent",
      "message": "<agent message>",
      "tool_calls": ["nuclei -t cves/ -u https://app.bugbounty-target.com"],
      "artifacts_produced": ["nuclei_scan_20260530.json"]
    },
    {
      "agent": "ScopeGuardianAgent",
      "message": "<scope validation message>",
      "tool_calls": [],
      "artifacts_produced": []
    },
    {
      "agent": "SkepticAgent",
      "message": "<autogen skeptic challenge — is this a real finding or FP?>",
      "tool_calls": [],
      "artifacts_produced": []
    },
    {
      "agent": "HunterAgent",
      "message": "<autogen hunter defense — evidence this is real>",
      "tool_calls": ["curl -v 'https://app.bugbounty-target.com/...'"],
      "artifacts_produced": ["reproduction_proof.txt"]
    },
    {
      "agent": "ReportWriterAgent",
      "message": "<final report summary>",
      "tool_calls": [],
      "artifacts_produced": ["finding_report_draft.md"]
    }
  ],
  "outcome": {
    "consensus": "confirmed_valid|confirmed_false_positive|needs_more_evidence",
    "final_severity": "high",
    "submitted": true
  },
  "metadata": {
    "difficulty": "hard",
    "training_tags": ["multi-agent", "autogen-debate", "false-positive-challenge"]
  }
}
```

---

## PHASE 6 — QUALITY REQUIREMENTS

Before outputting, validate every example against these gates:

| Gate | Requirement |
|------|-------------|
| **G1** | `cvss_score` matches `severity` label (critical ≥ 9.0, high 7.0–8.9, medium 4.0–6.9, low 0.1–3.9) |
| **G2** | `governance_band` is consistent with `tool_chain[*].tool` (passive tools → band_0, active probing → band_1, intrusive → band_2) |
| **G3** | `reproduction_steps` are technically executable (no hand-wavy steps) |
| **G4** | `http_request` contains valid HTTP/1.1 syntax if present |
| **G5** | `in_scope` is `false` for at least 5% of examples (test scope rejection) |
| **G6** | `is_false_positive` is `true` for at least 15–20% of examples |
| **G7** | At least 3 different `crew` values appear across the batch |
| **G8** | No two examples share the same `http_request` verbatim |
| **G9** | `novelty_score` varies realistically (0.1–0.3 for duplicate-class, 0.7–1.0 for novel) |
| **G10** | `command` strings in `tool_chain` use real flags for that tool (verify against tool manuals) |

---

## EXECUTION INSTRUCTIONS

1. **Fetch** 5–10 real disclosures from each source (NVD, Exploit-DB, HackerOne) using your web search capability or built-in knowledge.
2. **Map** each real finding to one or more synthetic training examples using the schema above.
3. **Augment** with pure synthetic variations to reach 100 total examples.
4. **Apply** the specialist scenario coverage (S1–S12) — embed these within the 100.
5. **Append** the 10 crew coordination examples (Phase 5).
6. **Validate** all 110 examples against gates G1–G10.
7. **Output** as JSONL to stdout (one JSON object per line, no markdown wrapper).

Total output: **110 lines of JSONL** (100 tool-chain examples + 10 crew coordination examples).

---

## EXAMPLE SEED (use this format as your first output line, then continue)

```json
{"id":"train_a1b2c3d4-0001","source_reference":{"type":"hackerone","id":"HackerOne-1523926","cwe":"CWE-79","cvss_v3_score":6.1,"cvss_v3_vector":"CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"},"scenario":{"phase":"phase_3_discovery","target":"app.bugbounty-target.com","target_type":"web_application","program_type":"public_bbp","scope_includes":["*.bugbounty-target.com"],"scope_excludes":["legacy.bugbounty-target.com"],"context":"Subfinder enumerated 34 subdomains. Httpx confirmed app.bugbounty-target.com returns 200. Feroxbuster found /search endpoint. Testing for reflected XSS."},"tool_chain":[{"step":1,"tool":"feroxbuster","governance_band":"band_1","rationale":"Enumerate hidden endpoints before testing for XSS injection points","command":"feroxbuster -u https://app.bugbounty-target.com -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt -x php,html,js -t 40 -o ferox_out.txt","stdout_sample":"200      GET   /search\n200      GET   /search?q=test\n301      GET   /admin -> /login","stderr_sample":null,"exit_code":0,"duration_seconds":62},{"step":2,"tool":"xsstrike","governance_band":"band_2","rationale":"Automated XSS fuzzing on discovered search parameter","command":"python3 xsstrike.py -u 'https://app.bugbounty-target.com/search?q=test'","stdout_sample":"[+] Vulnerability found at: https://app.bugbounty-target.com/search?q=<img+src=x+onerror=alert(1)>\n[+] Payload: <img src=x onerror=alert(1)>","stderr_sample":null,"exit_code":0,"duration_seconds":18}],"finding":{"title":"Reflected XSS in /search?q= parameter","description":"The q parameter on the /search endpoint reflects user input into the HTML response without encoding. An attacker can inject arbitrary JavaScript that executes in the victim's browser context, enabling session theft or phishing.","vulnerability_class":"XSS","severity":"medium","cvss_score":6.1,"cvss_vector":"CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N","is_false_positive":false,"false_positive_reason":null,"reproduction_steps":["Navigate to https://app.bugbounty-target.com/search?q=<img src=x onerror=alert(1)>","Observe JavaScript alert dialog fires in browser","Confirm the payload is reflected in page source without HTML encoding"],"http_request":"GET /search?q=<img+src=x+onerror=alert(1)> HTTP/1.1\nHost: app.bugbounty-target.com\nUser-Agent: Mozilla/5.0","http_response_snippet":"HTTP/1.1 200 OK\nContent-Type: text/html\n\n<div class=\"results\">Results for: <img src=x onerror=alert(1)></div>","affected_component":"GET /search endpoint — q parameter","attack_vector":"Network","impact":{"confidentiality":"Low","integrity":"Low","availability":"None"},"remediation":"1. HTML-encode all user-supplied input before reflection. 2. Implement Content-Security-Policy header. 3. Use a templating engine with auto-escaping enabled.","cve_references":[],"cwe":"CWE-79"},"agent_reasoning":{"crew":"primary_vuln_crew","initial_hypothesis":"Search parameter may reflect input unsanitized based on feroxbuster finding /search endpoint","evidence_chain":"Feroxbuster discovered /search endpoint → XSStrike confirmed reflected payload executes → HTTP response confirms no encoding applied","confidence_score":0.97,"escalation_decision":"submit","escalation_rationale":"High confidence, reproducible, clear impact on user sessions. No false-positive indicators.","similar_finding_ids":[],"novelty_score":0.74},"governance":{"in_scope":true,"scope_decision_rationale":"app.bugbounty-target.com matches *.bugbounty-target.com allowlist; not in excludes list","governance_band":"band_2","approval_required":true,"approval_requested":true,"kill_switch_triggered":false},"metadata":{"difficulty":"easy","training_tags":["xss","reflected","web-app","band-2-approval"],"generated_at":"2026-05-30T00:00:00Z","generator_model":"gemini-2.5-pro","batch_id":"batch_20260530_001"}}
```

Now generate the remaining 109 examples following the same schema, covering all specialist scenarios S1–S12 and Phase 5 crew coordination turns. Output raw JSONL only — no markdown, no commentary between lines.
