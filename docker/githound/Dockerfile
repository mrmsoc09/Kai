FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/tillson/git-hound@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /root/go/bin/git-hound /usr/local/bin/git-hound
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["git-hound"]
CMD ["-h"]
