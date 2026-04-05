#!/bin/bash

# ralph_loop.sh
# K1's Ralph Wiggum Loop Orchestrator for Stage 15 (Naive Persistence)
# Deploys 25+ concurrent Ralph instances to bypass WAFs.

# --- CONFIGURATION ---
RALPH_FUZZER_SCRIPT="Kai/apps/backend/src/agents/ralph_fuzzer.py"
PROGRESS_FILE_BASE="/tmp/ralph_progress" # Base for individual progress files
NUM_INSTANCES=25 # Number of concurrent Ralph instances
TARGET_URL="http://example.com/search" # Default target, to be replaced by K1 orchestration
MAX_RUN_TIME_SECONDS=3600 # Max run time for each Ralph instance (1 hour)

# --- FUNCTIONS ---

# Function to start a single Ralph instance
start_ralph_instance() {
    local instance_id=$1
    local target=$2
    local progress_file="${PROGRESS_FILE_BASE}_${instance_id}.txt"

    echo "$(date) - Starting Ralph instance ${instance_id} for target ${target}" | tee -a "${progress_file}"
    
    # Run Ralph Fuzzer in the background
    # Use unbuffered output to see progress in real-time if desired, or redirect to log files
    python3 -u "${RALPH_FUZZER_SCRIPT}" --target "${target}" --instance-id "${instance_id}" 
        > "/tmp/ralph_fuzzer_${instance_id}.log" 2>&1 &
    
    RALPH_PID=$!
    echo "${RALPH_PID}" > "/tmp/ralph_pid_${instance_id}.txt"
    echo "$(date) - Ralph instance ${instance_id} started with PID ${RALPH_PID}" | tee -a "${progress_file}"
}

# Function to stop a single Ralph instance
stop_ralph_instance() {
    local instance_id=$1
    local pid_file="/tmp/ralph_pid_${instance_id}.txt"
    if [ -f "${pid_file}" ]; then
        RALPH_PID=$(cat "${pid_file}")
        if kill -0 "${RALPH_PID}" > /dev/null 2>&1; then
            echo "$(date) - Stopping Ralph instance ${instance_id} (PID ${RALPH_PID})"
            kill "${RALPH_PID}"
            wait "${RALPH_PID}" 2>/dev/null
            echo "$(date) - Ralph instance ${instance_id} stopped."
        else
            echo "$(date) - Ralph instance ${instance_id} (PID ${RALPH_PID}) already dead."
        fi
        rm -f "${pid_file}"
    fi
}

# Function to monitor Ralph instances and restart if needed (Naive Persistence)
monitor_ralph_instances() {
    while true; do
        for i in $(seq 1 ${NUM_INSTANCES}); do
            local pid_file="/tmp/ralph_pid_${i}.txt"
            if [ -f "${pid_file}" ]; then
                RALPH_PID=$(cat "${pid_file}")
                if ! kill -0 "${RALPH_PID}" > /dev/null 2>&1; then
                    echo "$(date) - Ralph instance ${i} (PID ${RALPH_PID}) died. Restarting."
                    rm -f "${pid_file}" # Clean up old PID file
                    start_ralph_instance "${i}" "${TARGET_URL}" # Use orchestration context for target
                fi
            else
                # Instance not running, start it
                start_ralph_instance "${i}" "${TARGET_URL}"
            fi
        done
        sleep 10 # Check every 10 seconds
    done
}

# --- MAIN EXECUTION ---

# Clean up previous runs
echo "$(date) - Cleaning up previous Ralph runs..."
for i in $(seq 1 ${NUM_INSTANCES}); do
    stop_ralph_instance "${i}"
done
rm -f "${PROGRESS_FILE_BASE}"*.txt "/tmp/ralph_fuzzer_"*.log

# Start all Ralph instances
for i in $(seq 1 ${NUM_INSTANCES}); do
    start_ralph_instance "${i}" "${TARGET_URL}"
done

echo "$(date) - All Ralph instances launched. Starting monitor."

# Monitor and ensure persistence
monitor_ralph_instances

# --- Note: In a real K1, TARGET_URL and other parameters would be dynamically
#          provided by the Mission Orchestrator or a dedicated Ralph Orchestrator
#          based on input from Stage 16 Pre-Processor and Trilium context.
#          The progress.txt is meant for the Ralph instances themselves to record
#          their internal state/discoveries, not for this script to manage directly
#          for advanced persistence across reboots (which K1 Checkpointing handles).
