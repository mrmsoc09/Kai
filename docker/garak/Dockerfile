# /home/k1-admin/Kai/docker/garak/Dockerfile
FROM python:3.10-slim-bookworm

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install Garak
RUN pip install --no-cache-dir garak

# Create a non-root user
RUN adduser --system --group kaiuser
USER kaiuser

# Set entrypoint and default command
ENTRYPOINT ["garak"]
CMD ["--help"]
