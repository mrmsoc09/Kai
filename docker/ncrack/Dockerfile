FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends ncrack && rm -rf /var/lib/apt/lists/*
# NOTE: requires cap_add: [NET_RAW] in docker-compose for raw socket operations
ENTRYPOINT ["ncrack"]
CMD ["-h"]
