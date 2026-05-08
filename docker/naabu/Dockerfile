# NOTE: requires cap_add: [NET_RAW, NET_ADMIN] in docker-compose
FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /root/go/bin/naabu /usr/local/bin/naabu
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["naabu"]
CMD ["-h"]
