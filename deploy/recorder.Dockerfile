FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg xvfb x11-utils inotify-tools jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY ../scripts/recorder_watch.sh /app/recorder_watch.sh
RUN chmod +x /app/recorder_watch.sh
VOLUME ["/recordings"]
ENV CTL_DIR=/recordings/ctl
CMD ["/app/recorder_watch.sh"]
