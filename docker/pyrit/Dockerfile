# /home/k1-admin/Kai/docker/pyrit/Dockerfile
FROM python:3.10-slim-bookworm

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Assuming PyRIT is a pip-installable package or cloneable repo
# If it's a repo, you would: RUN git clone <repo_url> . && pip install --no-cache-dir .
RUN pip install --no-cache-dir pyrit # Placeholder, confirm actual package name/install method

# Create a non-root user
RUN adduser --system --group kaiuser
USER kaiuser

# Set entrypoint and default command
ENTRYPOINT ["python3", "-m", "pyrit_cli"] # Placeholder entrypoint, assuming a CLI module
CMD ["--help"] # Placeholder command
