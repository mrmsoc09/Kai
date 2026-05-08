# /home/k1-admin/Kai/docker/nmap/Dockerfile
FROM debian:bookworm-slim

# Install nmap and other necessary network utilities
RUN apt-get update && apt-get install -y --no-install-recommends nmap iputils-ping net-tools && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN adduser --system --group kaiuser
USER kaiuser

# Set entrypoint to nmap
ENTRYPOINT ["nmap"]
CMD ["--help"]
