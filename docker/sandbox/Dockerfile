FROM python:3.11-slim

# Create non-root sandbox user
RUN groupadd -r sandbox && \
    useradd -r -g sandbox \
      -s /bin/false \
      -d /workspace \
      sandbox

# Install minimal tools only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      wget \
      netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Switch to non-root user
USER sandbox

# Workspace is mounted as tmpfs at runtime
WORKDIR /workspace
