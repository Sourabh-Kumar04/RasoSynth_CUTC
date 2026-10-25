#!/usr/bin/env python3
"""
Benchmark Contamination & Data Leakage Diagnostic CLI Tool.

Audits synthetic instruction datasets against evaluation benchmark test sets
(MMLU-Hindi, GSM8K, IndicGLUE, ARC Challenge) using n-gram containment
and Jaccard word-level hashing to verify test-set purity.

Usage:
    python scripts/check_contamination.py --input outputs/example_indic_legal/dataset.jsonl
    python scripts/check_contamination.py --dry-run
    python scripts/check_contamination.py --input data.jsonl --strict --output report.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.evaluation.contamination_checker import (
    BENCHMARK_SIGNATURES,
    check_dataset_contamination,
)


def load_dataset_samples(path: Path) -> List[Dict[str, Any]]:
    """Load sample records from JSONL, JSON, CSV, or Parquet."""
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    ext = path.suffix.lower()
    samples: List[Dict[str, Any]] = []

    if ext == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
    elif ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            samples = data if isinstance(data, list) else data.get("samples", [data])
    elif ext == ".csv":
        import csv
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            samples = list(reader)
    elif ext == ".parquet":
        import pandas as pd
        df = pd.read_parquet(path)
        samples = df.to_dict(orient="records")
    else:
        raise ValueError(f"Unsupported format: {ext}")

    return samples


def run_audit(
    samples: List[Dict[str, Any]],
    benchmarks: List[str] = None,
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Execute benchmark decontamination audit."""
    return check_dataset_contamination(
        samples=samples,
        benchmarks=benchmarks,
        similarity_threshold=threshold,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Audit dataset for benchmark contamination (MMLU, GSM8K, IndicGLUE, ARC)."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Path to dataset file (JSONL, JSON, CSV, Parquet).",
    )
    parser.add_argument(
        "-b", "--benchmarks",
        type=str,
        default=None,
        help="Comma-separated benchmark names to verify (default: all supported).",
    )
    parser.add_argument(
        "-t", "--threshold",
        type=float,
        default=0.45,
        help="Jaccard n-gram overlap threshold (default: 0.45).",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Optional destination path for JSON audit report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero code if any contamination is detected.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run self-audit on simulated clean and contaminated samples.",
    )

    args = parser.parse_args()

    benchmarks = None
    if args.benchmarks:
        benchmarks = [b.strip() for b in args.benchmarks.split(",") if b.strip()]

    if args.dry_run or not args.input:
        print("[*] Running in dry-run diagnostic mode with benchmark probes...")
        samples = [
            {
                "instruction": "What are the compliance requisites for ITC claim under Section 16 CGST Act?",
                "response": "Under Section 16(2) of the CGST Act, a registered taxpayer must possess tax invoice...",
            },
            {
                "instruction": "Explain the difference between primary and secondary evidence in BSA 2023.",
                "response": "Primary evidence under Section 57 refers to the document itself produced for inspection...",
            },
            {
                "instruction": "Solve math: natalia sold clips to 48 of her friends in april how many did she sell?",
                "response": "Natalia sold 48 clips in April to her friends.",
            },
        ]
    else:
        input_path = Path(args.input)
        print(f"[*] Loading dataset from {input_path}...")
        try:
            samples = load_dataset_samples(input_path)
            print(f"[✓] Loaded {len(samples)} samples.")
        except Exception as exc:
            print(f"[✗] Error loading dataset: {exc}", file=sys.stderr)
            sys.exit(1)

    print(f"[*] Auditing {len(samples)} samples against benchmarks: {benchmarks or list(BENCHMARK_SIGNATURES.keys())}...")
    report = run_audit(samples, benchmarks=benchmarks, threshold=args.threshold)

    is_clean = report["status"] == "clean"
    print("\n" + "=" * 65)
    print("  RASOSYNTH BENCHMARK DECONTAMINATION REPORT")
    print("=" * 65)
    print(f"  Audit Status          : {'✓ ZERO CONTAMINATION' if is_clean else '✗ CONTAMINATION DETECTED'}")
    print(f"  Certificate ID        : {report['audit_certificate_id']}")
    print(f"  Total Samples Audited : {report['total_samples_audited']}")
    print(f"  Clean Samples         : {report['clean_samples_count']}")
    print(f"  Contaminated Samples  : {report['contaminated_samples_count']}")
    print(f"  Contamination Rate    : {report['contamination_rate_pct']}%")
    print(f"  Benchmarks Checked    : {', '.join(report['benchmarks_checked'])}")
    print("=" * 65)

    if not is_clean:
        print("\n[!] Contaminated Sample Trace:")
        for rec in report.get("contaminated_records", [])[:5]:
            print(f"  - Sample #{rec['sample_index']}: {rec['instruction']}")
            for m in rec.get("matches", []):
                print(f"    ↳ Overlap with {m['benchmark']} (Score: {m['overlap_score']}): {m['matched_ngrams']}")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[✓] Audit report saved to {out_path.resolve()}")

    if args.strict and not is_clean:
        print("\n[✗] Strict mode enabled: Failing build due to contamination.", file=sys.stderr)
        sys.exit(1)

    print("\n[✓] Decontamination audit complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
