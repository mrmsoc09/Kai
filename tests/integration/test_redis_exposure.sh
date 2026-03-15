#!/usr/bin/env bash
# Integration test to confirm Redis is unreachable from outside the Docker network

# Check live docker container if running
EXPOSED_IP=$(docker inspect --format='{{range $p, $conf := .NetworkSettings.Ports}}{{if eq $p "6379/tcp"}}{{(index $conf 0).HostIp}}{{end}}{{end}}' k1_redis 2>/dev/null)

if [ "$EXPOSED_IP" == "127.0.0.1" ]; then
    echo "PASS: Redis is bound only to 127.0.0.1"
    exit 0
elif [ -z "$EXPOSED_IP" ]; then
    echo "SKIP: k1_redis container not running, performing static config check..."
    if grep -q "127.0.0.1:6379:6379" docker-compose.dev.yml; then
        echo "PASS: Static config check passed. Redis is bound to 127.0.0.1."
        exit 0
    else
        echo "FAIL: Static config check failed."
        exit 1
    fi
else
    echo "FAIL: Redis exposed on $EXPOSED_IP"
    exit 1
fi
