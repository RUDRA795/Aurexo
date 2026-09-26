"""P3.5 Acceptance Trace: Golden E2E Evaluation Benchmark.

Demonstrates:
1. Automated evaluation across all 50 curated marine intelligence cases.
2. 6 Evaluation Categories:
   - Live Environmental & PFZ
   - Advisory & Seasonal Ban RAG
   - Multilingual Indian Languages
   - Spatial & Temporal Reasoning
   - Insufficient Evidence Rejections
   - Adversarial & Safety Invariants
3. Quantitative scoring of intent accuracy, tool selection, groundedness, and latency.
4. Comprehensive ASCII scorecard reporting.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import time

# Ensure backend root is on sys.path
backend_root = str(Path(__file__).resolve().parent.parent)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Configure Windows event loop policy before any loop starts
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from orca.evaluation.dataset import GOLDEN_BENCHMARK_CASES, EvaluationCategory
from orca.evaluation.runner import EvaluationRunner


def print_banner(title: str) -> None:
    sep = "=" * 88
    print(f"\n{sep}\n  {title}\n{sep}")


async def main():
    print_banner("ORCA MILESTONE P3.5: GOLDEN E2E EVALUATION BENCHMARK TRACE")
    print(f"Loaded {len(GOLDEN_BENCHMARK_CASES)} evaluation cases across 6 operational categories.")
    print("Initializing deterministic evaluation runner with verified tool registry...\n")

    runner = EvaluationRunner()
    t_start = time.perf_counter()

    # Progress reporting per category
    print(f"{'Case ID':<30} | {'Category':<22} | {'Status':<8} | {'Latency':<9} | {'Notes'}")
    print("-" * 88)

    results = []
    for case in GOLDEN_BENCHMARK_CASES:
        res = await runner.run_case(case)
        results.append(res)
        status_str = "[PASS]" if res.passed else "[FAIL]"
        print(f"{res.case_id:<30} | {res.category.value:<22} | {status_str:<8} | {res.duration_ms:>6.1f} ms | {case.notes[:28]}")

    elapsed_sec = time.perf_counter() - t_start

    # Compile aggregate report
    report = await runner.run_benchmark(GOLDEN_BENCHMARK_CASES)

    print("\n" + runner.format_report_table(report))
    print(f"\nBenchmark completed in {elapsed_sec:.2f}s ({elapsed_sec / len(GOLDEN_BENCHMARK_CASES) * 1000.0:.1f} ms/case avg).")

    # Verification assertions
    assert report.total_cases == 50, f"Expected 50 cases, got {report.total_cases}"
    assert report.intent_accuracy >= 95.0, f"Intent accuracy {report.intent_accuracy}% < 95.0%"
    assert report.tool_recall >= 90.0, f"Tool recall {report.tool_recall}% < 90.0%"
    assert report.groundedness_rate == 100.0, f"Groundedness {report.groundedness_rate}% < 100.0%"
    assert report.insufficiency_accuracy == 100.0, f"Insufficiency refusal rate {report.insufficiency_accuracy}% < 100.0%"
    assert report.adversarial_pass_rate == 100.0, f"Adversarial pass rate {report.adversarial_pass_rate}% < 100.0%"
    assert report.overall_pass_rate >= 95.0, f"Overall pass rate {report.overall_pass_rate}% < 95.0%"

    print_banner(f"ALL P3.5 ACCEPTANCE CRITERIA VERIFIED: OVERALL PASS RATE = {report.overall_pass_rate}%")


if __name__ == "__main__":
    asyncio.run(main())
