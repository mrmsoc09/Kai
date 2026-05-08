FROM rust:1.78-slim-bookworm AS builder
RUN apt-get update -qq && apt-get install -y --no-install-recommends libssl-dev pkg-config && rm -rf /var/lib/apt/lists/*
RUN cargo install feroxbuster
FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/cargo/bin/feroxbuster /usr/local/bin/feroxbuster
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["feroxbuster"]
CMD ["-h"]
