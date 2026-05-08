# /home/k1-admin/Kai/docker/nuclei/Dockerfile
FROM golang:1.25-alpine as builder

# Install git and other build dependencies
RUN apk add --no-cache git

WORKDIR /src
# Clone nuclei and build
RUN git clone https://github.com/projectdiscovery/nuclei.git --branch v3.8.0 --depth 1 .
RUN go mod download
RUN go build -o /usr/local/bin/nuclei ./cmd/nuclei

# --- Final image ---
FROM alpine:latest

# Install ca-certificates for HTTPS
RUN apk add --no-cache ca-certificates

# Copy the compiled binary from the builder stage
COPY --from=builder /usr/local/bin/nuclei /usr/local/bin/nuclei

# Create a non-root user
RUN adduser --system --group kaiuser
USER kaiuser

# Set entrypoint to nuclei
ENTRYPOINT ["nuclei"]
CMD ["-h"]
