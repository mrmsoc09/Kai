FROM golang:1.22-bookworm AS builder
RUN apt-get update -qq && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN go install github.com/trufflesecurity/trufflehog/v3@latest
FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends ca-certificates git && rm -rf /var/lib/apt/lists/*
COPY --from=builder /go/bin/trufflehog /usr/local/bin/trufflehog
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["trufflehog"]
CMD ["--help"]
