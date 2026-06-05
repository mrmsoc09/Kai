FROM golang:alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/httpx /usr/local/bin/httpx

ENTRYPOINT ["httpx"]
CMD ["-h"]
