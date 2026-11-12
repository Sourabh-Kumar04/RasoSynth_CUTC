#!/bin/bash
set -e
PORT="${PORT:-8000}"
echo "Starting RasoSynthTune on port ${PORT}..."
exec /app/.venv/bin/python main.py --host 0.0.0.0 --port "${PORT}" --workers 4
