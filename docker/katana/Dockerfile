FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates gcc musl-dev
ENV CGO_ENABLED=1 GOOS=linux
RUN go install -v github.com/projectdiscovery/katana/cmd/katana@v1.4.0
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/katana /usr/local/bin/katana
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["katana"]
CMD ["-h"]
