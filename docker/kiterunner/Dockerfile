FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates build-base make
WORKDIR /src
RUN git clone --depth 1 https://github.com/assetnote/kiterunner .
RUN go mod download && (make build 2>/dev/null || go build -o dist/kr ./cmd/kr)
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /src/dist/kr /usr/local/bin/kr
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["kr"]
CMD ["--help"]
