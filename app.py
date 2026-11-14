#!/usr/bin/env python3
"""
Hugging Face Space Free Tier Entrypoint.
Runs the complete RasoSynthTune FastAPI backend on Hugging Face Spaces using
the 100% FREE Gradio/Python runtime (2 vCPU · 16 GB RAM · Zero Payment Required).
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.server import app

# Hugging Face Spaces expect apps to listen on port 7860 by default
PORT = int(os.getenv("PORT", "7860"))
HOST = os.getenv("HOST", "0.0.0.0")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
