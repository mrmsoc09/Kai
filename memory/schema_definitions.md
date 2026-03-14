# Schema Definitions Memory

Canonical normalized models are defined in:

- `apps/backend/src/schemas/bugbounty.py`

Core entities:

- Target
- ScopeRule
- WorkflowRun
- StageRun
- ToolExecution
- DiscoveredAsset
- DNSRecord
- LiveService
- WebApplication
- URLRecord
- EndpointRecord
- ParameterRecord
- TechnologyFingerprint
- SecretFinding
- VulnCandidate
- CorrelationRecord
- AnalystExport

Persistence surfaces:

- canonical backend DB models for campaign execution lifecycle
- normalized workflow JSONL artifacts via `WorkflowDataStore`

Rule: new scanner outputs should normalize into existing schema types first; add new types only when necessary and documented.
