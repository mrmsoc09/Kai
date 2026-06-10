FROM golang:1.26-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/hahwul/dalfox/v2@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/dalfox /usr/local/bin/dalfox
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["dalfox"]
CMD ["-h"]
