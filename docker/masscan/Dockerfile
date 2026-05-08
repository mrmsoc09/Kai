FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends masscan && rm -rf /var/lib/apt/lists/*
# NOTE: requires cap_add: [NET_RAW, NET_ADMIN] in docker-compose for raw socket access
ENTRYPOINT ["masscan"]
CMD ["--help"]
