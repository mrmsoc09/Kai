# naabu — Tool Overview

naabu is a fast port scanner by ProjectDiscovery. It identifies open ports on discovered hosts, focusing on web-relevant and high-value service ports for bug bounty work.

## Output Format
`host:port` pairs, one per line.

## Pipeline Role
Phase 2, after httpx confirms live hosts. Input: live host list. Output: host:port pairs → feeds nuclei with port-aware templates.
