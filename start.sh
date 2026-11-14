#!/bin/bash
set -e
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"
echo "Starting RasoSynthTune on port ${PORT} with ${WORKERS} worker(s)..."
exec /app/.venv/bin/python main.py --host 0.0.0.0 --port "${PORT}" --workers "${WORKERS}"
