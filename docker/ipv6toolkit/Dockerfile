FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends ipv6toolkit && rm -rf /var/lib/apt/lists/*
# NOTE: most ipv6toolkit tools require cap_add: [NET_RAW, NET_ADMIN]
ENTRYPOINT ["scan6"]
CMD ["-h"]
