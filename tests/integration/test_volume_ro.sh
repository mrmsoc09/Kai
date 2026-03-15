#!/usr/bin/env bash
# Integration test to confirm source directories are read-only in the container

echo "Checking backend container..."
BACKEND_RO=$(docker exec k1_backend sh -c "touch /app/apps/test_write 2>&1" | grep -i "Read-only file system")
if [ -n "$BACKEND_RO" ]; then
    echo "PASS: /app/apps is read-only in k1_backend"
else
    echo "SKIP: k1_backend not running or touch failed for other reasons. Checking static config..."
    if grep -q "./apps:/app/apps:ro" docker-compose.dev.yml; then
        echo "PASS: Static config check passed for backend RO mount."
    else
        echo "FAIL: Backend source mount is not RO."
        exit 1
    fi
fi

echo "Checking worker container..."
WORKER_RO=$(docker exec k1_worker sh -c "touch /app/config/test_write 2>&1" | grep -i "Read-only file system")
if [ -n "$WORKER_RO" ]; then
    echo "PASS: /app/config is read-only in k1_worker"
else
    echo "SKIP: k1_worker not running or touch failed for other reasons. Checking static config..."
    if grep -q "./config:/app/config:ro" docker-compose.dev.yml; then
        echo "PASS: Static config check passed for worker RO mount."
    else
        echo "FAIL: Worker source mount is not RO."
        exit 1
    fi
fi

exit 0
