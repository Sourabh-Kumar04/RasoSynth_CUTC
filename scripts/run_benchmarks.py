#!/usr/bin/env python3
"""CLI script to run quality benchmarks."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from research.quality_benchmark import QualityBenchmark


async def main():
    benchmark = QualityBenchmark()
    results = await benchmark.run_all()
    report = benchmark.generate_report(results)
    print(report)

    # Save report
    output_path = Path("outputs/benchmark_report.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(report)
    print(f"\nReport saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())