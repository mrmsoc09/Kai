# dalfox — Tool Overview

dalfox is a powerful XSS scanning tool that finds reflected, DOM, and stored XSS vulnerabilities with higher accuracy than nuclei XSS templates. It confirms payloads actually execute before reporting.

## Input Source
URLs with parameters from `gf xss` output in Phase 3. Pre-qualification is essential — blind scanning all URLs without parameter filtering is inefficient.

## Output Format
JSON with confirmed XSS payloads and affected parameters.

## Pipeline Role
Phase 4 XSS scanning. Input: gf-filtered XSS candidate URLs → dalfox → vision validation.
