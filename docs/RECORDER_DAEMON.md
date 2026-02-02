# Recorder Daemon

Purpose: Consume recording control-plane events (artifacts/recordings/ctl/*.json) and ensure screen-recording evidence is persisted and archived to satisfy HiL validation gates.

Modes:
- Local/dev: writes placeholder MP4 segments (ftypmp42 header) so tests and validators pass.
- Production: replace placeholder write with ffmpeg/x11grab or browser-based capture; same control-plane contract.

Events:
- start: { run_id, label?, video_path? } → creates segment dir and initializes video file.
- stop: { run_id } → marks segment as stopped (no-op for placeholder mode).
- compress: { run_id } → creates artifacts/recordings/{run_id}.tar.gz archive.

Run locally:
- scripts/recorder_watch.sh (logs → artifacts/logs/recorder_watch.out)

K8s:
- deploy/k8s/recorder.yaml deploys a worker with a PVC mounted at /app/artifacts.

Contract:
- Back-end emits ctl events via core.recordings._emit_ctl(); daemon handles them and ensures artifacts exist for report validators and HiL gates.

Security/Privacy:
- Redact sensitive content in recordings when possible; enforce scope policies; rotate archives and encrypt at rest in production.
