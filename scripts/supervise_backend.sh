#!/usr/bin/env bash
# Backend supervisor and auto-restart watchdog for RasoSynthTune
# Usage: ./scripts/supervise_backend.sh [--daemon|--check|--restart]

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

PYTHON_BIN="$REPO_DIR/.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

PID_FILE="/tmp/rasosynth_backend.pid"
SUPERVISOR_PID_FILE="/tmp/rasosynth_supervisor.pid"
LOG_FILE="/tmp/rasosynth-backend.log"
PORT=8000
HOST="0.0.0.0"
HEALTH_URL="http://127.0.0.1:${PORT}/health"

is_backend_alive() {
    curl -sf --connect-timeout 2 --max-time 3 "$HEALTH_URL" > /dev/null 2>&1
}

start_backend() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%SZ')] Starting RasoSynthTune backend on port ${PORT}..." >> "$LOG_FILE"
    nohup "$PYTHON_BIN" main.py --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
    local new_pid=$!
    echo "$new_pid" > "$PID_FILE"
    echo "Backend launched with PID $new_pid"
}

stop_backend() {
    echo "Stopping existing backend instances..."
    pkill -f "python.*main\.py.*--port $PORT" 2>/dev/null || true
    sleep 1
    pkill -9 -f "python.*main\.py.*--port $PORT" 2>/dev/null || true
    rm -f "$PID_FILE"
}

restart_backend() {
    stop_backend
    start_backend
    for _ in {1..20}; do
        if is_backend_alive; then
            echo "Backend successfully started and healthy."
            return 0
        fi
        sleep 1
    done
    echo "Warning: Backend started but health probe did not return 200 within 20s. Check $LOG_FILE"
    return 1
}

case "${1:-}" in
    --restart)
        restart_backend
        exit 0
        ;;
    --check)
        if is_backend_alive; then
            echo "Backend is RUNNING and responding on port ${PORT}."
            exit 0
        else
            echo "Backend is NOT responding on port ${PORT}."
            exit 1
        fi
        ;;
    --daemon)
        echo $$ > "$SUPERVISOR_PID_FILE"
        echo "Supervisor daemon started with PID $$"
        trap 'rm -f "$SUPERVISOR_PID_FILE"; exit 0' SIGTERM SIGINT

        while true; do
            if ! is_backend_alive; then
                echo "[$(date -u '+%Y-%m-%d %H:%M:%SZ')] Health probe failed. Restarting backend..." >> "$LOG_FILE"
                stop_backend
                start_backend
                sleep 5
            fi
            sleep 5
        done
        ;;
    *)
        if ! is_backend_alive; then
            echo "Backend is down. Restarting..."
            restart_backend
        else
            echo "Backend is already running and healthy."
        fi
        ;;
esac
