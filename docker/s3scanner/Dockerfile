FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/sa7mon/s3scanner@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/s3scanner /usr/local/bin/S3Scanner
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["S3Scanner"]
CMD ["-h"]
