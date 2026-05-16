# Artifact Storage for Read-Only Tool Containers

This deployment keeps tool containers with `read_only: true` and exposes only specific writable bind mounts for scan output and cache data.

## Mount strategy

- Host root: `/var/kai-artifacts`
- Container root: `/tmp/kai-artifacts`
- Dedicated writable paths:
  - nmap: `/tmp/nmap-output`
  - nuclei: `/tmp/nuclei-output`
  - gitleaks: `/tmp/gitleaks-output`
  - burp cache: `/tmp/burp-cache`
  - shared cache: `/home/kai/.cache`

The compose file uses:
- `K1_ARTIFACTS_HOST_ROOT` (default `/var/kai-artifacts`)
- `K1_ARTIFACTS_CONTAINER_ROOT` (default `/tmp/kai-artifacts`)
- `K1_ARTIFACTS_ROOT` and per-tool paths built from the container root.

## Initialize host directories

Run once on each Docker host:

```bash
K1_ARTIFACTS_HOST_ROOT=/var/kai-artifacts ./scripts/init_kai_artifacts.sh
```

## Daily cleanup and quota enforcement

Cleanup script:

```bash
./scripts/cleanup_kai_artifacts.sh
```

Behavior:
- Deletes files older than `K1_ARTIFACT_RETENTION_DAYS` (default `14`).
- Enforces `K1_ARTIFACT_MAX_BYTES_PER_TOOL` per tool directory (default `107374182400`, 100 GiB).

## Enable systemd timer (recommended)

Install and start daily cleanup:

```bash
sudo ./scripts/install_kai_artifact_cleanup_timer.sh
```

Config file:
- `/etc/default/kai-artifact-cleanup` (seeded from `deploy/systemd/kai-artifact-cleanup.env`)

Units:
- `deploy/systemd/kai-artifact-cleanup.service`
- `deploy/systemd/kai-artifact-cleanup.timer`
