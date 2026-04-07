# KAISON AI Sandbox

Isolated Docker container for payload execution.

## Isolation Properties

- --network=none (no network access)
- --read-only root filesystem
- --tmpfs /workspace (64MB, no host access)
- --memory 256m (hard memory limit)
- --cpus 0.5 (CPU limit)
- --pids-limit 64 (process count limit)
- --cap-drop ALL (all capabilities removed)
- --no-new-privileges
- --user sandbox (non-root)
- Seccomp profile (restricted syscalls)
- Container destroyed after every execution

## Build

    docker build -t kaison-sandbox:latest .

## Test

    docker run --rm \
      --network none \
      --memory 256m \
      --read-only \
      --tmpfs /workspace:size=64m \
      --cap-drop ALL \
      --no-new-privileges \
      --user sandbox \
      kaison-sandbox:latest \
      /bin/bash -c "echo 'isolation verified'"

## Environment Variables

KAISON_SANDBOX_IMAGE — override image name
  default: kaison-sandbox:latest
