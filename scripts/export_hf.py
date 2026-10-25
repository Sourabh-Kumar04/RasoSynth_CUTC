#!/usr/bin/env python3
"""CLI utility to package and export datasets to Hugging Face Hub with DBOM attestation."""
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.publish_to_huggingface import main

if __name__ == "__main__":
    main()
