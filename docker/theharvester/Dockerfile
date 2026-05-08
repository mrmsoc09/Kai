# /home/k1-admin/Kai/docker/theharvester/Dockerfile
FROM python:3.12-slim-bookworm as builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential && rm -rf /var/lib/apt/lists/*

# Clone the repository
WORKDIR /app
RUN git clone https://github.com/laramies/theHarvester.git --branch v4.10.1 --depth 1 .

# Install theHarvester as a local package
RUN pip install --no-cache-dir .

# --- Final image ---
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY --from=builder /app /app

# Create a non-root user
RUN adduser --system --group kaiuser
USER kaiuser

# Set entrypoint
ENTRYPOINT ["python3", "-m", "theharvester.theharvester"]
CMD ["-h"]
