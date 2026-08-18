"""
CANONICAL ENTRY POINT - This is the sole production entry point for RasoSynthTune.

This module starts the canonical server (api/server.py).
Do NOT use api/server_v2.py, api/server_production.py, or api/server_standalone.py directly.
The canonical orchestrator is core/orchestrator_core.py (DatasetOrchestrator).
"""

"""Main entry point for RasoSynthTune."""
import uvicorn
import argparse


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="RasoSynthTune")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")

    args = parser.parse_args()

    uvicorn.run(
        "api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()