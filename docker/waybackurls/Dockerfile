FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN go install -v github.com/tomnomnom/waybackurls@latest
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/waybackurls /usr/local/bin/waybackurls
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["waybackurls"]
CMD ["-h"]
