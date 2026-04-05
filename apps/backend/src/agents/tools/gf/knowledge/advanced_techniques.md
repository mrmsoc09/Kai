# GF Advanced Techniques

## Multi-Pattern Workflow
Run separate passes for each category and store outputs independently (`gf_sqli.txt`, `gf_xss.txt`, etc.).

## Pattern Paths
GF pattern files are typically located under `~/.gf/`. Keep them version-controlled for consistent routing behavior.

## Manual Safety Rule
RCE-tagged URLs are always manual-review candidates and should not be auto-escalated to unsafe execution.

## Extensibility
Custom patterns can be added to match program-specific parameter naming conventions and framework artifacts.
