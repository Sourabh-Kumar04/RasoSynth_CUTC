"""
CANONICAL ENTRY POINT - This is the sole production entry point for RasoSynthTune.

Supports:
1. Production API Server: `rasosynthtune --host 0.0.0.0 --port 8000` or `rasosynthtune serve`
2. Autonomous Synthetic Generation CLI: `rasosynthtune generate --domain "..." --size 10`
3. Cryptographic DBOM Audit: `rasosynthtune audit --dataset path/to/dataset.jsonl`
4. Audited Benchmark Suite: `rasosynthtune benchmark`
5. Fine-Tuning Recipe Generator: `rasosynthtune recipe --framework axolotl --model "..."`
"""

import argparse
import sys
import uvicorn
from cli import main as cli_main


def main():
    """Main entry point for RasoSynthTune."""
    cli_commands = {"generate", "audit", "benchmark", "recipe", "serve"}
    
    # If a CLI subcommand is requested, delegate directly to the unified CLI
    if len(sys.argv) > 1 and sys.argv[1] in cli_commands:
        sys.exit(cli_main(sys.argv[1:]))

    # Also delegate to CLI if help flag is provided
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        sys.exit(cli_main(sys.argv[1:]))

    # Default to uvicorn API server
    parser = argparse.ArgumentParser(description="RasoSynthTune Canonical Server & Platform")
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
