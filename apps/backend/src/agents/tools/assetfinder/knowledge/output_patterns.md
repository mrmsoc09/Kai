# Assetfinder Output Patterns

## High Signal
- `admin.target.com`
- `api.target.com`
- `staging.target.com`
- `internal.target.com`
- `jenkins.target.com`
- `grafana.target.com`

These labels typically imply privileged interfaces, staging systems, or internal services.

## Lower Signal
- `mail.target.com`
- `smtp.target.com`
- `ftp.target.com`
- `autodiscover.target.com`

These still matter, but are usually lower-priority for web exploitation workflow.

## Validation Reminder
A hostname appearing in passive output is not proof of liveness. Always resolve with dnsx before forwarding to active phases.
