# Tool Categories Memory

Catalog categories (source: `tools/registry/tool_registry.yaml`):

- recon_asset_discovery
- http_live_host
- crawling_url_discovery
- fuzzing_content_discovery
- vulnerability_scanning
- network_service_scanning
- validation_support
- secret_leak_detection
- intelligence_osint
- manual_hil_integrations

Safety expectations:

- passive/safe: default autonomous
- active: allowed in safe mode if scope-valid
- intrusive/manual_only: approval or explicit override required

Registration model:

- wrappers are registered through `register_bugbounty_tools()`
- existing legacy wrapper ids are preserved for compatibility
