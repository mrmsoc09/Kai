# Github-Subdomains Advanced Techniques

## Tokened Execution
```bash
github-subdomains -d target.com -t "$GITHUB_TOKEN" -o github_subdomains_output.txt
```

## Rate-Aware Scheduling
Without a token, limit query bursts and batch targets to avoid API throttling.

## Correlated Secret Workflow
When subdomains are found in code, immediately queue repository secret scans (for example with trufflehog) to catch exposed credentials tied to newly discovered assets.

## Context Preservation
Store repository URL and file path metadata when possible for analyst reproducibility.
