FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /root/go/bin/grpcurl /usr/local/bin/grpcurl
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["grpcurl"]
CMD ["-h"]
