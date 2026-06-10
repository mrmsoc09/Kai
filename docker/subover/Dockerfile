FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOOS=linux
RUN git clone https://github.com/Ice3man543/SubOver.git /src
WORKDIR /src
RUN go mod init github.com/Ice3man543/SubOver && \
    go get golang.org/x/net@v0.33.0 && \
    go mod tidy && \
    go build -o /go/bin/SubOver
FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /go/bin/SubOver /usr/local/bin/SubOver
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["SubOver"]
CMD ["-h"]
