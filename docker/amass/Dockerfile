# /home/k1-admin/Kai/docker/amass/Dockerfile
FROM golang:1.22-alpine as builder

# Install git and other build dependencies
RUN apk add --no-cache git

WORKDIR /src
# Clone Amass and build
RUN git clone https://github.com/owasp-amass/amass.git .
RUN go mod download
RUN go build -o /usr/local/bin/amass ./cmd/amass

# --- Final image ---
FROM alpine:latest

# Install ca-certificates for HTTPS (common for Go tools)
RUN apk add --no-cache ca-certificates

# Copy the compiled binary from the builder stage
COPY --from=builder /usr/local/bin/amass /usr/local/bin/amass

# Create a non-root user
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser

# Set entrypoint and default command
ENTRYPOINT ["amass"]
CMD ["--help"]
