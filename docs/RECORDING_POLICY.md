# Recording Policy and Evidence Gate

- 24/7 recording is supported via a dedicated recorder service in Docker/K8s capturing a virtual display (Xvfb + ffmpeg).\n- Each run maintains segmented recordings under artifacts/recordings/<run_id>/seg_XXXX.mp4 and .json metadata.\n- Validation Gate: a screen recording showing safe reproduction is mandatory before a report can be finalized (enforced by /reports/finalize).
- Storage & Compression: segments are encoded H.264 with periodic compression tasks. Offloading to object storage/BigQuery can be enabled via policy (default off for local dev).

Control Plane:
- Backend emits JSON control events to artifacts/recordings/ctl: *start* (video_path) and *stop*.
- Recorder sidecar (Xvfb+ffmpeg) watches ctl via inotify and records to provided video_path.
- Configure via env: DISPLAY_NUM, RES, FPS, BITRATE. Default :99 @ 1920x1080@24fps.
