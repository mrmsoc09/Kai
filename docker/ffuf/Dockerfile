FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/ffuf/ffuf/v2@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/ffuf /usr/local/bin/ffuf
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["ffuf"]
CMD ["-h"]
