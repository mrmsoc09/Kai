FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/subfinder /usr/local/bin/subfinder

ENTRYPOINT ["subfinder"]
CMD ["-h"]
